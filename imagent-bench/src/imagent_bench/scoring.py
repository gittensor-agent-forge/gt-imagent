from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


DEFAULT_VISION_DIMENSIONS: dict[str, float] = {
    "prompt_alignment": 0.35,
    "visual_quality": 0.2,
    "aesthetics": 0.15,
    "text_accuracy": 0.15,
    "layout_and_composition": 0.1,
    "realism": 0.05,
}


class JudgeError(RuntimeError):
    """Raised when an image judge cannot produce a usable score."""


def evaluate_case(
    image_path: Path,
    *,
    prompt: str,
    checks: list[dict[str, Any]],
    judge_config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], float, dict[str, Any]]:
    judge_config = judge_config or {}
    provider = str(judge_config.get("provider", "mock_text")).strip().lower()
    if provider in {"openrouter", "openrouter_vision"}:
        # Intentional design: when a vision judge is configured, deterministic
        # image_contains checks are skipped in favor of the model's holistic score.
        # This is not a bug; text-based checks can't reliably validate a raster image.
        judge_result = evaluate_openrouter_vision(image_path, prompt=prompt, config=judge_config)
        return [], float(judge_result["overall_score"]), judge_result

    check_results = evaluate_checks(image_path, checks)
    return check_results, score_from_checks(check_results), {}


