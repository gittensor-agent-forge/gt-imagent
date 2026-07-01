from __future__ import annotations

from pathlib import Path

from imagent_bench.config import load_yaml, validate_config


def test_local_smoke_config_is_valid() -> None:
    path = Path("configs/local-smoke.yaml")
    assert validate_config(load_yaml(path), path) == []


def test_api_gate_openrouter_config_is_valid() -> None:
    path = Path("configs/api-gate-openrouter.yaml")
    assert validate_config(load_yaml(path), path) == []
