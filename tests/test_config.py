from __future__ import annotations

from pathlib import Path

from imagent_bench.config import load_yaml, validate_config


def test_local_smoke_config_is_valid() -> None:
    path = Path("configs/local-smoke.yaml")
    assert validate_config(load_yaml(path), path) == []


def test_openrouter_smoke_config_is_valid() -> None:
    path = Path("configs/openrouter-smoke.yaml")
    assert validate_config(load_yaml(path), path) == []


def test_api_gate_config_is_valid() -> None:
    path = Path("configs/api-gate.yaml")
    assert validate_config(load_yaml(path), path) == []


def test_pr_gate_config_is_valid() -> None:
    path = Path("configs/pr-gate.yaml")
    assert validate_config(load_yaml(path), path) == []


def test_config_rejects_unknown_selected_task(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
suite:
  id: ia_bench_v1
  tasks: [does_not_exist]
runtime:
  seeds: [1001]
metrics:
  primary: ia_score
""",
        encoding="utf-8",
    )

    errors = validate_config(load_yaml(path), path)

    assert "task 'does_not_exist' is not registered" in errors[0]


def test_config_rejects_invalid_task_case_schema(tmp_path: Path) -> None:
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "suite.yaml").write_text(
        """
id: custom_suite
version: 1
tasks:
  broken: cases/broken.jsonl
""",
        encoding="utf-8",
    )
    cases_dir = suite_dir / "cases"
    cases_dir.mkdir()
    (cases_dir / "broken.jsonl").write_text('{"id":"broken-case","capability":"plan","prompt":"missing expected"}\n', encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
suite:
  path: suite/suite.yaml
  tasks: [broken]
runtime:
  seeds: [1001]
metrics:
  primary: ia_score
""",
        encoding="utf-8",
    )

    errors = validate_config(load_yaml(config_path), config_path)

    assert "'expected' is a required property" in errors[0]
