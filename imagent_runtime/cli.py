from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


DEFAULT_AGENT = "agent.agent:ImageAgent"


def main(argv: Sequence[str] | None = None) -> int:
    defaults = _run_defaults()
    args = _parser(defaults).parse_args(argv)
    case = _case_from_args(args)
    config = _config_from_args(args)
    agent_class = _load_object(args.agent)
    agent = agent_class()
    agent.setup(config, Path(args.workdir).expanduser().resolve())
    result = agent.generate(case, Path(args.output_dir).expanduser().resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _parser(defaults: dict[str, str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imagent",
        description="Run an Imagent agent locally against OpenRouter Gemini Image.",
    )
    parser.add_argument("prompt_text", nargs="*", help="Prompt text. Example: imagent \"Create a benchmark badge.\"")
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="Agent class import path, e.g. agent.agent:ImageAgent.")
    parser.add_argument("--case-json", help="Path to a JSON object containing the agent case payload.")
    parser.add_argument("--config-json", help="Path to a JSON object containing the agent config.")
    parser.add_argument("--prompt", help="Deprecated prompt flag. Prefer positional prompt text.")
    parser.add_argument("--run-id", default=defaults["run_id"], help="Filename-safe run id. Defaults to UTC datetime.")
    parser.add_argument("--capability", default="plan", help="Case capability label.")
    parser.add_argument(
        "--allowed-tool",
        action="append",
        dest="allowed_tools",
        help="Allowed tool name. Can be repeated. Defaults to the capability.",
    )
    parser.add_argument("--workdir", default=".", help="Workdir used for resolving case assets.")
    parser.add_argument(
        "--output-dir",
        default=defaults["output_dir"],
        help="Directory for generated image and trace artifacts. Defaults to results/<UTC datetime>.",
    )
    parser.add_argument("--model", default="", help="Override OpenRouter image model in the generated config.")
    parser.add_argument("--resolution", default="1K", help="OpenRouter image resolution.")
    parser.add_argument("--aspect-ratio", default="1:1", help="OpenRouter image aspect ratio.")
    parser.add_argument("--referer", default="https://tryimagent.com", help="OpenRouter HTTP-Referer attribution header.")
    parser.add_argument("--title", default="Imagent CLI", help="OpenRouter X-OpenRouter-Title attribution header.")
    return parser


def _run_defaults() -> dict[str, str]:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return {
        "run_id": timestamp,
        "output_dir": f"results/{timestamp}",
    }


def _case_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.case_json:
        payload = _read_json_object(Path(args.case_json))
        payload.setdefault("run_id", args.run_id)
        return payload
    prompt = _prompt_from_args(args)
    if not prompt:
        raise SystemExit('prompt is required, e.g. imagent "Create a benchmark badge."')
    return {
        "run_id": args.run_id,
        "capability": args.capability,
        "prompt": prompt,
        "allowed_tools": args.allowed_tools or [args.capability],
    }


def _prompt_from_args(args: argparse.Namespace) -> str:
    positional_prompt = " ".join(args.prompt_text or []).strip()
    flag_prompt = str(args.prompt or "").strip()
    if positional_prompt and flag_prompt:
        raise SystemExit("pass prompt either positionally or with --prompt, not both")
    return positional_prompt or flag_prompt


def _config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    config = _read_json_object(Path(args.config_json)) if args.config_json else {}
    agent_config = config.setdefault("agent", {})
    if not isinstance(agent_config, dict):
        raise SystemExit("config.agent must be a JSON object")
    backend = agent_config.setdefault("image_backend", {})
    if not isinstance(backend, dict):
        raise SystemExit("config.agent.image_backend must be a JSON object")
    backend.setdefault("mode", "live")
    backend.setdefault("provider", "openrouter")
    backend.setdefault("api_key_env", "OPENROUTER_API_KEY")
    backend.setdefault("endpoint", "https://openrouter.ai/api/v1/images")
    if args.model:
        backend["model"] = args.model
    else:
        backend.setdefault("model", "google/gemini-3.1-flash-image")
    backend["resolution"] = args.resolution
    backend["aspect_ratio"] = args.aspect_ratio
    backend.setdefault("output_format", "png")
    backend.setdefault("send_output_format", False)
    backend.setdefault("send_seed", False)
    backend.setdefault("timeout_seconds", 240)
    backend["referer"] = args.referer
    backend["title"] = args.title
    return config


def _load_object(import_path: str) -> Any:
    module_name, separator, object_name = import_path.partition(":")
    if not separator or not module_name or not object_name:
        raise SystemExit("--agent must use module:object syntax")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, object_name)
    except AttributeError as exc:
        raise SystemExit(f"agent object not found: {import_path}") from exc


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"failed to read JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON file must contain an object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
