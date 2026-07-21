from __future__ import annotations

import ast
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from imagent_runtime.agent_runtime import AgentRuntime


DEFAULT_OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/images"
DEFAULT_OPENROUTER_MODEL = "google/gemini-3.1-flash-image"
DEFAULT_API_KEY_ENV = "OPENROUTER_API_KEY"


class OpenRouterImageError(RuntimeError):
    """Raised when OpenRouter cannot produce a usable image response."""


class BaseImageAgent:
    """Reference image agent that calls OpenRouter Gemini Image by default.

    Contributors should replace this class with stronger planning, critique, and
    regeneration logic while keeping the public setup/generate interface stable.
    """

    def setup(self, config: dict[str, Any], workdir: Path) -> None:
        self.config = config
        self.workdir = Path(workdir).expanduser().resolve()
        self.backend_config = _image_backend_config(config)
        self.runtime = AgentRuntime(self)

    def generate(self, case: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        if not hasattr(self, "runtime"):
            raise RuntimeError("agent.setup(config, workdir) must be called before generate()")
        return self.runtime.generate(case, output_dir)

    def _request_openrouter_image(self, prompt: str) -> tuple[bytes, str, dict[str, Any], dict[str, Any]]:
        api_key_env = str(self.backend_config.get("api_key_env", DEFAULT_API_KEY_ENV))
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise OpenRouterImageError(f"missing OpenRouter API key env var: {api_key_env}")

        payload = self._openrouter_payload(prompt)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self.backend_config.get("referer"):
            headers["HTTP-Referer"] = str(self.backend_config["referer"])
        if self.backend_config.get("title"):
            headers["X-OpenRouter-Title"] = str(self.backend_config["title"])

        request = urllib.request.Request(
            str(self.backend_config.get("endpoint", DEFAULT_OPENROUTER_ENDPOINT)),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=int(self.backend_config.get("timeout_seconds", 240))) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OpenRouterImageError(f"OpenRouter image HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise OpenRouterImageError(f"OpenRouter image request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise OpenRouterImageError("OpenRouter image response was not valid JSON") from exc

        image_bytes, media_type = _image_from_openrouter_response(response_payload, self.backend_config)
        return image_bytes, media_type, response_payload, payload

    def _openrouter_payload(self, prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": str(self.backend_config.get("model", DEFAULT_OPENROUTER_MODEL)),
            "prompt": prompt,
            "n": int(self.backend_config.get("n", 1)),
        }
        parameters = self.backend_config.get("parameters")
        if isinstance(parameters, dict):
            for key, value in parameters.items():
                _set_payload_parameter(payload, str(key), value)

        for key in (
            "resolution",
            "aspect_ratio",
            "size",
            "quality",
            "output_format",
            "background",
            "output_compression",
            "seed",
            "input_references",
            "provider",
        ):
            if key not in self.backend_config:
                continue
            if key == "seed" and self.backend_config.get("send_seed") is False:
                continue
            if key == "output_format" and self.backend_config.get("send_output_format") is False:
                continue
            _set_payload_parameter(payload, key, self.backend_config[key])
        return payload

    def _build_context(self, case: dict[str, Any]) -> dict[str, Any]:
        prompt = str(case.get("prompt", ""))
        memory = case.get("memory") if isinstance(case.get("memory"), dict) else {}
        assets = self._read_assets(case.get("assets", []))
        facts = self._read_search_facts(case.get("search_snapshots", []), prompt)
        title = (
            str(memory.get("preferred_label") or "").strip()
            or self._title_from_prompt(prompt)
            or assets.get("title")
            or ("Image-Agent" if facts else "")
        )
        sections = self._sections_from_prompt(prompt) or assets.get("sections", [])
        required_text = [title, *sections, *assets.get("required_text", [])]
        if "reason" in (case.get("allowed_tools") or []):
            display = self._reasoning_display(prompt)
            if display:
                required_text.extend([display["answer"], display["display"]])
        if "PASS" in prompt.upper():
            required_text.append("PASS")
        if facts:
            required_text.extend(["Image-Agent", "context gap"])

        return {
            "capability": str(case.get("capability", "")),
            "memory": {key: str(value) for key, value in memory.items() if value is not None},
            "title": title,
            "sections": _dedupe(sections),
            "required_text": _dedupe(required_text),
            "facts": facts[:4],
        }

    def _build_generation_prompt(self, case: dict[str, Any], context: dict[str, Any]) -> str:
        prompt = str(case.get("prompt", "")).strip()
        lines = [
            "Create one high-quality image that follows the user request exactly.",
            f"User request: {prompt}",
            "Reasoning plan: identify required content, preserve visible text, compose a clear layout, then render the final image.",
        ]
        if context.get("title"):
            lines.append(f"Primary title or label: {context['title']}")
        if context.get("sections"):
            lines.append(f"Required sections: {', '.join(context['sections'])}")
        if context.get("required_text"):
            lines.append(f"Text that must be visibly correct: {', '.join(context['required_text'])}")
        if context.get("facts"):
            lines.append(f"Grounding facts to incorporate where relevant: {'; '.join(context['facts'])}")
        if context.get("memory"):
            memory_text = "; ".join(f"{key}: {value}" for key, value in context["memory"].items())
            lines.append(f"User memory/preferences: {memory_text}")
        lines.append("Avoid misspelled text, missing labels, clutter, and contradictions.")
        return "\n".join(line for line in lines if line)

    def _read_assets(self, values: Any) -> dict[str, Any]:
        json_paths = [
            path
            for path in (self._case_path(value) for value in values or [])
            if path.suffix.lower() == ".json"
        ]
        merged: dict[str, Any] = {"title": "", "sections": [], "required_text": []}
        for path in sorted(json_paths, key=lambda item: item.name):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            merged = {
                "title": str(data.get("title") or "") or merged["title"],
                "sections": [str(item) for item in data.get("sections", []) if str(item).strip()] or merged["sections"],
                "required_text": [str(item) for item in data.get("required_text", []) if str(item).strip()]
                or merged["required_text"],
            }
        return merged

    def _read_search_facts(self, values: Any, prompt: str) -> list[str]:
        prompt_words = set(re.findall(r"[a-z0-9]+", prompt.lower()))
        facts: list[str] = []
        for value in values or []:
            path = self._case_path(value)
            if path.suffix.lower() != ".json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for fact in data.get("facts", []) if isinstance(data, dict) else []:
                text = str(fact)
                fact_words = set(re.findall(r"[a-z0-9]+", text.lower()))
                if prompt_words & fact_words:
                    facts.append(text)
        return _dedupe(facts)

    def _case_path(self, value: Any) -> Path:
        path = Path(str(value)).expanduser()
        candidate = path if path.is_absolute() else self.workdir / path
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(self.workdir)
        return resolved

    def _title_from_prompt(self, prompt: str) -> str:
        quoted = re.search(r'\btitled\s+["\']([^"\']+)["\']', prompt, re.IGNORECASE)
        if quoted:
            return quoted.group(1).strip()
        match = re.search(r"\btitled\s+(.+?)(?:\s+with\b|\.|$)", prompt, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _sections_from_prompt(self, prompt: str) -> list[str]:
        match = re.search(r"\bsections?\s+(.+?)(?:\.|$)", prompt, re.IGNORECASE)
        if not match:
            return []
        raw = re.sub(r"\band\b", ",", match.group(1), flags=re.IGNORECASE)
        return [part.strip(" .") for part in re.split(r"[,;/|]+", raw) if part.strip(" .")]

    def _reasoning_display(self, prompt: str) -> dict[str, str] | None:
        expression = _extract_expression(prompt)
        if not expression:
            return None
        try:
            value = _safe_eval(expression)
        except (ValueError, ZeroDivisionError):
            return None
        answer = _format_number(value)
        return {"answer": answer, "display": f"{expression} = {answer}"}


def _image_backend_config(config: dict[str, Any]) -> dict[str, Any]:
    agent_config = config.get("agent") if isinstance(config, dict) else {}
    agent_config = agent_config if isinstance(agent_config, dict) else {}
    backend_config = agent_config.get("image_backend")
    backend_config = dict(backend_config) if isinstance(backend_config, dict) else {}
    backend_config.setdefault("provider", "openrouter")
    backend_config.setdefault("model", DEFAULT_OPENROUTER_MODEL)
    backend_config.setdefault("endpoint", DEFAULT_OPENROUTER_ENDPOINT)
    backend_config.setdefault("api_key_env", DEFAULT_API_KEY_ENV)
    return backend_config


def _image_from_openrouter_response(
    response_payload: dict[str, Any], backend_config: dict[str, Any]
) -> tuple[bytes, str]:
    data = response_payload.get("data")
    if not isinstance(data, list) or not data:
        raise OpenRouterImageError("OpenRouter image response did not include image data")
    first_image = data[0]
    if not isinstance(first_image, dict):
        raise OpenRouterImageError("OpenRouter image response data item was not an object")

    media_type = str(first_image.get("media_type") or _media_type_from_format(backend_config.get("output_format")) or "image/png")
    if isinstance(first_image.get("b64_json"), str) and first_image["b64_json"].strip():
        try:
            return base64.b64decode(first_image["b64_json"]), media_type
        except ValueError as exc:
            raise OpenRouterImageError("OpenRouter image response included invalid base64 image bytes") from exc

    url = _image_url_from_response_item(first_image)
    if url:
        return _image_bytes_from_url(url, media_type, backend_config)

    raise OpenRouterImageError("OpenRouter image response did not include b64_json or url")


def _image_url_from_response_item(item: dict[str, Any]) -> str:
    if isinstance(item.get("url"), str):
        return str(item["url"])
    image_url = item.get("image_url")
    if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
        return str(image_url["url"])
    return ""


def _image_bytes_from_url(url: str, fallback_media_type: str, backend_config: dict[str, Any]) -> tuple[bytes, str]:
    if url.startswith("data:"):
        header, _, encoded = url.partition(",")
        media_type = header.removeprefix("data:").split(";", 1)[0] or fallback_media_type
        try:
            return base64.b64decode(encoded), media_type
        except ValueError as exc:
            raise OpenRouterImageError("OpenRouter image data URL included invalid base64 bytes") from exc

    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise OpenRouterImageError(f"OpenRouter image URL scheme is not allowed: {scheme or url!r}")

    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=int(backend_config.get("timeout_seconds", 240))) as response:
            media_type = response.headers.get_content_type() if hasattr(response, "headers") else fallback_media_type
            return response.read(), media_type or fallback_media_type
    except urllib.error.URLError as exc:
        raise OpenRouterImageError(f"failed to download OpenRouter image URL: {exc}") from exc


def _set_payload_parameter(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is None or value == "":
        return
    if key in {"background", "aspect_ratio"} and value == "auto":
        return
    payload[key] = value


def _media_type_from_format(value: Any) -> str:
    output_format = str(value or "").strip().lower()
    if output_format in {"jpg", "jpeg"}:
        return "image/jpeg"
    if output_format in {"png", "webp", "gif"}:
        return f"image/{output_format}"
    return ""


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _extract_expression(prompt: str) -> str:
    number = r"(?:\d+(?:\.\d*)?|\.\d+)"
    for match in re.finditer(rf"(?<![A-Za-z0-9_.])(?:{number}|\()[0-9()\s+\-*/.]*", prompt):
        candidate = match.group(0).strip().rstrip(".")
        if any(char.isdigit() for char in candidate) and any(op in candidate for op in "+-*/"):
            try:
                ast.parse(candidate, mode="eval")
            except SyntaxError:
                continue
            return candidate
    return ""


def _safe_eval(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
        if isinstance(node, ast.BinOp):
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
        raise ValueError(f"unsupported expression: {type(node).__name__}")

    return visit(tree)


def _format_number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.6f}".rstrip("0").rstrip(".")


ImageAgent = BaseImageAgent
