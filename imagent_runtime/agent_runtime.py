from __future__ import annotations

import json
import mimetypes
import re
import time
from pathlib import Path
from typing import Any


_IMAGE_EXTENSION_BY_MEDIA_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


class AgentRuntime:
    """Stable runtime that executes one image-agent trajectory.

    This module is intentionally outside `agent/agent.py`. Contributor PRs can
    experiment with the reference agent without changing the runtime contract.
    """

    id = "base-agent-runtime"
    version = "0.1"
    trajectory = [
        "understand_user_intent",
        "collect_available_context",
        "construct_generation_prompt",
        "generate_image_with_openrouter",
        "persist_artifacts",
    ]

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    def generate(self, case: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        started = time.perf_counter()
        images_dir, traces_dir = self._prepare_output_dirs(output_dir)

        run_id = _safe_run_id(case.get("run_id") or case.get("id") or "case")
        context = self.agent._build_context(case)
        generation_prompt = self.agent._build_generation_prompt(case, context)

        image_bytes, media_type, response_payload, request_payload = self.agent._request_openrouter_image(
            generation_prompt
        )
        image_path = images_dir / f"{run_id}{_extension_for_media_type(media_type)}"
        trace_path = traces_dir / f"{run_id}.json"
        image_path.write_bytes(image_bytes)

        usage = response_payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        model = str(response_payload.get("model") or request_payload["model"])
        trace = self._trace(
            case=case,
            context=context,
            generation_prompt=generation_prompt,
            media_type=media_type,
            model=model,
            request_payload=request_payload,
            response_payload=response_payload,
            usage=usage,
        )
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        return {
            "image_path": str(image_path),
            "trace_path": str(trace_path),
            "metadata": {
                "agent_id": "base-openrouter-gemini-agent",
                "runtime_id": self.id,
                "provider": "openrouter",
                "model": model,
                "media_type": media_type,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "cost_usd": _float_or_zero(usage.get("cost")),
            },
        }

    def _prepare_output_dirs(self, output_dir: Path) -> tuple[Path, Path]:
        output_dir = Path(output_dir)
        images_dir = output_dir / "images"
        traces_dir = output_dir / "traces"
        images_dir.mkdir(parents=True, exist_ok=True)
        traces_dir.mkdir(parents=True, exist_ok=True)
        return images_dir, traces_dir

    def _trace(
        self,
        *,
        case: dict[str, Any],
        context: dict[str, Any],
        generation_prompt: str,
        media_type: str,
        model: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        usage: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "agent": "base-openrouter-gemini",
            "runtime": {
                "id": self.id,
                "version": self.version,
                "steps": self.trajectory,
            },
            "model": model,
            "provider": "openrouter",
            "user_prompt": str(case.get("prompt", "")),
            "generation_prompt": generation_prompt,
            "context": context,
            "trajectory": self.trajectory,
            "request": _trace_request_summary(request_payload, self.agent.backend_config),
            "response": {
                "created": response_payload.get("created"),
                "media_type": media_type,
                "usage": usage,
            },
        }


def _safe_run_id(value: Any) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", text):
        raise ValueError("run_id must be filename safe")
    return text


def _extension_for_media_type(media_type: str) -> str:
    normalized = media_type.split(";", 1)[0].strip().lower()
    if normalized in _IMAGE_EXTENSION_BY_MEDIA_TYPE:
        return _IMAGE_EXTENSION_BY_MEDIA_TYPE[normalized]
    guessed = mimetypes.guess_extension(normalized, strict=False)
    return ".jpg" if guessed == ".jpe" else guessed or ".png"


def _trace_request_summary(payload: dict[str, Any], backend_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "endpoint": str(backend_config.get("endpoint", "https://openrouter.ai/api/v1/images")),
        "model": payload.get("model"),
        "parameters": {key: value for key, value in payload.items() if key not in {"prompt", "input_references"}},
    }


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
