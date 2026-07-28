from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from competition.challenge import (
    ChallengeAborted,
    RoomRun,
    ScoringStack,
    grade_side,
    issue_challenge,
    run_challenge,
    verify_run,
)
from competition.screening import screen_submission
from imagent_scoring import Detection, TextSpan
from imagent_scoring.imaging import ImageData

MEASUREMENT = "sha256:approved-room"


# --- stub backends ----------------------------------------------------------


class _Loader:
    def load(self, path: Path, *, max_edge=None) -> ImageData:
        # A deterministic non-blank image whose content depends on the file, so
        # two agents never collide on the duplicate check.
        base = path.read_bytes()[:1] or b"\x00"
        pixels = tuple(
            ((x * 7 + base[0]) % 256, (y * 11) % 256, (x + y) % 256)
            for y in range(64)
            for x in range(64)
        )
        return ImageData(width=64, height=64, pixels=pixels)

    def size(self, path: Path) -> tuple[int, int]:
        return (64, 64)


class _Detector:
    """Finds whatever the answer key asked for, minus a configurable shortfall."""

    def __init__(self, agent_scores: dict[str, float]) -> None:
        self.agent_scores = agent_scores

    def detect(self, path: Path) -> list[Detection]:
        agent = path.name.split("-")[0]
        quality = self.agent_scores.get(agent, 1.0)
        found = []
        for index in range(4 if quality > 0.5 else 1):
            found.append(
                Detection(
                    label=f"object{index}",
                    box=(index * 20, 0, index * 20 + 10, 10),
                    color="yellow",
                )
            )
        return found


class _Ocr:
    def read(self, path: Path) -> list[TextSpan]:
        return [TextSpan(text="MERIDIAN ANCHOR PRISM")]


class _Vqa:
    def __init__(self, answer: str = "yes") -> None:
        self.answer = answer

    def answer(self, path: Path, question: str) -> str:
        return self.answer


class _Judge:
    def __init__(self, pick: str = "A") -> None:
        self.pick = pick
        self.calls = 0

    def compare(self, **kwargs) -> str:
        self.calls += 1
        return self.pick


class _Room:
    """A sealed room that answers every problem with agent-specific bytes."""

    def __init__(
        self,
        *,
        fail_for: str = "",
        substitute_model_for: str = "",
        skip_for: dict[str, set[str]] | None = None,
    ) -> None:
        self.fail_for = fail_for
        self.substitute_model_for = substitute_model_for
        # Which problems a given agent fails to answer at all.
        self.skip_for = skip_for or {}

    def run(self, *, challenge_id: str, agent_id: str, nonce: str) -> RoomRun:
        if agent_id == self.fail_for:
            raise RuntimeError("room unreachable")

        from imagent_bench.problems import generate_problems

        seed = hashlib.sha256(f"imagent-challenge-v1:{challenge_id}".encode()).digest()
        problems = generate_problems(seed)
        skipped = self.skip_for.get(agent_id, set())
        images = {
            problem.problem_id: f"{agent_id}:{problem.problem_id}".encode()
            for problem in problems
            if problem.problem_id not in skipped and "all" not in skipped
        }
        return RoomRun(
            agent_id=agent_id,
            report={
                "challenge_id": challenge_id,
                "problems": [
                    {
                        "problem_id": problem_id,
                        "image_sha256": hashlib.sha256(payload).hexdigest(),
                    }
                    for problem_id, payload in images.items()
                ],
            },
            images=images,
            provenance={
                "inference_policy": {
                    "model_substitutions": 3 if agent_id == self.substitute_model_for else 0,
                    "requested_models": ["google/gemini-3-pro-image"]
                    if agent_id == self.substitute_model_for
                    else [],
                    "statuses": {"ok": 21},
                }
            },
            quote="0xquote",
            measurement=MEASUREMENT,
        )


def _stack(judge_pick: str = "A", scores: dict[str, float] | None = None) -> ScoringStack:
    return ScoringStack(
        loader=_Loader(),
        ocr=_Ocr(),
        detector=_Detector(scores or {}),
        vqa=_Vqa(),
        judge=_Judge(judge_pick),
    )


