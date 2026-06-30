from __future__ import annotations

from pathlib import Path

import pytest

from imagent_bench.runner import run


def test_qwen_baseline_mock_runs_smoke_suite(tmp_path: Path) -> None:
    result = run(Path("configs/qwen-smoke.yaml").resolve(), "agents/qwen_baseline", tmp_path)

    assert result["agent"]["id"] == "qwen-baseline"
    assert result["metrics"]["failed_generations"] == 0
    assert result["metrics"]["total_cases"] == 6
    assert result["cases"][0]["output"]["metadata"]["provider"] == "mock"


def test_qwen_baseline_live_requires_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DASHSCOPE_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("DASHSCOPE_ENDPOINT", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    config_path = tmp_path / "live.yaml"
    config_path.write_text(
        """
suite:
  id: ia_bench_v1
  tasks: [plan]
  max_cases: 1
runtime:
  seeds: [1001]
  deterministic: false
  timeout_seconds_per_case: 60
agent:
  qwen_image:
    mode: live
metrics:
  primary: ia_score
""",
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="DASHSCOPE_WORKSPACE_ID|DASHSCOPE_ENDPOINT"):
        run(config_path.resolve(), "agents/qwen_baseline", tmp_path / "out")
