from __future__ import annotations

from collections import defaultdict
from typing import Any


DEFAULT_IA_WEIGHTS = {
    "plan": 0.25,
    "reason": 0.25,
    "search": 0.25,
    "memory": 0.15,
    "feedback": 0.10,
}


def aggregate(
    case_results: list[dict[str, Any]],
    config: dict[str, Any],
    judge_cost_usd: float = 0.0,
) -> dict[str, Any]:
    total_cases = len(case_results)
    total_checks = 0
    passed_checks = 0
    passed_cases = 0
    valid_traces = 0
    context_gap_checks = 0
    passed_context_gap_checks = 0
    latencies: list[float] = []
    generation_cost = 0.0

    by_capability: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "cases": 0,
            "passed_cases": 0,
            "checks": 0,
            "passed_checks": 0,
            "pass_rate": 0.0,
            "checklist_accuracy": 0.0,
        }
    )

    for result in case_results:
        evaluation = result.get("evaluation", {})
        capability = str(result.get("capability", "unknown"))
        checks = evaluation.get("checks", [])
        case_passed = bool(evaluation.get("passed"))
        trace_valid = bool(evaluation.get("trace_valid"))

        passed_cases += int(case_passed)
        valid_traces += int(trace_valid)
        total_checks += len(checks)
        passed_checks += sum(1 for check in checks if check.get("passed"))
        context_gap_checks += sum(1 for check in checks if check.get("context_gap"))
        passed_context_gap_checks += sum(
            1 for check in checks if check.get("context_gap") and check.get("passed")
        )

        metadata = result.get("output", {}).get("metadata", {})
        if metadata.get("latency_ms") is not None:
            latencies.append(float(metadata["latency_ms"]))
        generation_cost += float(metadata.get("cost_usd", 0.0) or 0.0)

        bucket = by_capability[capability]
        bucket["cases"] += 1
        bucket["passed_cases"] += int(case_passed)
        bucket["checks"] += len(checks)
        bucket["passed_checks"] += sum(1 for check in checks if check.get("passed"))

    for bucket in by_capability.values():
        bucket["pass_rate"] = bucket["passed_cases"] / bucket["cases"] if bucket["cases"] else 0.0
        bucket["checklist_accuracy"] = bucket["passed_checks"] / bucket["checks"] if bucket["checks"] else 0.0

    weights = config.get("metrics", {}).get("ia_weights", DEFAULT_IA_WEIGHTS)
    weight_sum = sum(float(weight) for weight in weights.values()) or 1.0
    ia_score = 0.0
    for capability, weight in weights.items():
        capability_score = by_capability.get(capability, {}).get("checklist_accuracy", 0.0)
        ia_score += float(weight) * capability_score
    ia_score /= weight_sum

    return {
        "total_cases": total_cases,
        "completed_cases": total_cases,
        "total_checks": total_checks,
        "checklist_accuracy": passed_checks / total_checks if total_checks else 0.0,
        "pass_rate": passed_cases / total_cases if total_cases else 0.0,
        "ia_score": ia_score,
        "context_gap_score": passed_context_gap_checks / context_gap_checks if context_gap_checks else 0.0,
        "trace_validity": valid_traces / total_cases if total_cases else 0.0,
        "latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "cost_usd": generation_cost + judge_cost_usd,
        "generation_cost_usd": generation_cost,
        "judge_cost_usd": judge_cost_usd,
        "by_capability": dict(sorted(by_capability.items())),
    }
