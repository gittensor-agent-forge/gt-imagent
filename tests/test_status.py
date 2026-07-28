from __future__ import annotations

import json
from pathlib import Path

import pytest

from competition.lifecycle import PENDING, RUNNING, Submission
from competition.ranking import append_match
from competition.status import (
    KingError,
    crown,
    install_agent,
    load_king,
    record_defense,
    status,
)


def _bundle(tmp_path: Path, name: str = "alice-20260727-01") -> Path:
    bundle = tmp_path / "submissions" / name
    bundle.mkdir(parents=True)
    (bundle / "agent.yaml").write_text("entrypoint: agent:ImageAgent\n", encoding="utf-8")
    (bundle / "agent.py").write_text("class ImageAgent:\n    pass\n", encoding="utf-8")
    return bundle


def _crown(tmp_path: Path, agent_id: str, crowned_at: str, bundle: Path, challenge: str = "c1"):
    return crown(
        agent_id=agent_id,
        submission=7,
        commit_sha="a" * 40,
        crowned_at=crowned_at,
        challenge_id=challenge,
        bundle_dir=bundle,
        path=tmp_path / "kings" / "current.json",
        agent_dir=tmp_path / "kings" / "current",
    )


# --- installing the winning agent -------------------------------------------


def test_the_winning_bundle_is_copied_in_full(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "helpers.py").write_text("HELPER = 1\n", encoding="utf-8")
    target = tmp_path / "kings" / "current"

    installed = install_agent(bundle, target)

    assert sorted(installed) == ["agent.py", "agent.yaml", "helpers.py"]
    assert (target / "agent.py").read_text() == "class ImageAgent:\n    pass\n"
    assert (target / "helpers.py").read_text() == "HELPER = 1\n"


def test_nested_files_survive_the_copy(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "lib").mkdir()
    (bundle / "lib" / "planner.py").write_text("PLAN = 2\n", encoding="utf-8")
    target = tmp_path / "kings" / "current"

    install_agent(bundle, target)

    assert (target / "lib" / "planner.py").read_text() == "PLAN = 2\n"


def test_the_miners_sealed_key_is_not_carried_into_the_crown(tmp_path: Path) -> None:
    # It is bound to their submission and paid for by them. Copying it would bill
    # every future defence to whoever last won.
    bundle = _bundle(tmp_path)
    (bundle / "sealed_inference_key").write_text("04deadbeef\n", encoding="utf-8")
    target = tmp_path / "kings" / "current"

    installed = install_agent(bundle, target)

    assert "sealed_inference_key" not in installed
    assert not (target / "sealed_inference_key").exists()