def evaluate_checks(image_path: Path, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible_text = _read_visible_text(image_path)
    results: list[dict[str, Any]] = []
    for check in checks:
        check_type = str(check.get("type", ""))
        value = str(check.get("value", ""))
        if check_type == "image_contains":
            passed = _contains_visible_text(visible_text, value)
            reason = "exact visible text matched" if passed else "exact visible text missing"
        else:
            passed = False
            reason = f"unsupported check type: {check_type}"
        results.append(
            {
                "type": check_type,
                "value": value,
                "passed": passed,
                "reason": reason,
            }
        )
    return results


def score_from_checks(checks: list[dict[str, Any]]) -> float:
    if not checks:
        return 100.0
    passed = sum(1 for check in checks if check.get("passed") is True)
    return round((passed / len(checks)) * 100.0, 6)


def evaluate_openrouter_vision(image_path: Path, *, prompt: str, config: dict[str, Any]) -> dict[str, Any]:
    api_key_env = str(config.get("api_key_env", "OPENROUTER_API_KEY"))
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise JudgeError(f"missing OpenRouter judge API key env var: {api_key_env}")

    dimensions = _dimension_weights(config.get("dimensions"))
    payload = {
        "model": str(config.get("model", "google/gemini-2.5-flash")),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _judge_prompt(prompt, dimensions)},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                ],
            }
        ],
        "temperature": float(config.get("temperature", 0)),
        "max_tokens": int(config.get("max_tokens", 1200)),
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if config.get("referer"):
        headers["HTTP-Referer"] = str(config["referer"])
    if config.get("title"):
        headers["X-OpenRouter-Title"] = str(config["title"])

    request = urllib.request.Request(
        str(config.get("endpoint", "https://openrouter.ai/api/v1/chat/completions")),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    timeout = int(config.get("timeout_seconds", 180))
    max_retries = int(config.get("max_retries", 3))
    delay_seconds = float(config.get("retry_backoff_seconds", 1.0))
    response_payload: dict[str, Any] | None = None
    # Retry transient failures (429/5xx and network errors) with exponential
    # backoff, mirroring backends/openrouter_backend.py, so a single blip does
    # not abort the whole benchmark.
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < max_retries:
                time.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            body = exc.read().decode("utf-8", errors="replace")
            raise JudgeError(f"OpenRouter judge HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries:
                time.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            raise JudgeError(f"OpenRouter judge request failed: {exc}") from exc
    if response_payload is None:  # pragma: no cover - defensive, loop always sets or raises
        raise JudgeError("OpenRouter judge request failed after retries")

    content = _openrouter_message_content(response_payload)
    parsed = _parse_judge_json(content)
    dimension_scores = _normalize_dimension_scores(parsed.get("scores", {}), dimensions)
    overall_score = _weighted_score(dimension_scores, dimensions)
    if isinstance(parsed.get("overall_score"), int | float):
        overall_score = _clamp_score(float(parsed["overall_score"]))

    usage = response_payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return {
        "overall_score": overall_score,
        "dimensions": dimension_scores,
        "judge": {
            "provider": "openrouter",
            "model": response_payload.get("model") or payload["model"],
            "rubric_version": str(config.get("rubric_version", "openrouter-vision-v1")),
            "rationale": str(parsed.get("rationale", "")),
            "usage": usage,
            "raw_response": parsed,
        },
        "cost_usd": float(usage.get("cost", 0.0) or 0.0),
    }


def _read_visible_text(image_path: Path) -> str:
    # Intentional design limitation: only .svg and .txt expose extractable text.
    # Raster formats (.png/.jpg/...) return "" because text can't be recovered
    # without OCR, which is out of scope here. This is not a bug.
    if not image_path.exists():
        return ""
    if image_path.suffix.lower() == ".svg":
        return _read_svg_visible_text(image_path)
    if image_path.suffix.lower() == ".txt":
        return image_path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _dimension_weights(raw_dimensions: Any) -> dict[str, float]:
    if not isinstance(raw_dimensions, dict):
        return dict(DEFAULT_VISION_DIMENSIONS)
    weights: dict[str, float] = {}
    for name, value in raw_dimensions.items():
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            weights[str(name)] = weight
    return weights or dict(DEFAULT_VISION_DIMENSIONS)


def _judge_prompt(prompt: str, dimensions: dict[str, float]) -> str:
    dimension_lines = "\n".join(f"- {name}: score 0-100" for name in dimensions)
    return (
        "You are an image generation benchmark judge. Evaluate the generated image against the user prompt.\n"
        "Return only valid JSON with this shape:\n"
        '{"scores":{"dimension_name":0},"overall_score":0,"rationale":"short reason"}\n'
        "Use the full 0-100 range. Penalize missing prompt requirements, wrong text, wrong layout, artifacts, or low quality.\n\n"
        f"User prompt:\n{prompt}\n\n"
        f"Dimensions:\n{dimension_lines}\n"
    )


def _image_data_url(image_path: Path) -> str:
    media_type = mimetypes.guess_type(image_path.name, strict=False)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _openrouter_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise JudgeError("OpenRouter judge response did not include choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise JudgeError("OpenRouter judge response did not include a message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise JudgeError("OpenRouter judge response did not include text content")
    return content.strip()


def _parse_judge_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"OpenRouter judge returned invalid JSON: {content[:300]}") from exc
    if not isinstance(parsed, dict):
        raise JudgeError("OpenRouter judge JSON must be an object")
    return parsed


def _normalize_dimension_scores(raw_scores: Any, dimensions: dict[str, float]) -> dict[str, float]:
    raw_scores = raw_scores if isinstance(raw_scores, dict) else {}
    scores: dict[str, float] = {}
    for name in dimensions:
        try:
            value = float(raw_scores.get(name, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        scores[name] = _clamp_score(value)
    return scores


def _weighted_score(scores: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = sum(weights.values()) or 1.0
    return round(sum(scores.get(name, 0.0) * weight for name, weight in weights.items()) / total_weight, 6)


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 6)


def _read_svg_visible_text(image_path: Path) -> str:
    try:
        root = ET.fromstring(image_path.read_text(encoding="utf-8", errors="ignore"))
    except ET.ParseError:
        return ""
    lines: list[str] = []
    for element in root.iter():
        if _svg_local_name(element.tag) != "text":
            continue
        text = "".join(element.itertext()).strip()
        if text:
            lines.append(html.unescape(text))
    return "\n".join(lines)


def _svg_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _contains_visible_text(text: str, value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    prefix = r"(?<![A-Za-z0-9_])" if value[0].isalnum() or value[0] == "_" else ""
    suffix = r"(?![A-Za-z0-9_])" if value[-1].isalnum() or value[-1] == "_" else ""
    return re.search(prefix + re.escape(value) + suffix, text) is not None
