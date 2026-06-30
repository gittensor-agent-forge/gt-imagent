from __future__ import annotations

from pathlib import Path

from imagent_bench.config import validate_result_schema
from imagent_bench.runner import run


def test_runner_writes_valid_results(tmp_path: Path) -> None:
    result = run(
        Path("configs/local-smoke.yaml").resolve(),
        "tests/fixtures/echo_agent",
        tmp_path,
    )

    assert validate_result_schema(result) == []
    assert result["metrics"]["failed_generations"] == 0
    assert result["metrics"]["total_cases"] == 6
    assert result["metrics"]["pass_rate"] == 1.0
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "summary.md").exists()
