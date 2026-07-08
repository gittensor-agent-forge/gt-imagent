from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

DEFAULT_PUBLIC_SITE_URL = "https://tryimagent.com"
DEFAULT_IMAGE_MODEL = "google/gemini-3.1-flash-image"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_imagent_agent.py /path/to/request.json")

    request_path = Path(sys.argv[1]).resolve()
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request payload must be a JSON object")

    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")

    repository_path = Path(str(payload.get("repository_path", ""))).resolve()
    if not repository_path.exists():
        raise FileNotFoundError(f"imagent repository path does not exist: {repository_path}")
    if str(repository_path) not in sys.path:
        sys.path.insert(0, str(repository_path))

    from agent.agent import ImageAgent

    output_dir = Path(str(payload.get("output_dir", ""))).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    capability, allowed_tools = _capability(prompt)
    run_id = _safe_run_id(str(payload.get("run_id") or f"ui-{uuid.uuid4().hex[:12]}"))
    seed = int(payload.get("seed", 1001))
    background = str(payload.get("background", "auto")).strip()
    quality = str(payload.get("quality", "auto")).strip()
    public_site_url = _public_site_url(payload)
    image_parameters: dict[str, Any] = {}
    if background and background != "auto":
        image_parameters["background"] = background
    if quality and quality != "auto":
        image_parameters["quality"] = quality

    config = {
        "runtime": {
            "max_feedback_rounds": int(payload.get("max_feedback_rounds", 1)),
            "candidates_per_round": int(payload.get("candidates_per_round", 2)),
        },
        "agent": {
            "image_backend": {
                "mode": "live",
                "provider": "openrouter",
                "api_key_env": "OPENROUTER_API_KEY",
                "endpoint": "https://openrouter.ai/api/v1/images",
                "model": DEFAULT_IMAGE_MODEL,
                "resolution": "1K",
                "aspect_ratio": "1:1",
                "output_format": "png",
                "send_seed": False,
                "send_output_format": False,
                "timeout_seconds": 240,
                "referer": public_site_url,
                "title": "Imagent UI",
                "parameters": image_parameters,
            },
            "verifier": {
                "provider": "openrouter_vision",
                "api_key_env": "OPENROUTER_API_KEY",
                "model": "google/gemini-2.5-flash",
                "timeout_seconds": 180,
                "referer": public_site_url,
                "title": "Imagent UI Verifier",
            },
        },
        "evaluation": {
            "image_judge": {
                "provider": "openrouter_vision",
            }
        },
    }

    agent = ImageAgent()
    agent.setup(config, repository_path)
    result = agent.generate(
        {
            "run_id": run_id,
            "capability": capability,
            "prompt": prompt,
            "seed": seed,
            "allowed_tools": allowed_tools,
        },
        output_dir,
    )

    trace_path = Path(str(result["trace_path"]))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    response = {
        "image_path": str(result["image_path"]),
        "trace_path": str(trace_path),
        "metadata": result.get("metadata", {}),
        "agent_id": result.get("metadata", {}).get("agent_id"),
        "capability": capability,
        "candidate_count": int(result.get("metadata", {}).get("candidate_count", 0) or 0),
        "round_count": len(trace.get("feedback", [])),
        "selected_candidate_index": result.get("metadata", {}).get("selected_candidate_index"),
    }
    print(json.dumps(response))
    return 0


def _capability(prompt: str) -> tuple[str, list[str]]:
    if _looks_like_arithmetic(prompt):
        return "reason", ["reason"]
    if re.search(r"\b(exact|badge|validation|pass)\b", prompt, flags=re.IGNORECASE):
        return "feedback", ["feedback"]
    return "plan", ["plan"]


def _looks_like_arithmetic(prompt: str) -> bool:
    return re.search(r"(?:\d|\.\d)\s*[-+*/]\s*(?:\d|\.\d)", prompt) is not None


def _safe_run_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return cleaned or f"ui-{uuid.uuid4().hex[:12]}"


def _public_site_url(payload: dict[str, Any]) -> str:
    raw = str(payload.get("public_site_url") or DEFAULT_PUBLIC_SITE_URL).strip()
    if re.match(r"^https?://", raw):
        return raw.rstrip("/")
    return DEFAULT_PUBLIC_SITE_URL


if __name__ == "__main__":
    raise SystemExit(main())
