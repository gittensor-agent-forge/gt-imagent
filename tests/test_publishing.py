from __future__ import annotations

import hashlib
import json

import pytest

from competition.publishing import (
    LeakError,
    SideSummary,
    assert_no_prompt_leak,
    build_challenge_report,
    verify_image_hashes,
)

PROMPTS = {
    "p1": "a photo of three cakes",
    "p2": 'a photo of a blue sign with the word "MERIDIAN" written on it',
}


def _side(role: str, agent_id: str, score: float = 0.9) -> SideSummary:
    return SideSummary(
        agent_id=agent_id,
        role=role,
        fact_reports={
            problem_id: {"problem_id": problem_id, "fact_score": score, "checks": []}
            for problem_id in PROMPTS
        },
        image_hashes={
            problem_id: hashlib.sha256(f"{agent_id}:{problem_id}".encode()).hexdigest()
            for problem_id in PROMPTS
        },
        attestation={"quote": "0xdeadbeef", "measurement": "sha256:room"},
    )


def _report(**overrides):
    kwargs = {
        "challenge_id": "9f2c1ab3",
        "seed": b"\x01" * 32,
        "versions": {"generator": "imagent-problems-v1.0.0", "scoring": "scoring-v1.0.0"},
        "sides": [_side("king", "king-1", 0.92), _side("challenger", "chal-1", 0.88)],
        "match": {"promoted": False, "wins": 2, "losses": 3, "ties": 2},
        "judge_verdicts": {"p1": {"winner": "king", "challenger_slot": "B"}},
        "prompts": PROMPTS,
    }
    kwargs.update(overrides)
    return build_challenge_report(**kwargs)


# --- the leak guard, which is the whole point -------------------------------


def test_no_raw_prompt_survives_into_a_published_report() -> None:
    serialised = json.dumps(_report())

    for prompt in PROMPTS.values():
        assert prompt not in serialised


def test_prompts_appear_as_hashes() -> None:
    report = _report()

    assert report["problems"][0]["prompt_sha256"] == hashlib.sha256(
        PROMPTS["p1"].encode()
    ).hexdigest()


def test_a_leaked_prompt_is_caught_before_publication() -> None:
    # Publishing one report would burn the problem it came from, so this is
    # checked every time rather than trusted.
    leaky = {"notes": "the prompt was: a photo of three cakes"}

    with pytest.raises(LeakError, match="raw prompt"):
        assert_no_prompt_leak(leaky, PROMPTS.values())


def test_the_guard_ignores_short_incidental_strings() -> None:
    # A one-word prompt would match half the document by accident; the guard only
    # asserts on strings long enough to be a real prompt.
    assert_no_prompt_leak({"winner": "king"}, ["king", "tie"])


# --- report shape -----------------------------------------------------------


def test_the_seed_is_published_as_a_receipt() -> None:
    report = _report()

    # Not the seed itself: publishing it before the pool rotates would regenerate
    # every problem in the challenge.
    assert report["seed_sha256"] == hashlib.sha256(b"\x01" * 32).hexdigest()
    assert "seed" not in report


def test_every_side_is_recorded_per_problem() -> None:
    report = _report()
    first = report["problems"][0]

    assert set(first["sides"]) == {"king", "challenger"}
    assert first["sides"]["king"]["agent_id"] == "king-1"
    assert first["sides"]["king"]["facts"]["fact_score"] == 0.92
    assert first["sides"]["challenger"]["image_sha256"]


def test_the_baseline_control_can_be_published_alongside() -> None:
    report = _report(
        sides=[_side("king", "king-1"), _side("challenger", "chal-1"), _side("baseline", "direct")]
    )

    assert {agent["role"] for agent in report["agents"]} == {"king", "challenger", "baseline"}
    assert set(report["problems"][0]["sides"]) == {"king", "challenger", "baseline"}


def test_versions_are_recorded_so_a_verdict_can_be_reproduced() -> None:
    report = _report()

    assert report["versions"]["generator"] == "imagent-problems-v1.0.0"
    assert report["versions"]["scoring"] == "scoring-v1.0.0"


def test_the_attestation_travels_with_the_agent() -> None:
    report = _report()

    assert report["agents"][0]["attestation"]["measurement"] == "sha256:room"


def test_mean_fact_scores_are_summarised_per_agent() -> None:
    report = _report()

    assert report["agents"][0]["mean_fact_score"] == pytest.approx(0.92)
    assert report["agents"][1]["mean_fact_score"] == pytest.approx(0.88)


def test_the_report_is_deterministic() -> None:
    assert json.dumps(_report(), sort_keys=True) == json.dumps(_report(), sort_keys=True)


# --- image verification -----------------------------------------------------


def test_matching_bytes_verify() -> None:
    payloads = {"p1": b"first-image", "p2": b"second-image"}
    attested = {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}

    assert verify_image_hashes(payloads, attested) == []


def test_swapped_bytes_are_caught() -> None:
    attested = {"p1": hashlib.sha256(b"original").hexdigest()}

    assert verify_image_hashes({"p1": b"substituted"}, attested) == ["p1"]


def test_a_missing_image_is_caught() -> None:
    attested = {"p1": hashlib.sha256(b"x").hexdigest(), "p2": hashlib.sha256(b"y").hexdigest()}

    assert verify_image_hashes({"p1": b"x"}, attested) == ["p2"]


def test_an_unattested_extra_image_is_caught() -> None:
    # An extra image is an image nobody signed for.
    attested = {"p1": hashlib.sha256(b"x").hexdigest()}

    assert verify_image_hashes({"p1": b"x", "p9": b"smuggled"}, attested) == ["p9"]
