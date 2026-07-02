from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

import agent.agent as agent_module
from agent import ImageAgent
from agent.image_backend_api import ImageBackendClient
from agent.verifier import MockTextVerifier, OpenRouterVisionVerifier, build_image_verifier


class _DummyVerifier:
    total_cost_usd = 0.0

    def evaluate_image_checks(self, case, output, trace, checks):  # noqa: D401, ANN001
        return {
            index: {"passed": True, "reason": "ok", "provider": "mock_text"}
            for index, _check in enumerate(checks)
        }


def _mock_config(*, max_feedback_rounds: int = 1, mode: str = "mock") -> dict:
    return {
        "runtime": {"max_feedback_rounds": max_feedback_rounds},
        "agent": {"image_backend": {"mode": mode}},
        "evaluation": {"image_judge": {"provider": "mock_text"}},
    }


def _feedback_case(seed: int = 1001) -> dict:
    return {
        "run_id": f"feedback-label-001--seed-{seed}",
        "capability": "feedback",
        "prompt": "Create a validation badge with the exact label PASS.",
        "seed": seed,
        "allowed_tools": ["feedback"],
    }


def _setup_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, max_feedback_rounds: int = 1, mode: str = "mock") -> ImageAgent:
    monkeypatch.setattr(
        agent_module,
        "build_image_verifier",
        lambda config, workdir: _DummyVerifier(),
    )
    agent = ImageAgent()
    agent.setup(_mock_config(max_feedback_rounds=max_feedback_rounds, mode=mode), tmp_path)
    return agent


def test_image_agent_setup_rejects_unknown_image_backend_mode(tmp_path: Path) -> None:
    agent = ImageAgent()

    with pytest.raises(ValueError, match="unsupported image backend mode"):
        agent.setup(_mock_config(mode="liv"), tmp_path)


def test_image_agent_mock_generate_writes_svg_and_trace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_score_candidate",
        lambda case, output_dir, candidate, spec: {
            "score": 1.0 if candidate["candidate_index"] == 0 else 0.0,
            "passed": True,
            "failed_checks": [],
            "critique": [],
            "cost_usd": 0.0,
        },
    )

    output = agent.generate(
        {
            "run_id": "plan-layout-001--seed-1001",
            "capability": "plan",
            "prompt": "Create a three-panel infographic titled Context Gap Toolkit with sections Plan, Ground, Verify.",
            "seed": 1001,
            "allowed_tools": ["plan"],
        },
        tmp_path,
    )

    image_path = Path(output["image_path"])
    trace_path = Path(output["trace_path"])
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    assert image_path.exists()
    assert trace_path.exists()
    assert output["metadata"]["provider"] == "mock"
    assert trace["planning"]["generation_spec"]["title"] == "Context Gap Toolkit"
    assert trace["planning"]["generation_plan"]["selected_candidate_index"] == 0
    assert any(call["tool"] == "planner" for call in trace["tool_calls"])


def test_mock_text_verifier_checks_visible_svg_text(tmp_path: Path) -> None:
    image_path = tmp_path / "card.svg"
    image_path.write_text("<svg><text>PASS</text><text>Signal Review</text></svg>", encoding="utf-8")
    verifier = MockTextVerifier({}, tmp_path)

    verdicts = verifier.evaluate_image_checks(
        {"id": "case-1"},
        {"image_path": str(image_path)},
        {},
        [
            {"type": "image_contains", "value": "PASS"},
            {"type": "image_contains", "value": "MISSING"},
        ],
    )

    assert verdicts[0]["passed"] is True
    assert verdicts[1]["passed"] is False


def test_mock_text_verifier_ignores_non_visible_svg_attributes(tmp_path: Path) -> None:
    image_path = tmp_path / "card.svg"
    image_path.write_text('<svg aria-label="PASS"><title>PASS</title></svg>', encoding="utf-8")
    verifier = MockTextVerifier({}, tmp_path)

    verdicts = verifier.evaluate_image_checks(
        {"id": "case-1"},
        {"image_path": str(image_path)},
        {},
        [{"type": "image_contains", "value": "PASS"}],
    )

    assert verdicts[0]["passed"] is False


