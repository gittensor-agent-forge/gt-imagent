from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class JudgeError(RuntimeError):
    """Raised when a live judge cannot produce a usable verdict."""


def _check_values(check: dict[str, Any]) -> list[str]:
    if "values" in check:
        return [str(value) for value in check["values"]]
    if "value" in check:
        return [str(check["value"])]
    return []


def resolve_image_path(output: dict[str, Any], output_dir: Path) -> Path | None:
    image_path = output.get("image_path")
    if not image_path:
        return None
    path = Path(image_path)
    if not path.is_absolute():
        path = output_dir / path
    return path


_JUDGMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["checks"],
    "additionalProperties": False,
    "properties": {
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["index", "passed", "reason"],
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer"},
                    "passed": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
        }
    },
}


def _judge_prompt(
    case: dict[str, Any],
    trace: dict[str, Any],
    image_checks: list[tuple[int, dict[str, Any]]],
) -> str:
    final_context = trace.get("final_generation_context", {}) if isinstance(trace, dict) else {}
    criteria = [
        {
            "index": index,
            "type": check.get("type"),
            "required_visible_values": _check_values(check),
        }
        for index, check in image_checks
    ]
    return (
        "You are judging an image-agent benchmark output. "
        "Evaluate only visible content in the image. Do not use the file name, hidden metadata, "
        "or the expected answer as evidence unless it is visibly present. "
        "Return false for ambiguous, missing, or materially incorrect content.\n\n"
        f"Case id: {case.get('id')}\n"
        f"User prompt: {case.get('prompt')}\n"
        f"Agent final generation prompt: {final_context.get('prompt', '')}\n"
        f"Criteria JSON: {json.dumps(criteria, ensure_ascii=True, sort_keys=True)}\n\n"
        "Return JSON matching the provided schema."
    )


def _normalize_verdicts(
    verdict: dict[str, Any],
    image_checks: list[tuple[int, dict[str, Any]]],
    provider: str,
    cached: bool,
) -> dict[int, dict[str, Any]]:
    returned = verdict.get("checks")
    if not isinstance(returned, list):
        raise JudgeError(f"{provider} verdict missing checks array")
    by_index = {int(item["index"]): item for item in returned if isinstance(item, dict) and "index" in item}
    results: dict[int, dict[str, Any]] = {}
    for index, _ in image_checks:
        item = by_index.get(index)
        if not item:
            results[index] = {
                "passed": False,
                "reason": f"{provider} judge omitted this check",
                "provider": provider,
                "cached": cached,
            }
            continue
        results[index] = {
            "passed": bool(item.get("passed")),
            "reason": str(item.get("reason", "")),
            "provider": provider,
            "cached": cached,
        }
    return results


