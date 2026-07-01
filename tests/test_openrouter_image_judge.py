from __future__ import annotations

import json
from pathlib import Path

from imagent_bench.evaluators.checklist import evaluate_case
from imagent_bench.evaluators.judge import OpenRouterImageJudge, build_image_judge


def _write_case_and_output(tmp_path: Path) -> tuple[dict, dict]:
    image_path = tmp_path / "image.svg"
    trace_path = tmp_path / "trace.json"
    image_path.write_text("<svg><text>PASS</text></svg>", encoding="utf-8")
    trace_path.write_text(
        json.dumps(
            {
                "planning": {"missing_context": ["verification target"]},
                "grounding": {"reason": [], "search": [], "memory": []},
                "final_generation_context": {"prompt": "PASS"},
                "feedback": [],
            }
        ),
        encoding="utf-8",
    )
    case = {
        "id": "judge-001",
        "capability": "feedback",
        "prompt": "Create a badge with PASS.",
        "expected": {"checks": [{"type": "image_contains", "value": "PASS"}]},
    }
    output = {"image_path": str(image_path), "trace_path": str(trace_path), "metadata": {}}
    return case, output


def _judge_config(**overrides) -> dict:
    image_judge = {"provider": "openrouter", "model": "openai/gpt-4o", "fail_closed": True}
    image_judge.update(overrides)
    return {"evaluation": {"image_judge": image_judge}}


def _chat_response(passed: bool, reason: str) -> dict:
    content = json.dumps({"checks": [{"index": 0, "passed": passed, "reason": reason}]})
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def test_build_image_judge_returns_openrouter_provider(tmp_path: Path) -> None:
    judge = build_image_judge(_judge_config(), tmp_path)
    assert isinstance(judge, OpenRouterImageJudge)
    assert judge.provider == "openrouter"


def test_openrouter_judge_fails_closed_without_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    case, output = _write_case_and_output(tmp_path)
    judge = build_image_judge(_judge_config(), tmp_path)

    evaluation = evaluate_case(case, output, tmp_path, image_judge=judge)

    assert evaluation["passed"] is False
    assert evaluation["checks"][0]["provider"] == "openrouter"
    assert "OPENROUTER_API_KEY" in evaluation["checks"][0]["reason"]


def test_openrouter_request_payload_targets_chat_completions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    case, output = _write_case_and_output(tmp_path)
    judge = build_image_judge(_judge_config(max_output_tokens=800, reasoning_effort="low"), tmp_path)

    captured: dict = {}

    def fake_post(payload: dict) -> dict:
        captured["payload"] = payload
        return _chat_response(True, "image shows the PASS label")

    monkeypatch.setattr(judge, "_post_json", fake_post)

    evaluation = evaluate_case(case, output, tmp_path, image_judge=judge)

    payload = captured["payload"]
    # OpenRouter is Chat Completions, not the OpenAI Responses API.
    assert "messages" in payload
    assert "input" not in payload
    assert "text" not in payload
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["max_tokens"] == 800
    assert "max_output_tokens" not in payload
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["provider"]["require_parameters"] is True
    image_part = next(part for part in payload["messages"][0]["content"] if part["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/")
    assert image_part["image_url"]["detail"] == "high"

    # Verdict is parsed from choices[0].message.content.
    assert evaluation["passed"] is True
    assert evaluation["checks"][0]["provider"] == "openrouter"


def test_openrouter_judge_parses_failed_verdict(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    case, output = _write_case_and_output(tmp_path)
    judge = build_image_judge(_judge_config(), tmp_path)

    monkeypatch.setattr(judge, "_post_json", lambda payload: _chat_response(False, "no PASS visible"))

    evaluation = evaluate_case(case, output, tmp_path, image_judge=judge)

    assert evaluation["passed"] is False
    assert evaluation["checks"][0]["reason"] == "no PASS visible"


def test_openrouter_judge_records_usage_cost(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    case, output = _write_case_and_output(tmp_path)
    judge = build_image_judge(_judge_config(), tmp_path)
    assert judge.total_cost_usd == 0.0

    def fake_post(payload: dict) -> dict:
        response = _chat_response(True, "shows PASS")
        response["usage"] = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110, "cost": 0.0123}
        return response

    monkeypatch.setattr(judge, "_post_json", fake_post)

    evaluate_case(case, output, tmp_path, image_judge=judge)

    assert judge.total_cost_usd == 0.0123
