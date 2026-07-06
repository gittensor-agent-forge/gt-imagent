from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from agent.agent import ImageAgent


def _setup_agent(tmp_path: Path) -> ImageAgent:
    agent = ImageAgent()
    agent.setup({"agent": {"image_backend": {"mode": "mock"}}}, tmp_path)
    return agent


def test_base_agent_writes_svg_and_trace(tmp_path: Path) -> None:
    agent = _setup_agent(tmp_path)

    output = agent.generate(
        {
            "run_id": "plan-layout",
            "capability": "plan",
            "prompt": "Create a three-panel infographic titled Context Gap Toolkit with sections Plan, Ground, Verify.",
            "allowed_tools": ["plan"],
        },
        tmp_path / "output",
    )

    image_text = Path(output["image_path"]).read_text(encoding="utf-8")
    trace = json.loads(Path(output["trace_path"]).read_text(encoding="utf-8"))

    assert "Context Gap Toolkit" in image_text
    assert "Plan" in image_text
    assert "Ground" in image_text
    assert "Verify" in image_text
    assert trace["agent"] == "base"
    assert output["metadata"]["agent_id"] == "base-image-agent"


def test_base_agent_uses_memory_asset_reasoning_and_search_context(tmp_path: Path) -> None:
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

    image_text = Path(output["image_path"]).read_text(encoding="utf-8")

    assert "Launch Readiness Board" in image_text
    assert "Scope" in image_text
    assert "(8 + 4) / 3 = 4" in image_text
    assert "context gap" in image_text


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

    prs = round_manager.open_same_repo_prs(github, "imagent-ai/imagent")

    assert [item["number"] for item in prs] == [1]
    assert round_manager.is_maintainer_pr(_pull(4, "dave", [], author_association="COLLABORATOR"), "imagent-ai/imagent")


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
        "head": {"repo": {"full_name": "imagent-ai/imagent"}},
        "user": {"login": author},
        "labels": [{"name": label} for label in labels],
    }


class _FakeGitHub:
    def __init__(self, pulls: list[dict]) -> None:
        self.pulls = pulls

    def paginate(self, path: str) -> list[dict]:
        if path.startswith("/repos/imagent-ai/imagent/pulls?"):
            return self.pulls
        raise AssertionError(path)

    def issue_labels(self, number: int) -> set[str]:
        pull = next(item for item in self.pulls if item["number"] == number)
        return {label["name"] for label in pull["labels"]}
