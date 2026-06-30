from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from imagent_bench.config import load_yaml


@dataclass(frozen=True)
class AgentManifest:
    id: str
    name: str
    entrypoint: str
    version: str
    path: Path
    raw: dict[str, Any]


def load_manifest(agent: str | Path) -> AgentManifest:
    manifest_path = Path(agent).resolve()
    if manifest_path.is_dir():
        manifest_path = manifest_path / "agent.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Agent manifest not found: {manifest_path}")

    raw = load_yaml(manifest_path)
    missing = [key for key in ("id", "entrypoint") if key not in raw]
    if missing:
        raise ValueError(f"{manifest_path} missing required keys: {', '.join(missing)}")
    return AgentManifest(
        id=str(raw["id"]),
        name=str(raw.get("name", raw["id"])),
        entrypoint=str(raw["entrypoint"]),
        version=str(raw.get("version", "0.0.0")),
        path=manifest_path.parent,
        raw=raw,
    )


def load_agent_class(manifest: AgentManifest):
    module_name, sep, class_name = manifest.entrypoint.partition(":")
    if not sep:
        raise ValueError(f"Invalid entrypoint {manifest.entrypoint!r}; expected module:Class")

    path_text = str(manifest.path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

    module = importlib.import_module(module_name)
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise AttributeError(f"{manifest.entrypoint} does not define {class_name}") from exc
