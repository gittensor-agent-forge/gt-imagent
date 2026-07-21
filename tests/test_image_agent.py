from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent.agent as agent_module
from agent.agent import DEFAULT_OPENROUTER_MODEL, ImageAgent, OpenRouterImageError
from imagent_runtime import cli as runtime_cli


def _setup_agent(tmp_path: Path, backend: dict[str, Any] | None = None) -> ImageAgent:
    agent = ImageAgent()
    agent.setup({"agent": {"image_backend": backend or {}}}, tmp_path)
    return agent


def test_base_agent_does_not_fallback_to_mock_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    agent = _setup_agent(tmp_path, {"mode": "mock"})

    with pytest.raises(OpenRouterImageError, match="OPENROUTER_API_KEY"):
        agent.generate(
            {
                "run_id": "plan-layout",
                "capability": "plan",
                "prompt": "Create a three-panel infographic titled Context Gap Toolkit with sections Plan, Ground, Verify.",
                "allowed_tools": ["plan"],
            },
            tmp_path / "output",
        )


def test_base_agent_uses_external_runtime(tmp_path: Path) -> None:
    agent = _setup_agent(tmp_path)

    assert agent.runtime.__class__.__module__ == "imagent_runtime.agent_runtime"


def test_base_agent_calls_openrouter_gemini_and_writes_image(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests: list[dict[str, Any]] = []
    response_payload = {
        "created": 1783296000,
        "data": [
            {
                "b64_json": base64.b64encode(b"fake-png-bytes").decode("ascii"),
                "media_type": "image/png",
            }
        ],
        "usage": {"cost": 0.0123, "total_tokens": 123},
    }

    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "authorization": request.get_header("Authorization"),
                "payload": json.loads(request.data.decode("utf-8")),
            }
        )
        return _FakeResponse(response_payload)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    agent = _setup_agent(
        tmp_path,
        {
            "mode": "live",
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "referer": "https://tryimagent.com",
            "title": "imagent test",
        },
    )

    output = agent.generate(
        {
            "run_id": "openrouter-live",
            "capability": "plan",
            "prompt": "Create a three-panel infographic titled Context Gap Toolkit with sections Plan, Ground, Verify.",
            "allowed_tools": ["plan"],
        },
        tmp_path / "output",
    )

    image_path = Path(output["image_path"])
    trace_text = Path(output["trace_path"]).read_text(encoding="utf-8")
    trace = json.loads(trace_text)

    assert image_path.suffix == ".png"
    assert image_path.read_bytes() == b"fake-png-bytes"
    assert requests[0]["url"] == "https://openrouter.ai/api/v1/images"
    assert requests[0]["authorization"] == "Bearer test-key"
    assert requests[0]["payload"]["model"] == DEFAULT_OPENROUTER_MODEL
    assert requests[0]["payload"]["aspect_ratio"] == "1:1"
    assert requests[0]["payload"]["resolution"] == "1K"
    assert "Context Gap Toolkit" in requests[0]["payload"]["prompt"]
    assert "test-key" not in trace_text
    assert trace["provider"] == "openrouter"
    assert trace["runtime"]["id"] == "base-agent-runtime"
    assert trace["runtime"]["steps"][-1] == "persist_artifacts"
    assert trace["model"] == DEFAULT_OPENROUTER_MODEL
    assert output["metadata"]["model"] == DEFAULT_OPENROUTER_MODEL
    assert output["metadata"]["runtime_id"] == "base-agent-runtime"
    assert output["metadata"]["cost_usd"] == 0.0123


