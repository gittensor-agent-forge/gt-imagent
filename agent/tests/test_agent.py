from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

import agent.agent as agent_module
from agent.agent import DEFAULT_OPENROUTER_MODEL, ImageAgent, OpenRouterImageError


def _setup_agent(tmp_path: Path, backend: dict[str, Any] | None = None) -> ImageAgent:
    agent = ImageAgent()
    agent.setup({"agent": {"image_backend": backend or {}}}, tmp_path)
    return agent


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _image_response() -> dict[str, Any]:
    return {
        "created": 1783296000,
        "data": [
            {
                "b64_json": base64.b64encode(b"fake-png-bytes").decode("ascii"),
                "media_type": "image/png",
            }
        ],
        "usage": {"cost": 0.0123, "total_tokens": 123},
    }


def _mock_openrouter(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
        requests.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    return requests


def test_generate_returns_bytes_and_never_touches_the_filesystem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests = _mock_openrouter(monkeypatch)
    agent = _setup_agent(tmp_path, {"model": DEFAULT_OPENROUTER_MODEL, "resolution": "1K"})

    result = agent.generate({"run_id": "case-1", "capability": "plan", "prompt": "Create a small poster."})

    assert result["image_bytes"] == b"fake-png-bytes"
    assert result["media_type"] == "image/png"
    assert result["metadata"]["model"] == DEFAULT_OPENROUTER_MODEL
    assert result["metadata"]["cost_usd"] == pytest.approx(0.0123)
    assert requests[0]["model"] == DEFAULT_OPENROUTER_MODEL
    assert requests[0]["resolution"] == "1K"
    # The agent must not decide where artifacts live; that is the engine's job.
    assert list(tmp_path.iterdir()) == []


def test_generate_result_carries_a_serializable_trace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_openrouter(monkeypatch)
    agent = _setup_agent(tmp_path)

    trace = agent.generate({"run_id": "case-1", "prompt": "Create a small poster."})["trace"]

    assert json.loads(json.dumps(trace))["user_prompt"] == "Create a small poster."
    assert trace["provider"] == "openrouter"
    assert trace["trajectory"] == ImageAgent.trajectory
    # The API key must never reach the trace.
    assert "test-key" not in json.dumps(trace)


def test_generate_requires_setup_first(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="setup"):
        ImageAgent().generate({"run_id": "case-1", "prompt": "hello"})


def test_generate_requires_an_openrouter_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    agent = _setup_agent(tmp_path)

    with pytest.raises(OpenRouterImageError, match="OPENROUTER_API_KEY"):
        agent.generate({"run_id": "missing-key", "prompt": "Create a small poster."})


def test_generate_has_no_mock_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    agent = _setup_agent(tmp_path, {"mode": "mock"})

    with pytest.raises(OpenRouterImageError):
        agent.generate({"run_id": "mock", "prompt": "Create a small poster."})


def test_context_combines_memory_assets_and_search_snapshots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "brief.json").write_text(
        json.dumps(
            {
                "title": "Launch Readiness Board",
                "sections": ["Scope", "Risks", "Owners"],
                "required_text": ["Scope", "Risks", "Owners"],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "snapshot.json").write_text(
        json.dumps({"facts": ["Planning reduces the readiness gap.", "Unrelated fact."]}),
        encoding="utf-8",
    )
    requests = _mock_openrouter(monkeypatch)
    agent = _setup_agent(tmp_path)

    agent.generate(
        {
            "run_id": "mixed-context",
            "capability": "search",
            "prompt": "Create a readiness board.",
            "allowed_tools": ["search"],
            "assets": ["brief.json"],
            "search_snapshots": ["snapshot.json"],
        }
    )

    prompt = requests[0]["prompt"]

    assert "Launch Readiness Board" in prompt
    assert "Scope" in prompt
    assert "readiness gap" in prompt


def test_generate_tolerates_null_allowed_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_openrouter(monkeypatch)
    agent = _setup_agent(tmp_path)

    result = agent.generate(
        {"run_id": "null-tools", "prompt": "Create a poster.", "allowed_tools": None, "memory": None}
    )

    assert result["image_bytes"] == b"fake-png-bytes"


def test_read_assets_merges_multiple_json_assets(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps({"title": "First Board", "sections": ["Alpha"], "required_text": ["Alpha"]}),
        encoding="utf-8",
    )
    (tmp_path / "b.json").write_text(
        json.dumps({"title": "Second Board", "required_text": ["Beta"]}),
        encoding="utf-8",
    )
    agent = _setup_agent(tmp_path)

    merged = agent._read_assets(["b.json", "a.json"])

    # Sorted-filename order: a.json then b.json. b.json overrides title and
    # required_text; a.json's sections survive because b.json omits them.
    assert merged["title"] == "Second Board"
    assert merged["sections"] == ["Alpha"]
    assert merged["required_text"] == ["Beta"]


def test_case_assets_cannot_escape_the_workdir(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    (tmp_path / "outside.json").write_text("{}", encoding="utf-8")
    agent = _setup_agent(workdir)

    with pytest.raises(ValueError):
        agent._case_path("../outside.json")


def test_image_bytes_from_url_rejects_file_scheme(tmp_path: Path) -> None:
    agent = _setup_agent(tmp_path)

    with pytest.raises(OpenRouterImageError, match="scheme is not allowed"):
        agent_module._image_bytes_from_url("file:///etc/passwd", "image/png", agent.backend_config)


def test_agent_manifest_points_at_the_declared_entrypoint() -> None:
    manifest = (Path(__file__).resolve().parents[1] / "agent.yaml").read_text(encoding="utf-8")

    assert "entrypoint: agent.agent:ImageAgent" in manifest
