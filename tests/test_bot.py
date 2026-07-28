from __future__ import annotations

import json
from pathlib import Path

import pytest

from competition import bot
from competition.lifecycle import DEFEATED, INVALID, KING, PENDING, RUNNING, Submission
from competition.status import load_king


class _FakeClient:
    """Records the plan instead of calling GitHub."""

    def __init__(self, submissions: list[Submission] | None = None) -> None:
        self.submissions = submissions or []
        self.applied: list = []

    def list_submissions(self, *, label: str = "") -> list[Submission]:
        if not label:
            return list(self.submissions)
        return [item for item in self.submissions if label in item.labels]

    def apply(self, actions) -> list[str]:
        self.applied.extend(actions)
        return [action.describe() for action in actions]


@pytest.fixture
def client(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(bot, "_client", lambda args: fake)
    return fake


def _bundle(tmp_path: Path, name: str = "alice-20260727-01", *, sealed: str = "04deadbeef") -> Path:
    directory = tmp_path / "submissions" / name
    directory.mkdir(parents=True)
    (directory / "agent.yaml").write_text("entrypoint: agent:ImageAgent\n", encoding="utf-8")
    (directory / "agent.py").write_text("class ImageAgent:\n    pass\n", encoding="utf-8")
    if sealed:
        (directory / "sealed_inference_key").write_text(sealed + "\n", encoding="utf-8")
    return directory


def _kinds(actions) -> list[tuple[str, int, str]]:
    return [(action.kind, action.pull_request, action.value) for action in actions]


# --- reading a submission ----------------------------------------------------


def test_the_sealed_key_is_read_apart_from_the_bundle(tmp_path: Path) -> None:
    # Including it among the hashed files would make every binding
    # self-referential.
    files, sealed = bot.read_bundle(_bundle(tmp_path))

    assert set(files) == {"agent.yaml", "agent.py"}
    assert sealed == "04deadbeef"


def test_nested_bundle_files_are_read(tmp_path: Path) -> None:
    directory = _bundle(tmp_path)
    (directory / "lib").mkdir()
    (directory / "lib" / "planner.py").write_text("x = 1\n", encoding="utf-8")

    files, _ = bot.read_bundle(directory)

    assert "lib/planner.py" in files


# --- screen: untrusted, decides but never acts -------------------------------


def test_screening_a_good_submission_writes_a_passing_verdict(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    out = tmp_path / "verdict.json"

    code = bot.main(
        ["screen", "--pr", "7", "--author", "alice", "--bundle", str(bundle), "--out", str(out)]
    )

    verdict = json.loads(out.read_text())
    assert code == 0
    assert verdict["passed"] is True
    assert verdict["reasons"] == []
    assert verdict["pull_request"] == 7


def test_screening_a_bad_submission_still_exits_zero(tmp_path: Path) -> None:
    # A rejected submission is a normal outcome. A red X tells a miner less than
    # the comment the bot is about to leave.
    bundle = _bundle(tmp_path, sealed="")
    out = tmp_path / "verdict.json"

    code = bot.main(
        ["screen", "--pr", "7", "--author", "alice", "--bundle", str(bundle), "--out", str(out)]
    )

    verdict = json.loads(out.read_text())
    assert code == 0
    assert verdict["passed"] is False
    assert any("sealed inference key" in reason for reason in verdict["reasons"])


def test_screening_never_touches_github(tmp_path: Path, monkeypatch) -> None:
    # This command runs with a fork's code on disk. If it could reach GitHub it
    # would be holding write access next to untrusted code.
    def explode(args):
        raise AssertionError("screening must not construct a GitHub client")

    monkeypatch.setattr(bot, "_client", explode)
    bundle = _bundle(tmp_path)

    bot.main(
        [
            "screen", "--pr", "7", "--author", "alice",
            "--bundle", str(bundle), "--out", str(tmp_path / "v.json"),
        ]
    )


def test_a_replayed_bundle_is_caught_against_the_archive(tmp_path: Path) -> None:
    import hashlib

    bundle = _bundle(tmp_path)
    files, _ = bot.read_bundle(bundle)
    digest = hashlib.sha256(
        b"".join(name.encode() + b"\x00" + files[name] for name in sorted(files))
    ).hexdigest()
    archive = tmp_path / "archived.txt"
    archive.write_text(digest + "\n", encoding="utf-8")
    out = tmp_path / "verdict.json"

    bot.main(
        [
            "screen", "--pr", "7", "--author", "alice", "--bundle", str(bundle),
            "--archive", str(archive), "--out", str(out),
        ]
    )

    assert any("byte-identical" in reason for reason in json.loads(out.read_text())["reasons"])


# --- apply: trusted, acts on a verdict ---------------------------------------


def _verdict(tmp_path: Path, *, passed: bool, reasons: list[str] | None = None) -> Path:
    path = tmp_path / "verdict.json"
    path.write_text(
        json.dumps(
            {
                "version": bot.VERDICT_VERSION,
                "pull_request": 7,
                "author": "alice",
                "bundle_dir": "submissions/alice-1",
                "passed": passed,
                "reasons": reasons or [],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_a_passing_verdict_queues_the_challenger(tmp_path: Path, client) -> None:
    bot.main(["apply", "--verdict", str(_verdict(tmp_path, passed=True))])

    kinds = _kinds(client.applied)
    assert ("label", 7, PENDING) in kinds
    assert ("close", 7, "") not in kinds


def test_a_failing_verdict_closes_the_pull_request_with_the_reason(tmp_path: Path, client) -> None:
    verdict = _verdict(tmp_path, passed=False, reasons=["bundle is missing agent.yaml"])

    bot.main(["apply", "--verdict", str(verdict)])

    kinds = _kinds(client.applied)
    assert ("label", 7, INVALID) in kinds
    assert ("close", 7, "") in kinds
    comment = next(action for action in client.applied if action.kind == "comment")
    assert "missing agent.yaml" in comment.value


def test_apply_enforces_one_open_submission_per_author(tmp_path: Path, client) -> None:
    client.submissions = [Submission(4, "alice"), Submission(7, "alice")]

    bot.main(["apply", "--verdict", str(_verdict(tmp_path, passed=True))])

    kinds = _kinds(client.applied)
    assert ("label", 7, INVALID) in kinds


def test_an_unversioned_verdict_is_refused(tmp_path: Path, client) -> None:
    path = tmp_path / "verdict.json"
    path.write_text(json.dumps({"version": "something-else"}), encoding="utf-8")

    with pytest.raises(SystemExit, match="unsupported verdict"):
        bot.main(["apply", "--verdict", str(path)])


# --- tick: start one duel ----------------------------------------------------


def test_tick_starts_the_oldest_waiting_challenger(tmp_path: Path, client) -> None:
    client.submissions = [
        Submission(9, "carol", labels=(PENDING,), created_at="2026-07-03"),
        Submission(4, "alice", labels=(PENDING,), created_at="2026-07-01"),
    ]
    out = tmp_path / "started.json"

    bot.main(["tick", "--out", str(out)])

    assert ("label", 4, RUNNING) in _kinds(client.applied)
    assert json.loads(out.read_text())["started"] == 4


def test_tick_starts_nothing_while_a_duel_runs(tmp_path: Path, client) -> None:
    client.submissions = [
        Submission(4, "alice", labels=(PENDING,)),
        Submission(2, "bob", labels=(RUNNING,)),
    ]
    out = tmp_path / "started.json"

    bot.main(["tick", "--out", str(out)])

    assert client.applied == []
    assert json.loads(out.read_text())["started"] is None


def test_tick_on_an_empty_queue_is_not_an_error(tmp_path: Path, client) -> None:
    out = tmp_path / "started.json"

    assert bot.main(["tick", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["started"] is None


# --- resolve: crown, then announce -------------------------------------------


def _outcome(tmp_path: Path, bundle: Path, **overrides) -> Path:
    payload = {
        "pull_request": 7,
        "author": "alice",
        "promoted": True,
        "agent_id": "alice-agent",
        "commit_sha": "b" * 40,
        "challenge_id": "c1",
        "bundle_dir": str(bundle),
        "match": {"wins": 5, "losses": 2, "ties": 0, "margin": 3, "reasons": []},
    }
    payload.update(overrides)
    path = tmp_path / "outcome.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _resolve_args(tmp_path: Path, outcome: Path) -> list[str]:
    return [
        "resolve",
        "--outcome", str(outcome),
        "--king-path", str(tmp_path / "kings" / "current.json"),
        "--king-agent-dir", str(tmp_path / "kings" / "current"),
    ]


def test_a_promotion_installs_the_crown_and_merges(tmp_path: Path, client) -> None:
    bundle = _bundle(tmp_path)
    outcome = _outcome(tmp_path, bundle)

    bot.main(_resolve_args(tmp_path, outcome))

    king = load_king(tmp_path / "kings" / "current.json")
    assert king.agent_id == "alice-agent"
    # The crown is a full copy of the winning code.
    assert (tmp_path / "kings" / "current" / "agent.py").is_file()
    kinds = _kinds(client.applied)
    assert ("label", 7, KING) in kinds
    assert ("merge", 7, "") in kinds


def test_the_crown_is_installed_before_it_is_announced(tmp_path: Path, client, monkeypatch) -> None:
    # A comment saying "you are the new king" beside a crown that was never
    # installed is the one inconsistency a miner would be right to distrust.
    order: list[str] = []
    real_crown = bot.crown
    monkeypatch.setattr(
        bot, "crown", lambda **kwargs: (order.append("crown"), real_crown(**kwargs))[1]
    )

    fake_apply = client.apply

    def recording_apply(actions):
        order.append("announce")
        return fake_apply(actions)

    client.apply = recording_apply
    bot.main(_resolve_args(tmp_path, _outcome(tmp_path, _bundle(tmp_path))))

    assert order == ["crown", "announce"]


def test_a_defeat_closes_without_touching_the_crown(tmp_path: Path, client) -> None:
    outcome = _outcome(
        tmp_path,
        _bundle(tmp_path),
        promoted=False,
        match={"wins": 2, "losses": 3, "ties": 2, "margin": -1, "reasons": ["net wins -1 is below the required margin of 2"]},
    )

    bot.main(_resolve_args(tmp_path, outcome))

    kinds = _kinds(client.applied)
    assert ("label", 7, DEFEATED) in kinds
    assert ("close", 7, "") in kinds
    assert not (tmp_path / "kings" / "current.json").exists()


def test_an_aborted_duel_requeues_and_crowns_nobody(tmp_path: Path, client) -> None:
    outcome = _outcome(
        tmp_path, _bundle(tmp_path), promoted=False, aborted="room unreachable for chal-1"
    )

    bot.main(_resolve_args(tmp_path, outcome))

    kinds = _kinds(client.applied)
    assert ("label", 7, PENDING) in kinds
    assert ("close", 7, "") not in kinds
    assert not (tmp_path / "kings" / "current.json").exists()


def test_a_promotion_dethrones_the_previous_king(tmp_path: Path, client) -> None:
    client.submissions = [Submission(3, "bob", labels=(KING,)), Submission(7, "alice", labels=(RUNNING,))]
    # An existing reign, whose pull request the bot must find and relabel.
    from competition.status import crown as install

    install(
        agent_id="bob-agent",
        submission=3,
        commit_sha="a" * 40,
        crowned_at="2026-07-01T00:00:00Z",
        challenge_id="c0",
        bundle_dir=_bundle(tmp_path, "bob-1"),
        path=tmp_path / "kings" / "current.json",
        agent_dir=tmp_path / "kings" / "current",
    )

    bot.main(_resolve_args(tmp_path, _outcome(tmp_path, _bundle(tmp_path, "alice-2"))))

    kinds = _kinds(client.applied)
    assert ("label", 3, "king:past") in kinds
    assert ("label", 7, KING) in kinds