def test_image_agent_builds_structured_spec_for_plan_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path)
    case = {
        "capability": "plan",
        "prompt": "Create a three-panel infographic titled Context Gap Toolkit with sections Plan, Ground, Verify.",
        "allowed_tools": ["plan"],
    }

    grounding = agent._build_grounding(case)
    spec = agent._build_generation_spec(case, grounding)

    assert spec["title"] == "Context Gap Toolkit"
    assert spec["layout"] == "three_panel"
    assert spec["must_include"][:4] == ["Context Gap Toolkit", "Plan", "Ground", "Verify"]
    assert spec["visual_constraints"]["sections"] == ["Plan", "Ground", "Verify"]


def test_image_agent_records_explicit_tool_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "title": "Image-Agent",
                "facts": [
                    "Image-Agent reduces the context gap through planning.",
                ],
            }
        ),
        encoding="utf-8",
    )
    asset = tmp_path / "brief.json"
    asset.write_text(
        json.dumps(
            {
                "title": "Launch Readiness Board",
                "layout": "three_panel",
                "required_text": ["Launch Readiness Board"],
            }
        ),
        encoding="utf-8",
    )
    agent = _setup_agent(monkeypatch, tmp_path)
    bundle = agent._build_grounding_bundle(
        {
            "capability": "search",
            "prompt": "Create a search card about Image-Agent planning.",
            "assets": [str(asset)],
            "allowed_tools": ["search", "memory"],
            "search_snapshots": [str(snapshot)],
            "memory": {"preferred_label": "Signal Review"},
        }
    )

    assert [call["tool"] for call in bundle.tool_calls] == ["asset", "search", "memory"]
    assert bundle.tool_calls[0]["arguments"]["asset_count"] == 1
    assert bundle.tool_calls[1]["arguments"]["snapshot_count"] == 1
    assert bundle.tool_calls[2]["arguments"]["memory_keys"] == ["preferred_label"]


def test_image_agent_builds_structured_spec_from_asset_brief(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    asset = tmp_path / "brief.json"
    asset.write_text(
        json.dumps(
            {
                "title": "Launch Readiness Board",
                "layout": "three_panel",
                "sections": ["Scope", "Risks", "Owners"],
                "required_text": ["Launch Readiness Board", "Scope", "Risks", "Owners"],
                "visual_constraints": {"density": "compact"},
            }
        ),
        encoding="utf-8",
    )
    agent = _setup_agent(monkeypatch, tmp_path)
    case = {
        "capability": "plan",
        "prompt": "Create a release-readiness board using the provided brief asset.",
        "assets": [str(asset)],
        "allowed_tools": ["plan"],
    }

    grounding = agent._build_grounding(case)
    spec = agent._build_generation_spec(case, grounding)

    assert grounding["asset"][0]["title"] == "Launch Readiness Board"
    assert spec["title"] == "Launch Readiness Board"
    assert spec["layout"] == "three_panel"
    assert spec["must_include"][:4] == ["Launch Readiness Board", "Scope", "Risks", "Owners"]


def test_image_agent_resolves_relative_asset_paths_from_workdir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    asset = workdir / "brief.json"
    asset.write_text(
        json.dumps(
            {
                "title": "Launch Readiness Board",
                "layout": "three_panel",
                "required_text": ["Launch Readiness Board"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    agent = _setup_agent(monkeypatch, workdir)

    grounding = agent._build_grounding(
        {
            "capability": "plan",
            "prompt": "Create a release-readiness board using the provided brief asset.",
            "assets": ["brief.json"],
            "allowed_tools": ["plan"],
        }
    )

    assert grounding["asset"][0]["title"] == "Launch Readiness Board"
    assert grounding["asset"][0]["source"] == str(asset)


def test_image_agent_search_ranks_top_three_facts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "title": "Image-Agent",
                "facts": [
                    "Image-Agent reduces the context gap through planning.",
                    "Planning improves the quality of structured image generation.",
                    "Context gap mitigation benefits from grounded facts.",
                    "Weather and bird migration are unrelated here.",
                ],
            }
        ),
        encoding="utf-8",
    )
    agent = _setup_agent(monkeypatch, tmp_path)

    results = agent._search(
        {
            "capability": "search",
            "prompt": "Create a research card about Image-Agent planning and context gap handling.",
            "allowed_tools": ["search"],
            "search_snapshots": [str(snapshot)],
        }
    )

    assert len(results) == 3
    assert results[0]["fact"] == "Image-Agent reduces the context gap through planning."
    assert all("bird migration" not in item["fact"] for item in results)


def test_image_agent_resolves_relative_search_snapshots_from_workdir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    snapshot = workdir / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "title": "Image-Agent",
                "facts": [
                    "Image-Agent reduces the context gap through planning.",
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    agent = _setup_agent(monkeypatch, workdir)

    results = agent._search(
        {
            "capability": "search",
            "prompt": "Create a research card about Image-Agent planning.",
            "allowed_tools": ["search"],
            "search_snapshots": ["snapshot.json"],
        }
    )

    assert len(results) == 1
    assert results[0]["source"] == str(snapshot)


def test_image_agent_search_ignores_unrelated_snapshots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "title": "Birds",
                "facts": [
                    "Migration peaks in spring.",
                    "Nests are built from twigs.",
                ],
            }
        ),
        encoding="utf-8",
    )
    agent = _setup_agent(monkeypatch, tmp_path)

    results = agent._search(
        {
            "capability": "search",
            "prompt": "Create a release dashboard for server latency.",
            "allowed_tools": ["search"],
            "search_snapshots": [str(snapshot)],
        }
    )

    assert results == []