def test_cli_runs_reference_agent_with_openrouter(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)

    exit_code = runtime_cli.main(
        [
            "Create a benchmark badge titled CLI PASS.",
            "--run-id",
            "cli-pass",
            "--output-dir",
            str(tmp_path / "cli-output"),
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(result["image_path"]).name == "cli-pass.png"
    assert Path(result["image_path"]).read_bytes() == b"fake-png-bytes"
    assert Path(result["trace_path"]).exists()
    assert result["metadata"]["runtime_id"] == "base-agent-runtime"


def test_cli_defaults_to_timestamped_results_directory(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        return _FakeResponse(_image_response())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)

    exit_code = runtime_cli.main(["Create a timestamped result image."])
    result = json.loads(capsys.readouterr().out)
    image_path = Path(result["image_path"])
    trace_path = Path(result["trace_path"])
    run_id = image_path.stem
    run_dir = image_path.parents[1]

    assert exit_code == 0
    assert re.fullmatch(r"\d{8}-\d{6}", run_id)
    assert run_dir == tmp_path / "results" / run_id
    assert image_path == run_dir / "images" / f"{run_id}.png"
    assert trace_path == run_dir / "traces" / f"{run_id}.json"


def test_cli_keeps_prompt_flag_for_compatibility(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)

    exit_code = runtime_cli.main(
        [
            "--prompt",
            "Create a legacy prompt flag image.",
            "--run-id",
            "legacy-prompt",
            "--output-dir",
            str(tmp_path / "legacy-output"),
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(result["image_path"]).name == "legacy-prompt.png"


def test_base_agent_requires_openrouter_key_for_live_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    agent = _setup_agent(tmp_path, {"mode": "live"})

    with pytest.raises(OpenRouterImageError, match="OPENROUTER_API_KEY"):
        agent.generate(
            {
                "run_id": "missing-key",
                "capability": "plan",
                "prompt": "Create a small poster.",
            },
            tmp_path / "output",
        )


def test_base_agent_uses_memory_asset_reasoning_and_search_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    asset = tmp_path / "brief.json"
    asset.write_text(
        json.dumps(
            {
                "title": "Launch Readiness Board",
                "sections": ["Scope", "Risks", "Owners"],
                "required_text": ["Launch Readiness Board", "Scope", "Risks", "Owners"],
            }
        ),
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "facts": [
                    "Image-Agent reduces the context gap through planning.",
                    "Unrelated fact.",
                ]
            }
        ),
        encoding="utf-8",
    )
    requests: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        requests.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    agent = _setup_agent(tmp_path)

    output = agent.generate(
        {
            "run_id": "mixed-context",
            "capability": "search",
            "prompt": "Create a card that shows the correct result of (8 + 4) / 3 about Image-Agent context gap.",
            "allowed_tools": ["reason", "search"],
            "assets": ["brief.json"],
            "search_snapshots": ["snapshot.json"],
        },
        tmp_path / "output",
    )

    prompt = requests[0]["prompt"]

    assert Path(output["image_path"]).read_bytes() == b"fake-png-bytes"
    assert "Launch Readiness Board" in prompt
    assert "Scope" in prompt
    assert "(8 + 4) / 3 = 4" in prompt
    assert "context gap" in prompt


def test_generate_handles_date_like_prompt_without_syntax_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    agent = _setup_agent(tmp_path)

    output = agent.generate(
        {
            "run_id": "date-prompt",
            "capability": "reason",
            "prompt": "Create a badge for the event on 2026-07-21.",
            "allowed_tools": ["reason"],
        },
        tmp_path / "output",
    )

    assert Path(output["image_path"]).read_bytes() == b"fake-png-bytes"


def test_generate_handles_incomplete_expression_without_syntax_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    agent = _setup_agent(tmp_path)

    output = agent.generate(
        {
            "run_id": "partial-expr",
            "capability": "reason",
            "prompt": "Rate this 8+ out of ten.",
            "allowed_tools": ["reason"],
        },
        tmp_path / "output",
    )

    assert Path(output["image_path"]).read_bytes() == b"fake-png-bytes"


def test_generate_handles_null_allowed_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    agent = _setup_agent(tmp_path)

    output = agent.generate(
        {
            "run_id": "null-tools",
            "capability": "plan",
            "prompt": "Create a simple poster.",
            "allowed_tools": None,
        },
        tmp_path / "output",
    )

    assert Path(output["image_path"]).read_bytes() == b"fake-png-bytes"


def test_read_assets_merges_multiple_json_assets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps({"title": "First Board", "sections": ["Alpha"], "required_text": ["Alpha"]}),
        encoding="utf-8",
    )
    (tmp_path / "b.json").write_text(
        json.dumps({"title": "Second Board", "required_text": ["Beta"]}),
        encoding="utf-8",
    )
    requests: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        requests.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    agent = _setup_agent(tmp_path)

    merged = agent._read_assets(["b.json", "a.json"])

    # Sorted-filename order: a.json then b.json. b.json overrides title and
    # required_text; a.json's sections survive because b.json omits them.
    assert merged["title"] == "Second Board"
    assert merged["sections"] == ["Alpha"]
    assert merged["required_text"] == ["Beta"]


def test_image_bytes_from_url_rejects_file_scheme(tmp_path: Path) -> None:
    agent = _setup_agent(tmp_path)
    with pytest.raises(OpenRouterImageError, match="scheme is not allowed"):
        agent_module._image_bytes_from_url(
            "file:///etc/passwd", "image/png", agent.backend_config
        )


def test_cli_config_json_values_survive_without_flags(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"agent": {"image_backend": {"resolution": "4K", "aspect_ratio": "16:9"}}}),
        encoding="utf-8",
    )
    captured: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        captured.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)

    exit_code = runtime_cli.main(
        [
            "Create a badge.",
            "--config-json",
            str(config_path),
            "--run-id",
            "config-survives",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    capsys.readouterr()

    assert exit_code == 0
    assert captured[0]["resolution"] == "4K"
    assert captured[0]["aspect_ratio"] == "16:9"


def test_cli_explicit_flag_overrides_config_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"agent": {"image_backend": {"resolution": "4K", "aspect_ratio": "16:9"}}}),
        encoding="utf-8",
    )
    captured: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: int) -> "_FakeResponse":
        captured.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(_image_response())

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)

    exit_code = runtime_cli.main(
        [
            "Create a badge.",
            "--config-json",
            str(config_path),
            "--resolution",
            "2K",
            "--run-id",
            "flag-overrides",
            "--output-dir",
            str(tmp_path / "out2"),
        ]
    )
    capsys.readouterr()

    assert exit_code == 0
    assert captured[0]["resolution"] == "2K"
    assert captured[0]["aspect_ratio"] == "16:9"


