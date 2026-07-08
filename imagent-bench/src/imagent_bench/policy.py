from __future__ import annotations

from typing import Any

from .models import PolicyResult


def evaluate_policy(
    policy: dict[str, Any],
    *,
    overall_score: float,
    failed_case_count: int,
    cost_usd: float,
    latency_p95_ms: float,
    ranking: dict[str, Any] | None = None,
) -> PolicyResult:
    reasons: list[str] = []
    minimum_score = float(policy.get("minimum_score", 0.0))
    max_failed_cases = int(policy.get("max_failed_cases", 0))
    max_cost_usd = float(policy.get("max_cost_usd", float("inf")))
    max_latency_p95_ms = float(policy.get("max_latency_p95_ms", float("inf")))

    if overall_score < minimum_score:
        reasons.append(f"overall score {overall_score:.2f} is below required {minimum_score:.2f}")
    if failed_case_count > max_failed_cases:
        reasons.append(f"failed cases {failed_case_count} exceeds allowed {max_failed_cases}")
    if cost_usd > max_cost_usd:
        reasons.append(f"cost ${cost_usd:.6f} exceeds allowed ${max_cost_usd:.6f}")
    if latency_p95_ms > max_latency_p95_ms:
        reasons.append(f"latency p95 {latency_p95_ms:.3f} ms exceeds allowed {max_latency_p95_ms:.3f} ms")
    if ranking and ranking.get("baseline_score") is not None and not ranking.get("merge_eligible"):
        delta = float(ranking.get("delta", 0.0) or 0.0)
        required = float(ranking.get("minimum_merge_improvement", 0.0) or 0.0)
        reasons.append(f"score improvement {delta:.2f} is below required {required:.2f}")

    return PolicyResult(
        passed=not reasons,
        reasons=reasons,
        thresholds={
            "minimum_score": minimum_score,
            "max_failed_cases": max_failed_cases,
            "max_cost_usd": max_cost_usd,
            "max_latency_p95_ms": max_latency_p95_ms,
            "minimum_merge_improvement": ranking.get("minimum_merge_improvement") if ranking else None,
        },
    )
