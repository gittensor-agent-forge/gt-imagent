from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def _load_image_text(output: dict[str, Any], output_dir: Path) -> tuple[str, str | None]:
    image_path = output.get("image_path")
    if not image_path:
        return "", "missing image_path"
    path = Path(image_path)
    if not path.is_absolute():
        path = output_dir / path
    if not path.exists():
        return "", f"image does not exist: {path}"
    try:
        return path.read_text(encoding="utf-8", errors="ignore").lower(), None
    except Exception as exc:  # noqa: BLE001
        return "", f"could not read image text: {exc}"


def _tool_items(trace: dict[str, Any], tool_name: str) -> list[Any]:
    grounding = trace.get("grounding", {})
    if not isinstance(grounding, dict):
        return []
    items = grounding.get(tool_name, [])
    return items if isinstance(items, list) else []


def _check_one(check: dict[str, Any], trace: dict[str, Any], image_text: str) -> tuple[bool, str]:
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

    if check_type == "image_contains":
        ok = all(value in image_text for value in wanted)
        return ok, "image text contains requested values" if ok else f"image text lacks {wanted}"

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


def evaluate_case(case: dict[str, Any], output: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    trace, trace_error = _load_trace(output, output_dir)
    image_text, image_error = _load_image_text(output, output_dir)
    checks = case.get("expected", {}).get("checks", [])

    check_results = []
    for index, check in enumerate(checks):
        if trace_error:
            passed, reason = False, trace_error
        elif image_error and check.get("type") == "image_contains":
            passed, reason = False, image_error
        else:
            passed, reason = _check_one(check, trace, image_text)
        check_results.append(
            {
                "index": index,
                "type": check.get("type"),
                "passed": passed,
                "reason": reason,
                "context_gap": check.get("type") in CONTEXT_GAP_CHECKS,
            }
        )

    return {
        "case_id": case["id"],
        "capability": case.get("capability", "unknown"),
        "trace_valid": trace_error is None,
        "image_valid": image_error is None,
        "checks": check_results,
        "passed": bool(check_results) and all(item["passed"] for item in check_results),
    }