# --- screening --------------------------------------------------------------


def test_a_well_formed_submission_passes_screening() -> None:
    reasons = screen_submission(
        bundle_files={"agent.yaml": b"entrypoint: agent:A", "agent.py": b"class A: pass"},
        sealed_key="deadbeef",
        archived_hashes=set(),
    )

    assert reasons == []


def test_screening_rejects_a_submission_with_no_sealed_key() -> None:
    reasons = screen_submission(
        bundle_files={"agent.yaml": b"x", "agent.py": b"y"}, sealed_key="  ", archived_hashes=set()
    )

    assert any("sealed inference key" in reason for reason in reasons)


def test_screening_rejects_a_replayed_bundle() -> None:
    files = {"agent.yaml": b"x", "agent.py": b"y"}
    digest = hashlib.sha256(b"agent.py\x00y" + b"agent.yaml\x00x").hexdigest()

    reasons = screen_submission(
        bundle_files=files, sealed_key="ok", archived_hashes={digest}
    )

    assert any("byte-identical" in reason for reason in reasons)


def test_screening_rejects_an_oversized_bundle() -> None:
    reasons = screen_submission(
        bundle_files={"agent.yaml": b"x", "agent.py": b"z" * 300_000},
        sealed_key="ok",
        archived_hashes=set(),
    )

    assert any("limit is" in reason for reason in reasons)


# --- issuing ----------------------------------------------------------------


def test_each_challenge_is_unpredictable_and_self_consistent() -> None:
    first_id, first_seed, first_problems = issue_challenge()
    second_id, _, second_problems = issue_challenge()

    assert first_id != second_id
    assert len(first_problems) == 7
    assert first_seed == hashlib.sha256(f"imagent-challenge-v1:{first_id}".encode()).digest()
    assert {p.prompt for p in first_problems} != {p.prompt for p in second_problems}


# --- verification -----------------------------------------------------------


def _run(**overrides) -> RoomRun:
    payload = b"image-bytes"
    kwargs = {
        "agent_id": "a",
        "report": {
            "challenge_id": "c1",
            "problems": [{"problem_id": "p1", "image_sha256": hashlib.sha256(payload).hexdigest()}],
        },
        "images": {"p1": payload},
        "provenance": {},
        "quote": "0xquote",
        "measurement": MEASUREMENT,
    }
    kwargs.update(overrides)
    return RoomRun(**kwargs)


def test_a_verified_run_passes() -> None:
    verify_run(_run(), challenge_id="c1", allowed_measurements={MEASUREMENT})


def test_an_unallowlisted_room_image_aborts() -> None:
    with pytest.raises(ChallengeAborted, match="not allowlisted"):
        verify_run(_run(measurement="sha256:rogue"), challenge_id="c1", allowed_measurements={MEASUREMENT})


def test_a_run_without_a_quote_aborts() -> None:
    with pytest.raises(ChallengeAborted, match="no attestation quote"):
        verify_run(_run(quote=""), challenge_id="c1", allowed_measurements=set())


def test_a_report_for_another_challenge_aborts() -> None:
    with pytest.raises(ChallengeAborted, match="different challenge"):
        verify_run(_run(), challenge_id="c2", allowed_measurements=set())


def test_substituted_image_bytes_abort() -> None:
    run = _run(images={"p1": b"substituted"})

    with pytest.raises(ChallengeAborted, match="do not match the attested hashes"):
        verify_run(run, challenge_id="c1", allowed_measurements=set())


# --- grading ----------------------------------------------------------------


def test_a_missing_image_loses_its_problem_without_aborting(tmp_path: Path) -> None:
    # The agent had its chance and produced nothing. That is a lost problem, not
    # a failed challenge.
    challenge_id, _, problems = issue_challenge()
    room = _Room(skip_for={"a": {problems[0].problem_id}})
    run = room.run(challenge_id=challenge_id, agent_id="a", nonce="n")

    results, fact_reports = grade_side(run, problems, stack=_stack(), image_dir=tmp_path)

    assert not results[problems[0].problem_id].valid
    assert "produced no image" in results[problems[0].problem_id].error
    assert problems[0].problem_id not in fact_reports
    # The other six were still graded.
    assert sum(1 for result in results.values() if result.valid) == 6