def test_image_agent_memory_maps_visual_constraints(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path)

    memory = agent._memory(
        {
            "capability": "memory",
            "allowed_tools": ["memory"],
            "memory": {
                "preferred_label": "Image Agent Benchmark",
                "preferred_style": "minimal monochrome",
                "typography": "mono",
                "density": "compact",
                "persona": "ignored",
            },
        }
    )[0]

    assert memory["mapped_title"] == "Image Agent Benchmark"
    assert memory["mapped_style"] == "minimal monochrome"
    assert memory["visual_constraints"] == {"typography": "mono", "density": "compact"}
    assert memory["unmapped"] == {"persona": "ignored"}


def test_image_agent_reason_normalizes_parenthesized_arithmetic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path)

    result = agent._reason(
        {
            "capability": "reason",
            "prompt": "Create a card that shows the correct result of (8 + 4) / 3.",
            "allowed_tools": ["reason"],
        }
    )[0]

    assert result["source"] == "local-arithmetic-parser"
    assert result["answer"] == "4"
    assert result["display"] == "(8 + 4) / 3 = 4"


def test_image_agent_mock_svg_renders_spec_not_raw_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_score_candidate",
        lambda case, output_dir, candidate, spec: {
            "score": 1.0 if candidate["candidate_index"] == 0 else 0.0,
            "passed": True,
            "failed_checks": [],
            "critique": [],
            "cost_usd": 0.0,
        },
    )
    output = agent.generate(
        {
            "run_id": "reason-math-001--seed-1001",
            "capability": "reason",
            "prompt": "Create a small educational card that shows the correct result of 2 + 3.",
            "seed": 1001,
            "allowed_tools": ["reason"],
        },
        tmp_path,
    )
    image_text = Path(output["image_path"]).read_text(encoding="utf-8")

    assert "2 + 3 = 5" in image_text
    assert "Create a small educational card that shows the correct result of 2 + 3." not in image_text


def test_image_agent_selects_second_candidate_without_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path, max_feedback_rounds=0)
    scores = iter(
        [
            {"score": 0.2, "passed": False, "failed_checks": ["PASS"], "critique": ["Add exact visible text: PASS"], "cost_usd": 0.0},
            {"score": 1.0, "passed": True, "failed_checks": [], "critique": [], "cost_usd": 0.0},
        ]
    )
    monkeypatch.setattr(agent, "_score_candidate", lambda case, output_dir, candidate, spec: next(scores))

    output = agent.generate(_feedback_case(), tmp_path)
    trace = json.loads(Path(output["trace_path"]).read_text(encoding="utf-8"))

    assert Path(output["image_path"]).exists()
    assert len(trace["feedback"]) == 1
    assert trace["feedback"][0]["candidate_index"] == 1
    assert trace["feedback"][0]["selected"] is True
    assert len(trace["feedback_attempts"]) == 2
    assert trace["feedback_attempts"][1]["selected"] is True


