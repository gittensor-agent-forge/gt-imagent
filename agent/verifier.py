from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class ImageVerificationError(RuntimeError):
    """Raised when agent-side image verification fails."""


class MockTextVerifier:
    provider = "mock_text"

    def __init__(self, config: dict[str, Any] | None = None, workdir: Path | None = None) -> None:
        self.config = config or {}
        self.workdir = Path(workdir) if workdir is not None else None
        self.total_cost_usd = 0.0

    def evaluate_image_checks(
        self,
        case: dict[str, Any],
        output: dict[str, Any],
        trace: dict[str, Any],
        checks: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        del case, trace
        text = self._read_text(Path(output["image_path"]))
        verdicts: dict[int, dict[str, Any]] = {}
        for index, check in enumerate(checks):
            value = str(check.get("value", ""))
            passed = value in text
            verdicts[index] = {
                "passed": passed,
                "reason": "exact visible text matched" if passed else "exact visible text missing",
                "provider": self.provider,
            }
        return verdicts

    def _read_text(self, image_path: Path) -> str:
        if not image_path.exists():
            return ""
        if image_path.suffix.lower() == ".svg":
            return self._read_svg_visible_text(image_path)
        if image_path.suffix.lower() == ".txt":
            return image_path.read_text(encoding="utf-8", errors="ignore")
        return ""

    def _read_svg_visible_text(self, image_path: Path) -> str:
        try:
            root = ET.fromstring(image_path.read_text(encoding="utf-8", errors="ignore"))
        except ET.ParseError:
            return ""
        lines: list[str] = []
        for element in root.iter():
            if self._svg_local_name(element.tag) != "text":
                continue
            text = "".join(element.itertext()).strip()
            if text:
                lines.append(html.unescape(text))
        return "\n".join(lines)

    def _svg_local_name(self, tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[1]
        return tag


class OpenRouterVisionVerifier:
    provider = "openrouter_vision"

    def __init__(self, config: dict[str, Any], workdir: Path) -> None:
        self.config = config
        self.workdir = Path(workdir)
        self.model = str(config.get("model", "openai/gpt-4o"))
        self.api_key_env = str(config.get("api_key_env", "OPENROUTER_API_KEY"))
        self.api_key = os.environ.get(self.api_key_env)
        if not self.api_key:
            raise ImageVerificationError(f"{self.api_key_env} is required for live image verification")
        self.endpoint = str(config.get("endpoint", "https://openrouter.ai/api/v1/chat/completions"))
        self.timeout_seconds = int(config.get("timeout_seconds", 180))
        self.referer = config.get("referer")
        self.title = config.get("title")
        self.total_cost_usd = 0.0

    def evaluate_image_checks(
        self,
        case: dict[str, Any],
        output: dict[str, Any],
        trace: dict[str, Any],
        checks: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        del case, trace
        values = [str(check.get("value", "")) for check in checks]
        if not values:
            return {}

        image_path = Path(output["image_path"])
        response = self._post_json(self._payload(image_path, values))
        usage = response.get("usage", {})
        usage = usage if isinstance(usage, dict) else {}
        self.total_cost_usd += float(usage.get("cost") or 0.0)

        parsed = self._parse_response(response)
        by_value = {
            str(item.get("value", "")): {
                "passed": bool(item.get("passed")),
                "reason": str(item.get("reason", "")).strip() or "no reason provided",
                "provider": self.provider,
            }
            for item in parsed
            if isinstance(item, dict)
        }

        verdicts: dict[int, dict[str, Any]] = {}
        for index, value in enumerate(values):
            verdicts[index] = by_value.get(
                value,
                {
                    "passed": False,
                    "reason": "verifier response did not include this exact string",
                    "provider": self.provider,
                },
            )
        return verdicts

    def _payload(self, image_path: Path, values: list[str]) -> dict[str, Any]:
        media_type = mimetypes.guess_type(image_path.name, strict=False)[0] or "application/octet-stream"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        checks_json = json.dumps(values, ensure_ascii=True)
        instructions = (
            "Check whether each exact string is visibly present in the image. "
            "Use exact matching, not paraphrase matching. "
            "Return JSON only in the form "
            '{"checks":[{"value":"...", "passed":true, "reason":"..."}]}. '
            f"Strings to verify: {checks_json}"
        )
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You verify exact visible text in images. Return strict JSON only.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instructions},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
        }

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.referer:
            headers["HTTP-Referer"] = str(self.referer)
        if self.title:
            headers["X-OpenRouter-Title"] = str(self.title)
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ImageVerificationError(f"image verifier HTTP {exc.code}: {body}") from exc
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ImageVerificationError("image verifier response must be a JSON object")
        if data.get("error"):
            raise ImageVerificationError(f"image verifier API error: {data['error']}")
        return data

    def _parse_response(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ImageVerificationError("image verifier response did not include choices")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            text = "".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("type") in {None, "text", "output_text"}
            )
        else:
            text = str(content)
        data = _extract_json_object(text)
        checks = data.get("checks", [])
        if not isinstance(checks, list):
            raise ImageVerificationError("image verifier JSON must include a checks list")
        return [item for item in checks if isinstance(item, dict)]


def build_image_verifier(config: dict[str, Any], workdir: Path) -> MockTextVerifier | OpenRouterVisionVerifier:
    verifier_config: dict[str, Any] = {}
    agent_config = config.get("agent", {})
    if isinstance(agent_config, dict) and isinstance(agent_config.get("verifier"), dict):
        verifier_config.update(agent_config["verifier"])

    evaluation = config.get("evaluation", {})
    legacy = evaluation.get("image_judge", {}) if isinstance(evaluation, dict) else {}
    if isinstance(legacy, dict):
        for key, value in legacy.items():
            verifier_config.setdefault(key, value)

    provider = verifier_config.get("provider")
    if not provider:
        image_backend = agent_config.get("image_backend", {}) if isinstance(agent_config, dict) else {}
        mode = str(image_backend.get("mode", "mock")).strip().lower()
        provider = "openrouter_vision" if mode == "live" else "mock_text"

    normalized = str(provider)
    if normalized in {"mock", "mock_text"}:
        return MockTextVerifier(verifier_config, workdir)
    if normalized in {"openrouter", "openrouter_vision"}:
        return OpenRouterVisionVerifier(verifier_config, workdir)
    raise ImageVerificationError(f"unsupported verifier provider: {normalized}")


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.replace("json\n", "", 1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ImageVerificationError("image verifier did not return a JSON object")
    payload = stripped[start : end + 1]
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ImageVerificationError("image verifier JSON payload must be an object")
    return data