def test_candidate_subprocess_env_strips_github_tokens_keeps_openrouter() -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()
    base_env = {
        "GITHUB_TOKEN": "secret-gh",
        "GH_TOKEN": "secret-gh2",
        "OPENROUTER_API_KEY": "secret-or",
        "PATH": "/usr/bin",
    }

    env = round_manager._candidate_subprocess_env(base_env)

    assert "GITHUB_TOKEN" not in env
    assert "GH_TOKEN" not in env
    assert env["OPENROUTER_API_KEY"] == "secret-or"
    assert env["PATH"] == "/usr/bin"
    # original mapping is not mutated
    assert base_env["GITHUB_TOKEN"] == "secret-gh"


def test_merge_improvement_reason_guards_non_string() -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()

    assert round_manager.is_merge_improvement_reason(None) is False
    assert round_manager.is_merge_improvement_reason(123) is False
    assert (
        round_manager.is_merge_improvement_reason("score improvement 0.50 is below required 1.00")
        is True
    )


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


def test_agent_manifest_points_at_base_candidate_entrypoint() -> None:
    manifest = Path("agent/agent.yaml").read_text(encoding="utf-8")

    assert "entrypoint: agent.agent:ImageAgent" in manifest


def test_last_winner_module_is_importable_when_empty() -> None:
    import agent.last_winner as last_winner

    assert last_winner.__name__ == "agent.last_winner"


def test_round_helper_generates_two_daily_utc_slots() -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()

    assert round_manager.current_round_id(datetime(2026, 7, 6, 0, 0, tzinfo=UTC)) == "20260706-0"
    assert round_manager.current_round_id(datetime(2026, 7, 6, 11, 59, tzinfo=UTC)) == "20260706-0"
    assert round_manager.current_round_id(datetime(2026, 7, 6, 12, 0, tzinfo=UTC)) == "20260706-1"
    assert round_manager.current_round_id(datetime(2026, 7, 6, 23, 59, tzinfo=UTC)) == "20260706-1"


def test_round_archive_filename_is_stable_and_safe() -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()

    assert (
        round_manager.archive_filename("20260706-1", 42, "abcdef1234567890")
        == "20260706_1_pr_42_abcdef123456.py"
    )


def test_round_candidate_file_rules_only_accept_agent_candidate_surface() -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()

    assert round_manager.candidate_file_failures(["agent/agent.py"]) == []

    failures = round_manager.candidate_file_failures(["tests/test_image_agent.py"])
    assert "agent/agent.py" in "\n".join(failures)

    failures = round_manager.candidate_file_failures(["agent/agent.py", "tests/test_image_agent.py"])
    assert "may only change `agent/agent.py`" in "\n".join(failures)

    failures = round_manager.candidate_file_failures(["agent/agent.py", "agent/last_winner.py", "winners/past.py"])
    assert "agent/last_winner.py" in "\n".join(failures)