# --- the whole challenge ----------------------------------------------------


def test_a_challenge_runs_end_to_end(tmp_path: Path) -> None:
    result = run_challenge(
        room=_Room(),
        king_id="king-1",
        challenger_id="chal-1",
        stack=_stack(),
        image_dir=tmp_path / "images",
        allowed_measurements={MEASUREMENT},
        match_log=tmp_path / "matches.jsonl",
    )

    assert result.challenge_id
    assert result.match["wins"] + result.match["losses"] + result.match["ties"] == 7
    assert len(result.report["problems"]) == 7
    assert result.leaderboard
    assert {row["agent_id"] for row in result.leaderboard} >= {"king-1", "chal-1"}


def test_the_published_report_never_carries_a_prompt(tmp_path: Path) -> None:
    import json

    result = run_challenge(
        room=_Room(),
        king_id="king-1",
        challenger_id="chal-1",
        stack=_stack(),
        image_dir=tmp_path / "images",
        allowed_measurements={MEASUREMENT},
    )
    seed = hashlib.sha256(f"imagent-challenge-v1:{result.challenge_id}".encode()).digest()

    from imagent_bench.problems import generate_problems

    serialised = json.dumps(result.report)
    for problem in generate_problems(seed):
        assert problem.prompt not in serialised


def test_a_model_substitution_disqualifies_the_challenger(tmp_path: Path) -> None:
    result = run_challenge(
        room=_Room(substitute_model_for="chal-1"),
        king_id="king-1",
        challenger_id="chal-1",
        stack=_stack(),
        image_dir=tmp_path / "images",
        allowed_measurements={MEASUREMENT},
    )

    assert not result.promoted
    assert result.match["reasons"][0].startswith("disqualified:")


def test_a_room_failure_aborts_instead_of_blaming_the_miner(tmp_path: Path) -> None:
    # The distinction the whole competition rests on: infrastructure failing must
    # not be recorded as an agent losing.
    with pytest.raises(ChallengeAborted, match="challenger run failed"):
        run_challenge(
            room=_Room(fail_for="chal-1"),
            king_id="king-1",
            challenger_id="chal-1",
            stack=_stack(),
            image_dir=tmp_path / "images",
            allowed_measurements={MEASUREMENT},
        )


def test_a_baseline_failure_does_not_cost_the_duel(tmp_path: Path) -> None:
    result = run_challenge(
        room=_Room(fail_for="direct-baseline"),
        king_id="king-1",
        challenger_id="chal-1",
        stack=_stack(),
        image_dir=tmp_path / "images",
        allowed_measurements={MEASUREMENT},
    )

    assert result.match["wins"] + result.match["losses"] + result.match["ties"] == 7
    assert {agent["role"] for agent in result.report["agents"]} == {"king", "challenger"}


def test_the_judge_is_paid_once_per_vote_when_both_sides_answer(tmp_path: Path) -> None:
    stack = _stack()

    run_challenge(
        room=_Room(),
        king_id="king-1",
        challenger_id="chal-1",
        stack=stack,
        image_dir=tmp_path / "images",
        allowed_measurements={MEASUREMENT},
    )

    # Seven problems, three votes each, both sides valid throughout.
    assert stack.judge.calls == 21


def test_no_judge_is_paid_when_a_side_produced_nothing(tmp_path: Path) -> None:
    # Nothing to compare, so the comparison is never bought. Judge calls cost
    # money, and a missing image already decides the problem by the validity rule.
    stack = _stack()

    result = run_challenge(
        room=_Room(skip_for={"chal-1": {"all"}}),
        king_id="king-1",
        challenger_id="chal-1",
        stack=stack,
        image_dir=tmp_path / "images",
        allowed_measurements={MEASUREMENT},
    )

    assert stack.judge.calls == 0
    assert result.match["losses"] == 7
    assert not result.promoted