def test_build_droppings_are_not_carried_in(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    cache = bundle / "__pycache__"
    cache.mkdir()
    (cache / "agent.cpython-312.pyc").write_bytes(b"\x00")

    installed = install_agent(bundle, tmp_path / "kings" / "current")

    assert all("__pycache__" not in name for name in installed)


def test_installing_replaces_the_previous_king_completely(tmp_path: Path) -> None:
    # A leftover file from the old king would be loaded alongside the new one.
    first = _bundle(tmp_path, "alice-1")
    (first / "old_helper.py").write_text("x = 1\n", encoding="utf-8")
    target = tmp_path / "kings" / "current"
    install_agent(first, target)

    second = _bundle(tmp_path, "bob-1")
    install_agent(second, target)

    assert not (target / "old_helper.py").exists()
    assert (target / "agent.yaml").is_file()


def test_a_bundle_without_a_manifest_is_refused(tmp_path: Path) -> None:
    bundle = tmp_path / "broken"
    bundle.mkdir()
    (bundle / "agent.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(KingError, match="no agent.yaml"):
        install_agent(bundle, tmp_path / "kings" / "current")


def test_a_symlink_is_refused_and_leaves_the_crown_untouched(tmp_path: Path) -> None:
    good = _bundle(tmp_path, "good")
    target = tmp_path / "kings" / "current"
    install_agent(good, target)

    bad = _bundle(tmp_path, "bad")
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    (bad / "link.txt").symlink_to(tmp_path / "outside.txt")

    with pytest.raises(KingError, match="regular files"):
        install_agent(bad, target)

    # The staged copy was discarded; the reigning agent is still there.
    assert (target / "agent.yaml").is_file()
    assert not (target.parent / ".current.incoming").exists()


# --- the reign record -------------------------------------------------------


def test_there_is_no_king_before_the_first_crowning(tmp_path: Path) -> None:
    assert load_king(tmp_path / "current.json") is None


def test_crowning_installs_the_code_and_records_the_reign(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    _crown(tmp_path, "agent-1", "2026-07-01T00:00:00Z", bundle)

    king = load_king(tmp_path / "kings" / "current.json")
    assert king is not None
    assert king.agent_id == "agent-1"
    assert king.defenses == 0
    # The crown is a full copy, not a pointer.
    assert (tmp_path / "kings" / "current" / "agent.py").is_file()


def test_a_defence_is_the_number_a_reign_is_measured_in(tmp_path: Path) -> None:
    king = _crown(tmp_path, "agent-1", "2026-07-01T00:00:00Z", _bundle(tmp_path))
    path = tmp_path / "kings" / "current.json"

    king = record_defense(king, "c2", path=path)
    king = record_defense(king, "c3", path=path)

    reloaded = load_king(path)
    assert reloaded.defenses == 2
    assert reloaded.challenges == ("c1", "c2", "c3")


def test_crowning_a_successor_replaces_both_code_and_record(tmp_path: Path) -> None:
    _crown(tmp_path, "agent-1", "2026-07-01T00:00:00Z", _bundle(tmp_path, "alice-1"))

    second = _bundle(tmp_path, "bob-1")
    (second / "agent.py").write_text("class ImageAgent:\n    VERSION = 2\n", encoding="utf-8")
    _crown(tmp_path, "agent-2", "2026-07-05T00:00:00Z", second, challenge="c3")

    assert load_king(tmp_path / "kings" / "current.json").agent_id == "agent-2"
    assert "VERSION = 2" in (tmp_path / "kings" / "current" / "agent.py").read_text()


def test_a_corrupt_reign_record_is_loud(tmp_path: Path) -> None:
    path = tmp_path / "current.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(KingError, match="unreadable"):
        load_king(path)


def test_an_unversioned_reign_record_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "current.json"
    path.write_text(json.dumps({"agent_id": "x"}), encoding="utf-8")

    with pytest.raises(KingError, match="unsupported"):
        load_king(path)


# --- the status snapshot ----------------------------------------------------


def test_status_reports_the_crown_the_queue_and_the_standings(tmp_path: Path) -> None:
    _crown(tmp_path, "agent-1", "2026-07-01T00:00:00Z", _bundle(tmp_path))
    log = tmp_path / "matches.jsonl"
    append_match(
        log,
        challenge_id="c1",
        king_id="agent-1",
        challenger_id="chal-1",
        problem_winners={"p1": "king", "p2": "king", "p3": "challenger"},
    )

    snapshot = status(
        submissions=[
            Submission(4, "alice", labels=(PENDING,), created_at="2026-07-02"),
            Submission(9, "carol", labels=(PENDING,), created_at="2026-07-01"),
            Submission(2, "bob", labels=(RUNNING,)),
        ],
        king_path=tmp_path / "kings" / "current.json",
        agent_dir=tmp_path / "kings" / "current",
        match_log=log,
    )

    assert snapshot["king"]["agent_id"] == "agent-1"
    assert snapshot["king_agent_installed"] is True
    assert snapshot["queue"]["running"] == [2]
    # Oldest first, so the queue is a queue and not a lottery.
    assert snapshot["queue"]["pending"] == [9, 4]
    assert snapshot["queue"]["accepting"] is False
    assert {row["agent_id"] for row in snapshot["leaderboard"]} == {"agent-1", "chal-1"}


def test_a_reign_record_with_no_agent_beside_it_is_surfaced(tmp_path: Path) -> None:
    # A crown nobody can defend, discovered before a challenge rather than during.
    _crown(tmp_path, "agent-1", "2026-07-01T00:00:00Z", _bundle(tmp_path))
    (tmp_path / "kings" / "current" / "agent.yaml").unlink()

    snapshot = status(
        submissions=[],
        king_path=tmp_path / "kings" / "current.json",
        agent_dir=tmp_path / "kings" / "current",
    )

    assert snapshot["king"] is not None
    assert snapshot["king_agent_installed"] is False


def test_an_empty_competition_still_reports_cleanly(tmp_path: Path) -> None:
    snapshot = status(
        submissions=[], king_path=tmp_path / "none.json", agent_dir=tmp_path / "none"
    )

    assert snapshot["king"] is None
    assert snapshot["queue"]["accepting"] is True
    assert snapshot["leaderboard"] == []