def test_round_quality_policy_uses_round_threshold_for_merge_improvement() -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()

    merge_threshold_report = {
        "status": "fail",
        "policy": {"reasons": ["score improvement 0.50 is below required 1.00"]},
    }
    quality_failure_report = {
        "status": "fail",
        "policy": {"reasons": ["overall score 70.00 is below required 75.00"]},
    }

    assert round_manager.report_passes_quality_policy(merge_threshold_report) is True
    assert round_manager.report_passes_quality_policy(quality_failure_report) is False


def test_round_promotion_staging_keeps_final_diff_to_winner_files(tmp_path: Path) -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "agent").mkdir()
    (repo / "agent" / "agent.py").write_text("BASE = True\n", encoding="utf-8")
    (repo / "agent" / "agent.yaml").write_text("entrypoint: agent.agent:ImageAgent\n", encoding="utf-8")
    (repo / "agent" / "last_winner.py").write_text("", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base_branch = _git_output(repo, "branch", "--show-current")

    _git(repo, "checkout", "-q", "-b", "candidate")
    (repo / "agent" / "agent.py").write_text("WINNER = True\n", encoding="utf-8")
    _git(repo, "add", "agent/agent.py")
    _git(repo, "commit", "-q", "-m", "candidate")
    head = _git_output(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", base_branch)
    (repo / "agent" / "last_winner.py").write_text("WINNER_A = True\n", encoding="utf-8")
    (repo / "winners").mkdir()
    (repo / "winners" / "a.py").write_text("WINNER_A = True\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "promote-a")
    base = _git_output(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "candidate")
    (repo / "_imagent-bench").mkdir()
    (repo / "_imagent-bench" / "artifact.txt").write_text("do not stage\n", encoding="utf-8")

    cwd = Path.cwd()
    os.chdir(repo)
    try:
        candidate_paths = round_manager.changed_paths_between(base, head)
        winner_code = Path("agent/agent.py").read_text(encoding="utf-8")
        round_manager.merge_base_into_candidate(base)
        round_manager.restore_changed_paths_from_ref(base, candidate_paths)
        Path("agent/last_winner.py").write_text(winner_code, encoding="utf-8")
        Path("winners").mkdir(exist_ok=True)
        Path("winners/archive.py").write_text(winner_code, encoding="utf-8")
        round_manager.stage_paths([*candidate_paths, "agent/last_winner.py", "winners/archive.py"])
        staged = _git_output(repo, "diff", "--cached", "--name-only").splitlines()
        final_diff = _git_output(repo, "diff", "--cached", "--name-status", base).splitlines()
    finally:
        os.chdir(cwd)

    assert "_imagent-bench/artifact.txt" not in staged
    assert final_diff == ["M\tagent/last_winner.py", "A\twinners/archive.py"]


def test_round_filters_maintainer_and_needs_rebase_prs() -> None:
    from support.round_manager_import import load_round_manager

    round_manager = load_round_manager()
    github = _FakeGitHub(
        [
            _pull(1, "alice", ["pr-rules-pass"]),
            _pull(2, "bob", ["pr-rules-pass", "needs-rebase"]),
            _pull(3, "carol", ["pr-rules-pass"], author_association="MEMBER"),
        ]
    )

    prs = round_manager.open_same_repo_prs(github, "gittensor-agent-forge/gt-imagent")

    assert [item["number"] for item in prs] == [1]
    assert round_manager.is_maintainer_pr(
        _pull(4, "dave", [], author_association="COLLABORATOR"), "gittensor-agent-forge/gt-imagent"
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True)


def _git_output(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _pull(number: int, author: str, labels: list[str], *, author_association: str = "CONTRIBUTOR") -> dict:
    return {
        "number": number,
        "created_at": f"2026-07-06T00:00:{number:02d}Z",
        "draft": False,
        "author_association": author_association,
        "head": {"repo": {"full_name": "gittensor-agent-forge/gt-imagent"}},
        "user": {"login": author},
        "labels": [{"name": label} for label in labels],
    }


class _FakeGitHub:
    def __init__(self, pulls: list[dict]) -> None:
        self.pulls = pulls

    def paginate(self, path: str) -> list[dict]:
        if path.startswith("/repos/gittensor-agent-forge/gt-imagent/pulls?"):
            return self.pulls
        raise AssertionError(path)

    def issue_labels(self, number: int) -> set[str]:
        pull = next(item for item in self.pulls if item["number"] == number)
        return {label["name"] for label in pull["labels"]}
