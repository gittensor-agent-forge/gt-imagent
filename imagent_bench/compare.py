from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from imagent_bench.config import load_yaml, validate_result_schema


def _load_result(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _metric(result: dict[str, Any], name: str) -> float:
    metrics = result.get("metrics", {})
    if name not in metrics:
        raise KeyError(f"metric {name!r} not found in result")
    return float(metrics[name])


def _evaluate_rule(rule: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    metric = rule["metric"]
    mode = rule["mode"]
    base = _metric(baseline, metric)
    cand = _metric(candidate, metric)
    passed = True
    reasons: list[str] = []

    if "min_absolute" in rule:
        ok = cand >= float(rule["min_absolute"])
        passed = passed and ok
        reasons.append(f"{cand:.6f} >= min_absolute {float(rule['min_absolute']):.6f}: {ok}")

    if "max_absolute" in rule:
        ok = cand <= float(rule["max_absolute"])
        passed = passed and ok
        reasons.append(f"{cand:.6f} <= max_absolute {float(rule['max_absolute']):.6f}: {ok}")

    if "min_delta_vs_baseline" in rule:
        delta = cand - base if mode == "higher_is_better" else base - cand
        ok = delta >= float(rule["min_delta_vs_baseline"])
        passed = passed and ok
        reasons.append(f"delta {delta:.6f} >= {float(rule['min_delta_vs_baseline']):.6f}: {ok}")

    if "max_regression_vs_baseline" in rule:
        regression = base - cand if mode == "higher_is_better" else cand - base
        ok = regression <= float(rule["max_regression_vs_baseline"])
        passed = passed and ok
        reasons.append(f"regression {regression:.6f} <= {float(rule['max_regression_vs_baseline']):.6f}: {ok}")

    if "max_ratio_vs_baseline" in rule:
        if base == 0:
            ratio = 1.0 if cand == 0 else float("inf")
        else:
            ratio = cand / base
        ok = ratio <= float(rule["max_ratio_vs_baseline"])
        passed = passed and ok
        reasons.append(f"ratio {ratio:.6f} <= {float(rule['max_ratio_vs_baseline']):.6f}: {ok}")

    if not reasons:
        if mode == "higher_is_better":
            ok = cand >= base
            reasons.append(f"{cand:.6f} >= baseline {base:.6f}: {ok}")
        else:
            ok = cand <= base
            reasons.append(f"{cand:.6f} <= baseline {base:.6f}: {ok}")
        passed = passed and ok

    return {
        "metric": metric,
        "mode": mode,
        "baseline": base,
        "candidate": cand,
        "passed": passed,
        "reasons": reasons,
    }


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_summary(path: Path, comparison: dict[str, Any]) -> None:
    status = "PASS" if comparison["accepted"] else "FAIL"
    lines = [
        "# Benchmark Comparison",
        "",
        f"Status: **{status}**",
        "",
        "| Metric | Baseline | Candidate | Passed |",
        "| --- | ---: | ---: | --- |",
    ]
    for rule in comparison["rules"]:
        lines.append(
            f"| `{rule['metric']}` | {rule['baseline']:.6f} | {rule['candidate']:.6f} | {rule['passed']} |"
        )
    if comparison["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in comparison["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compare(config_path: Path, baseline_path: Path, candidate_path: Path, output_path: Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    baseline = _load_result(baseline_path)
    candidate = _load_result(candidate_path)
    failures: list[str] = []

    if config.get("acceptance", {}).get("require_schema_valid", True):
        for label, result in (("baseline", baseline), ("candidate", candidate)):
            errors = validate_result_schema(result)
            failures.extend(f"{label} result schema error: {error}" for error in errors)

    if config.get("acceptance", {}).get("require_all_cases_completed", True):
        for label, result in (("baseline", baseline), ("candidate", candidate)):
            metrics = result.get("metrics", {})
            if metrics.get("failed_generations", 0) != 0:
                failures.append(f"{label} has failed_generations={metrics.get('failed_generations')}")
            if metrics.get("completed_cases") != metrics.get("total_cases"):
                failures.append(
                    f"{label} completed_cases={metrics.get('completed_cases')} total_cases={metrics.get('total_cases')}"
                )

    rule_results = [
        _evaluate_rule(rule, baseline, candidate)
        for rule in config.get("acceptance", {}).get("rules", [])
    ]
    for rule in rule_results:
        if not rule["passed"]:
            failures.append(f"rule failed for {rule['metric']}: {'; '.join(rule['reasons'])}")

    comparison = {
        "accepted": not failures,
        "baseline": {
            "agent": baseline.get("agent", {}),
            "suite": baseline.get("suite", {}),
            "metrics": baseline.get("metrics", {}),
        },
        "candidate": {
            "agent": candidate.get("agent", {}),
            "suite": candidate.get("suite", {}),
            "metrics": candidate.get("metrics", {}),
        },
        "rules": rule_results,
        "failures": failures,
    }

    _write_json(output_path, comparison)
    _write_summary(output_path.with_suffix(".md"), comparison)
    return comparison


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare benchmark results against acceptance rules.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    comparison = compare(
        Path(args.config).resolve(),
        Path(args.baseline).resolve(),
        Path(args.candidate).resolve(),
        Path(args.output).resolve(),
    )
    return 0 if comparison["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