def test_image_agent_revises_after_round_zero_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path, max_feedback_rounds=1)
    scores = iter(
        [
            {"score": 0.1, "passed": False, "failed_checks": ["PASS"], "critique": ["Add exact visible text: PASS"], "cost_usd": 0.0},
            {"score": 0.3, "passed": False, "failed_checks": ["PASS"], "critique": ["Add exact visible text: PASS"], "cost_usd": 0.0},
            {"score": 1.0, "passed": True, "failed_checks": [], "critique": [], "cost_usd": 0.0},
            {"score": 0.6, "passed": False, "failed_checks": ["PASS"], "critique": ["Add exact visible text: PASS"], "cost_usd": 0.0},
        ]
    )
    monkeypatch.setattr(agent, "_score_candidate", lambda case, output_dir, candidate, spec: next(scores))

    output = agent.generate(_feedback_case(), tmp_path)
    trace = json.loads(Path(output["trace_path"]).read_text(encoding="utf-8"))

    assert len(trace["feedback"]) == 2
    assert trace["feedback"][0]["selected"] is False
    assert trace["feedback"][0]["failed_checks"] == ["PASS"]
    assert trace["feedback"][1]["selected"] is True
    assert "revision_focus" in trace["feedback"][1]["candidate_prompt"]
    assert len(trace["feedback_attempts"]) == 4
    assert sum(1 for attempt in trace["feedback_attempts"] if attempt["selected"]) == 1
    assert "PASS" in trace["final_generation_context"]["prompt"]


def test_image_agent_honors_configured_feedback_rounds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _setup_agent(monkeypatch, tmp_path, max_feedback_rounds=3)
    monkeypatch.setattr(
        agent,
        "_score_candidate",
        lambda case, output_dir, candidate, spec: {
            "score": 0.0,
            "passed": False,
            "failed_checks": ["PASS"],
            "critique": ["Add exact visible text: PASS"],
            "cost_usd": 0.0,
        },
    )

    output = agent.generate(_feedback_case(), tmp_path)
    trace = json.loads(Path(output["trace_path"]).read_text(encoding="utf-8"))

    assert len(trace["feedback"]) == 4
    assert len(trace["feedback_attempts"]) == 8
    assert trace["feedback"][-1]["round"] == 3
    assert trace["feedback_attempts"][-1]["round"] == 3


def test_build_image_verifier_normalizes_live_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    verifier = build_image_verifier({"agent": {"image_backend": {"mode": " LIVE "}}}, tmp_path)

    assert isinstance(verifier, OpenRouterVisionVerifier)


def test_image_agent_live_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    agent = ImageAgent()

    with pytest.raises(Exception, match="OPENROUTER_API_KEY"):
        agent.setup(_mock_config(mode="live"), tmp_path)


def test_image_backend_client_uses_returned_media_type_extension(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = ImageBackendClient({"output_format": "png"})
    jpeg_bytes = b"jpeg-bytes"

    def fake_post(payload: dict) -> dict:
        return {
            "data": [
                {
                    "b64_json": base64.b64encode(jpeg_bytes).decode("ascii"),
                    "media_type": "image/jpeg",
                }
            ],
            "usage": {"cost": 0.01},
        }

    monkeypatch.setattr(client, "_post_json", fake_post)

    metadata = client.generate("prompt", 1001, tmp_path / "image.png")

    assert metadata["media_type"] == "image/jpeg"
    assert metadata["image_path"].endswith(".jpg")
    assert (tmp_path / "image.jpg").read_bytes() == jpeg_bytes


def test_image_agent_records_actual_live_image_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    agent = _setup_agent(monkeypatch, tmp_path, max_feedback_rounds=0, mode="live")

    class FakeClient:
        def generate(self, prompt: str, seed: int, output_path: Path) -> dict[str, object]:
            jpg_path = output_path.with_suffix(".jpg")
            jpg_path.write_bytes(b"jpg")
            return {
                "image_path": str(jpg_path),
                "provider": "openrouter",
                "model": "fake-model",
                "cost_usd": 0.01,
            }

    agent.client = FakeClient()
    monkeypatch.setattr(
        agent,
        "_score_candidate",
        lambda case, output_dir, candidate, spec: {
            "score": 1.0 if candidate["candidate_index"] == 0 else 0.0,
            "passed": True,
            "failed_checks": [],
            "critique": [],
            "cost_usd": 0.0,
        },
    )
    output = agent.generate(
        {
            "run_id": "live-case",
            "capability": "plan",
            "prompt": "Create a card.",
            "seed": 1001,
            "allowed_tools": [],
        },
        tmp_path,
    )

    trace = json.loads(Path(output["trace_path"]).read_text(encoding="utf-8"))

    assert output["image_path"].endswith(".jpg")
    assert trace["planning"]["generation_plan"]["format"] == "jpg"
