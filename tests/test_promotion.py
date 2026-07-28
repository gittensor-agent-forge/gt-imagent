from __future__ import annotations

from competition.promotion import decide_match, disqualification_from_provenance
from imagent_scoring.judge import JudgeVerdict, JudgeVote
from imagent_scoring.ladder import SideResult, decide_problem


def _side(fact: float = 0.9, *, valid: bool = True, preference: float | None = None, error: str = ""):
    return SideResult(valid=valid, fact_score=fact, preference=preference, error=error)


def _judge(winner: str) -> JudgeVerdict:
    return JudgeVerdict(
        winner=winner,  # type: ignore[arg-type]
        challenger_slot="A",
        votes=(JudgeVote(raw="A", slot="A", winner=winner),) * 3,  # type: ignore[arg-type]
    )


# --- the match --------------------------------------------------------------


def _match(pattern: str, king_fact: float = 0.9, challenger_fact: float = 0.9, **kwargs):
    """pattern: 'c' challenger win, 'k' king win, 't' tie."""
    verdicts = [
        decide_problem(
            problem_id=f"p{index}",
            king=_side(king_fact),
            challenger=_side(challenger_fact),
            judge=_judge({"c": "challenger", "k": "king", "t": "tie"}[mark]),
        )
        for index, mark in enumerate(pattern)
    ]
    return decide_match(verdicts, **kwargs)


def test_a_clear_win_promotes() -> None:
    verdict = _match("cccckkk")

    assert verdict.wins == 4 and verdict.losses == 3
    assert not verdict.promoted  # margin of 1 is inside the noise

    verdict = _match("ccccckk")
    assert verdict.margin == 3
    assert verdict.promoted


def test_a_one_win_margin_does_not_promote() -> None:
    verdict = _match("cccckkk")

    assert not verdict.promoted
    assert any("below the required margin" in reason for reason in verdict.reasons)


def test_ties_count_for_the_king() -> None:
    # Five ties and one win each: the incumbent keeps the crown.
    verdict = _match("cktttt")

    assert verdict.wins == 1 and verdict.losses == 1 and verdict.ties == 4
    assert not verdict.promoted


def test_a_winning_record_still_fails_on_fact_regression() -> None:
    # Prettier images, worse instruction-following. This is exactly the trade the
    # gate exists to refuse.
    verdict = _match("ccccckk", king_fact=0.95, challenger_fact=0.80)

    assert verdict.margin == 3
    assert not verdict.promoted
    assert any("regressed" in reason for reason in verdict.reasons)


def test_a_small_fact_regression_is_tolerated() -> None:
    verdict = _match("ccccckk", king_fact=0.92, challenger_fact=0.90)

    assert verdict.promoted


def test_a_disqualification_ends_the_match_regardless_of_score() -> None:
    verdict = _match("ccccccc", disqualification="agent requested a non-pinned model")

    assert verdict.wins == 7
    assert not verdict.promoted
    assert verdict.reasons[0].startswith("disqualified:")


def test_an_empty_match_never_promotes() -> None:
    verdict = decide_match([])

    assert not verdict.promoted
    assert "no problems were decided" in verdict.reasons


def test_the_match_serialises_for_publication() -> None:
    payload = _match("ccccckk").to_dict()

    assert payload["promoted"] is True
    assert payload["wins"] == 5
    assert len(payload["problems"]) == 7
    assert payload["problems"][0]["judge"]["challenger_slot"] == "A"


# --- disqualification from attested provenance ------------------------------


def test_a_model_substitution_disqualifies() -> None:
    reason = disqualification_from_provenance(
        {
            "inference_policy": {
                "model_substitutions": 2,
                "requested_models": ["google/gemini-3-pro-image"],
                "statuses": {},
            }
        }
    )

    assert reason is not None
    assert "google/gemini-3-pro-image" in reason


def test_an_honest_run_is_not_disqualified() -> None:
    assert (
        disqualification_from_provenance(
            {"inference_policy": {"model_substitutions": 0, "statuses": {"ok": 12}}}
        )
        is None
    )


def test_an_exhausted_miner_key_is_the_miner_s_problem() -> None:
    reason = disqualification_from_provenance(
        {"inference_policy": {"model_substitutions": 0, "statuses": {"payment_required": 4}}}
    )

    assert reason is not None
    assert "credit" in reason


def test_missing_provenance_is_treated_as_a_failure_not_a_pass() -> None:
    assert disqualification_from_provenance({}) is not None
