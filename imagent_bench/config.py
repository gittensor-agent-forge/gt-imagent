from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_sha256(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_suite_path(config: dict[str, Any], config_path: str | Path) -> Path:
    suite = config.get("suite", {})
    if "path" in suite:
        path = Path(suite["path"])
        if not path.is_absolute():
            path = Path(config_path).resolve().parent / path
        return path
    suite_id = suite.get("id")
    if not suite_id:
        raise ValueError("config.suite.id or config.suite.path is required")
    return REPO_ROOT / "imagent_bench" / "tasks" / suite_id / "suite.yaml"


def validate_config(config: dict[str, Any], config_path: str | Path) -> list[str]:
    errors: list[str] = []
    if "suite" not in config:
        errors.append("missing required key: suite")
    if "runtime" not in config:
        errors.append("missing required key: runtime")
    if "metrics" not in config:
        errors.append("missing required key: metrics")

    suite = config.get("suite", {})
    if not suite.get("id") and not suite.get("path"):
        errors.append("suite.id or suite.path is required")
    if not isinstance(suite.get("tasks", []), list):
        errors.append("suite.tasks must be a list")

    runtime = config.get("runtime", {})
    seeds = runtime.get("seeds", [])
    if not isinstance(seeds, list) or not seeds:
        errors.append("runtime.seeds must be a non-empty list")

    if not errors:
        suite_path = resolve_suite_path(config, config_path)
        if not suite_path.exists():
            errors.append(f"suite file does not exist: {suite_path}")
    return errors


def validate_result_schema(result: dict[str, Any]) -> list[str]:
    schema = load_json(REPO_ROOT / "imagent_bench" / "schemas" / "result.schema.json")
    validator = Draft202012Validator(schema)
    return [error.message for error in validator.iter_errors(result)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark configuration utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="Validate a benchmark config.")
    validate_parser.add_argument("config")
    args = parser.parse_args()

    if args.command == "validate":
        config = load_yaml(args.config)
        errors = validate_config(config, args.config)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.config}")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