class MockTextJudge:
    provider = "mock_text"

    def __init__(self, config: dict[str, Any], output_dir: Path) -> None:
        self.config = config
        self.output_dir = output_dir

    def evaluate_image_checks(
        self,
        case: dict[str, Any],
        output: dict[str, Any],
        trace: dict[str, Any],
        checks: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        path = resolve_image_path(output, self.output_dir)
        image_text, error = "", None
        if path is None:
            error = "missing image_path"
        elif not path.exists():
            error = f"image does not exist: {path}"
        else:
            image_text = path.read_text(encoding="utf-8", errors="ignore").lower()

        results: dict[int, dict[str, Any]] = {}
        for index, check in enumerate(checks):
            if check.get("type") != "image_contains":
                continue
            wanted = [value.lower() for value in _check_values(check)]
            if error:
                results[index] = {"passed": False, "reason": error, "provider": self.provider}
                continue
            passed = all(value in image_text for value in wanted)
            reason = "image text contains requested values" if passed else f"image text lacks {wanted}"
            results[index] = {"passed": passed, "reason": reason, "provider": self.provider}
        return results


class _ApiImageJudge:
    """Shared scaffolding for API-backed image judges.

    Subclasses set ``provider`` and the ``default_*`` connection settings and
    implement ``_request_payload`` (their API's request body) and
    ``_extract_verdict_text`` (pulling the model's text out of the response). Prompt
    construction, image-hash caching, HTTP, fail-closed handling, and verdict
    normalization are shared here.
    """

    provider = "api"
    default_model = ""
    default_api_key_env = ""
    default_endpoint = ""

    def __init__(self, config: dict[str, Any], output_dir: Path) -> None:
        judge_config = config.get("evaluation", {}).get("image_judge", {})
        self.config = judge_config
        self.output_dir = output_dir
        self.model = str(judge_config.get("model", self.default_model))
        self.api_key_env = str(judge_config.get("api_key_env", self.default_api_key_env))
        self.api_key = os.environ.get(self.api_key_env)
        self.endpoint = str(judge_config.get("endpoint", self.default_endpoint))
        self.timeout_seconds = int(judge_config.get("timeout_seconds", 120))
        self.detail = str(judge_config.get("detail", "high"))
        self.fail_closed = bool(judge_config.get("fail_closed", True))
        self.total_cost_usd = 0.0
        cache_dir = judge_config.get("cache_dir")
        self.cache_dir = Path(cache_dir) if cache_dir else output_dir / "judge_cache"
        if not self.cache_dir.is_absolute():
            self.cache_dir = Path.cwd() / self.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_image_checks(
        self,
        case: dict[str, Any],
        output: dict[str, Any],
        trace: dict[str, Any],
        checks: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        image_checks = [(index, check) for index, check in enumerate(checks) if check.get("type") == "image_contains"]
        if not image_checks:
            return {}
        try:
            return self._evaluate(case, output, trace, image_checks)
        except Exception as exc:  # noqa: BLE001
            if not self.fail_closed:
                raise
            return {
                index: {
                    "passed": False,
                    "reason": f"{self.provider} judge error: {exc}",
                    "provider": self.provider,
                }
                for index, _ in image_checks
            }

    def _evaluate(
        self,
        case: dict[str, Any],
        output: dict[str, Any],
        trace: dict[str, Any],
        image_checks: list[tuple[int, dict[str, Any]]],
    ) -> dict[int, dict[str, Any]]:
        if not self.api_key:
            raise JudgeError(f"{self.api_key_env} is required for {self.provider} image judging")
        image_path = resolve_image_path(output, self.output_dir)
        if image_path is None or not image_path.exists():
            raise JudgeError(f"image does not exist: {image_path}")

        image_sha = _file_sha256(image_path)
        prompt = _judge_prompt(case, trace, image_checks)
        cache_key = _stable_sha256(
            {
                "provider": self.provider,
                "model": self.model,
                "detail": self.detail,
                "image_sha256": image_sha,
                "prompt": prompt,
            }
        )
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return _normalize_verdicts(cached["verdict"], image_checks, self.provider, cached=True)

        response = self._post_json(self._request_payload(prompt, image_path))
        verdict = _parse_json_object(self._extract_verdict_text(response))
        cost_usd = self._response_cost(response)
        self.total_cost_usd += cost_usd
        cache_path.write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "model": self.model,
                    "image_sha256": image_sha,
                    "prompt": prompt,
                    "verdict": verdict,
                    "cost_usd": cost_usd,
                    "raw_response": response,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return _normalize_verdicts(verdict, image_checks, self.provider, cached=False)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise JudgeError(f"{self.provider} HTTP {exc.code}: {body}") from exc
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise JudgeError(f"{self.provider} response must be a JSON object")
        if data.get("error"):
            raise JudgeError(f"{self.provider} API error: {data['error']}")
        return data

    def _request_payload(self, prompt: str, image_path: Path) -> dict[str, Any]:
        raise NotImplementedError

    def _extract_verdict_text(self, response: dict[str, Any]) -> str:
        raise NotImplementedError

    def _response_cost(self, response: dict[str, Any]) -> float:
        """USD cost of one judge call; providers that report it override this."""
        return 0.0


class OpenRouterImageJudge(_ApiImageJudge):
    """Image judge backed by the OpenRouter Chat Completions API.

    OpenRouter is Chat Completions compatible, so image input uses the ``image_url``
    content part and structured output uses ``response_format`` with a JSON schema.
    ``provider.require_parameters`` makes OpenRouter route only to providers that
    honor the schema instead of returning free-form text.
    """

    provider = "openrouter"
    default_model = "openai/gpt-4o"
    default_api_key_env = "OPENROUTER_API_KEY"
    default_endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, config: dict[str, Any], output_dir: Path) -> None:
        super().__init__(config, output_dir)
        self.referer = self.config.get("referer")
        self.title = self.config.get("title")

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.referer:
            headers["HTTP-Referer"] = str(self.referer)
        if self.title:
            headers["X-OpenRouter-Title"] = str(self.title)
        return headers

    def _request_payload(self, prompt: str, image_path: Path) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_data_url(image_path), "detail": self.detail},
                        },
                    ],
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "image_agent_judgment",
                    "strict": True,
                    "schema": _JUDGMENT_SCHEMA,
                },
            },
            "provider": {"require_parameters": True},
        }
        if self.config.get("max_output_tokens"):
            payload["max_tokens"] = int(self.config["max_output_tokens"])
        if self.config.get("reasoning_effort"):
            payload["reasoning"] = {"effort": str(self.config["reasoning_effort"])}
        return payload

    def _extract_verdict_text(self, response: dict[str, Any]) -> str:
        return _extract_message_content(response)

    def _response_cost(self, response: dict[str, Any]) -> float:
        usage = response.get("usage")
        if isinstance(usage, dict) and usage.get("cost") is not None:
            return float(usage["cost"])
        return 0.0


def build_image_judge(config: dict[str, Any], output_dir: Path):
    judge_config = config.get("evaluation", {}).get("image_judge", {})
    provider = str(judge_config.get("provider", "mock_text"))
    if provider == "mock_text":
        return MockTextJudge(config, output_dir)
    if provider == "openrouter":
        return OpenRouterImageJudge(config, output_dir)
    raise ValueError(f"Unknown image judge provider: {provider}")


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_sha256(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
    raise JudgeError("OpenRouter response did not contain message content")


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise JudgeError("Judge output must be a JSON object")
    return data
