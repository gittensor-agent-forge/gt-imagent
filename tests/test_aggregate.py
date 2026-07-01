from __future__ import annotations

import pytest

from imagent_bench.metrics.aggregate import aggregate


def _case(cost: float | None) -> dict:
    metadata: dict = {"latency_ms": 1.0}
    if cost is not None:
        metadata["cost_usd"] = cost
    return {
        "capability": "plan",
        "evaluation": {"checks": [], "passed": True, "trace_valid": True},
        "output": {"metadata": metadata},
    }


def test_aggregate_sums_generation_and_judge_cost() -> None:
    metrics = aggregate([_case(0.01), _case(0.02)], {}, judge_cost_usd=0.05)

    assert metrics["generation_cost_usd"] == pytest.approx(0.03)
    assert metrics["judge_cost_usd"] == pytest.approx(0.05)
    assert metrics["cost_usd"] == pytest.approx(0.08)


def test_aggregate_cost_defaults_to_zero() -> None:
    metrics = aggregate([_case(None)], {})

    assert metrics["generation_cost_usd"] == 0.0
    assert metrics["judge_cost_usd"] == 0.0
    assert metrics["cost_usd"] == 0.0
