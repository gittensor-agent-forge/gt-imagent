from __future__ import annotations

import copy
import json
from pathlib import Path

from imagent_bench.compare import compare
from imagent_bench.runner import run


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_compare_accepts_matching_results_with_no_regression_rule(tmp_path: Path) -> None:
    result = run(Path("configs/qwen-smoke.yaml").resolve(), "agents/qwen_baseline", tmp_path / "base")
    baseline_path = tmp_path / "base" / "results.json"
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, result)

    config_path = tmp_path / "compare.yaml"
    config_path.write_text(
        """
acceptance:
  require_schema_valid: true
  require_all_cases_completed: true
  rules:
    - metric: ia_score
      mode: higher_is_better
      max_regression_vs_baseline: 0.0
""",
        encoding="utf-8",
    )

    comparison = compare(config_path, baseline_path, candidate_path, tmp_path / "comparison.json")

    assert comparison["accepted"] is True


def test_compare_rejects_missing_required_improvement(tmp_path: Path) -> None:
    result = run(Path("configs/qwen-smoke.yaml").resolve(), "agents/qwen_baseline", tmp_path / "base")
    baseline_path = tmp_path / "base" / "results.json"
    candidate = copy.deepcopy(result)
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, candidate)

    config_path = tmp_path / "compare.yaml"
    config_path.write_text(
        """
acceptance:
  require_schema_valid: true
  require_all_cases_completed: true
  rules:
    - metric: ia_score
      mode: higher_is_better
      min_delta_vs_baseline: 0.01
""",
        encoding="utf-8",
    )

    comparison = compare(config_path, baseline_path, candidate_path, tmp_path / "comparison.json")

    assert comparison["accepted"] is False
    assert "rule failed for ia_score" in comparison["failures"][0]


def test_compare_rejects_mismatched_suite_hash(tmp_path: Path) -> None:
    result = run(Path("configs/local-smoke.yaml").resolve(), "tests/fixtures/echo_agent", tmp_path / "base")
    baseline_path = tmp_path / "base" / "results.json"
    candidate = copy.deepcopy(result)
    candidate["suite"]["hash"] = "not-the-same-suite"
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, candidate)

    config_path = tmp_path / "compare.yaml"
    config_path.write_text(
        """
acceptance:
  require_schema_valid: true
  require_all_cases_completed: true
  rules:
    - metric: ia_score
      mode: higher_is_better
      max_regression_vs_baseline: 0.0
""",
        encoding="utf-8",
    )

    comparison = compare(config_path, baseline_path, candidate_path, tmp_path / "comparison.json")

    assert comparison["accepted"] is False
    assert "suite.hash mismatch" in comparison["failures"][0]


def test_compare_rejects_case_matrix_mismatch(tmp_path: Path) -> None:
    result = run(Path("configs/local-smoke.yaml").resolve(), "tests/fixtures/echo_agent", tmp_path / "base")
    baseline_path = tmp_path / "base" / "results.json"
    candidate = copy.deepcopy(result)
    candidate["cases"] = candidate["cases"][:-1]
    candidate["metrics"]["total_cases"] = len(candidate["cases"])
    candidate["metrics"]["completed_cases"] = len(candidate["cases"])
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, candidate)

    config_path = tmp_path / "compare.yaml"
    config_path.write_text(
        """
acceptance:
  require_schema_valid: true
  require_all_cases_completed: true
  rules:
    - metric: ia_score
      mode: higher_is_better
      max_regression_vs_baseline: 0.0
""",
        encoding="utf-8",
    )

    comparison = compare(config_path, baseline_path, candidate_path, tmp_path / "comparison.json")

    assert comparison["accepted"] is False
    assert "case matrix mismatch" in comparison["failures"][0]
