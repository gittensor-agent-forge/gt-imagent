from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from imagent_bench.evaluators.judge import resolve_image_path


CONTEXT_GAP_CHECKS = {
    "trace_has_missing_context",
    "used_tool",
    "final_prompt_contains",
    "feedback_used",
}


def _lower_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    return json.dumps(value, sort_keys=True).lower()


def _values(check: dict[str, Any]) -> list[str]:
    if "values" in check:
        return [str(value).lower() for value in check["values"]]
    if "value" in check:
        return [str(check["value"]).lower()]
    return []


def _load_trace(output: dict[str, Any], output_dir: Path) -> tuple[dict[str, Any], str | None]:
    trace_path = output.get("trace_path")
    if not trace_path:
        return {}, "missing trace_path"
    path = Path(trace_path)
    if not path.is_absolute():
        path = output_dir / path
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        return {}, f"could not load trace: {exc}"
    if not isinstance(data, dict):
        return {}, "trace must be a JSON object"
    return data, None


def _tool_items(trace: dict[str, Any], tool_name: str) -> list[Any]:
    grounding = trace.get("grounding", {})
    if not isinstance(grounding, dict):
        return []
    items = grounding.get(tool_name, [])
    return items if isinstance(items, list) else []


def _check_one(check: dict[str, Any], trace: dict[str, Any]) -> tuple[bool, str]:
    check_type = check.get("type")
    wanted = _values(check)

    if check_type == "always":
        return True, "always passes"

    if check_type == "trace_has_missing_context":
        planning = trace.get("planning", {})
        missing = planning.get("missing_context", []) if isinstance(planning, dict) else []
        haystack = _lower_text(missing)
        ok = all(value in haystack for value in wanted)
        return ok, "missing context contains requested values" if ok else f"missing context lacks {wanted}"

    if check_type == "used_tool":
        tool_name = str(check.get("value", "")).lower()
        ok = bool(_tool_items(trace, tool_name))
        return ok, f"used {tool_name}" if ok else f"did not use {tool_name}"

    if check_type == "final_prompt_contains":
        context = trace.get("final_generation_context", {})
        prompt = context.get("prompt", "") if isinstance(context, dict) else ""
        haystack = _lower_text(prompt)
        ok = all(value in haystack for value in wanted)
        return ok, "final prompt contains requested values" if ok else f"final prompt lacks {wanted}"

    if check_type == "feedback_used":
        feedback = trace.get("feedback", [])
        ok = isinstance(feedback, list) and len(feedback) > 0
        return ok, "feedback was used" if ok else "feedback was not used"

    if check_type == "feedback_attempts_at_most":
        feedback = trace.get("feedback", [])
        limit = int(check.get("value", 0))
        actual = len(feedback) if isinstance(feedback, list) else 0
        ok = actual <= limit
        return ok, f"feedback attempts {actual} <= {limit}" if ok else f"feedback attempts {actual} > {limit}"

    return False, f"unknown check type: {check_type}"


def _image_exists(output: dict[str, Any], output_dir: Path) -> bool:
    path = resolve_image_path(output, output_dir)
    return path is not None and path.exists()


def evaluate_case(
    case: dict[str, Any],
    output: dict[str, Any],
    output_dir: Path,
    image_judge: Any | None = None,
) -> dict[str, Any]:
    trace, trace_error = _load_trace(output, output_dir)
    checks = case.get("expected", {}).get("checks", [])
    image_verdicts = {}
    if image_judge is not None and trace_error is None:
        image_verdicts = image_judge.evaluate_image_checks(case, output, trace, checks)

    check_results = []
    for index, check in enumerate(checks):
        if trace_error:
            passed, reason = False, trace_error
            provider = None
        elif check.get("type") == "image_contains":
            verdict = image_verdicts.get(index)
            if verdict is None:
                passed, reason = False, "image judge did not return a verdict"
                provider = None
            else:
                passed, reason = verdict["passed"], verdict["reason"]
                provider = verdict.get("provider")
        else:
            passed, reason = _check_one(check, trace)
            provider = None
        result = {
            "index": index,
            "type": check.get("type"),
            "passed": passed,
            "reason": reason,
            "context_gap": check.get("type") in CONTEXT_GAP_CHECKS,
        }
        if provider:
            result["provider"] = provider
        check_results.append(result)

    return {
        "case_id": case["id"],
        "capability": case.get("capability", "unknown"),
        "trace_valid": trace_error is None,
        "image_valid": _image_exists(output, output_dir),
        "checks": check_results,
        "passed": bool(check_results) and all(item["passed"] for item in check_results),
    }
