from __future__ import annotations

from pathlib import Path

import pytest

from competition.ranking import (
    BASE_RATING,
    Comparison,
    append_match,
    build_leaderboard,
    fit_bradley_terry,
    load_comparisons,
    rank,
    to_rating,
)


def _duel(left: str, right: str, pattern: str) -> list[Comparison]:
    """pattern: 'l' left wins, 'r' right wins, 't' tie."""
    return [
        Comparison(
            left=left,
            right=right,
            winner={"l": "left", "r": "right", "t": "tie"}[mark],
            problem_id=f"p{index}",
        )
        for index, mark in enumerate(pattern)
    ]


# --- the model ---------------------------------------------------------------


def test_the_stronger_agent_gets_the_higher_strength() -> None:
    strengths = fit_bradley_terry(_duel("alice", "bob", "lllllr"))

    assert strengths["alice"] > strengths["bob"]


def test_two_equal_agents_land_on_the_same_rating() -> None:
    ratings = {item.agent_id: item.rating for item in rank(_duel("a", "b", "lrlrlr"), bootstrap=50)}

    assert ratings["a"] == pytest.approx(ratings["b"], abs=1e-6)
    assert ratings["a"] == pytest.approx(BASE_RATING, abs=1e-6)


def test_three_to_one_odds_are_about_190_rating_points() -> None:
    # 400 points is 10:1 by construction, so 3:1 should be 400*log10(3) ≈ 190.8.
    # This pins the scale: if it drifts, every published rating changes meaning.
    ratings = {item.agent_id: item.rating for item in rank(_duel("a", "b", "lllr" * 25), bootstrap=0)}

    assert ratings["a"] - ratings["b"] == pytest.approx(190.8, abs=6.0)


def test_ordering_does_not_change_the_result() -> None:
    # The reason this is not Elo: a rating that depends on match order would let
    # the scheduler decide the leaderboard.
    forward = _duel("a", "b", "llrl") + _duel("b", "c", "lrll")
    backward = list(reversed(forward))

    assert fit_bradley_terry(forward) == pytest.approx(fit_bradley_terry(backward))


def test_ties_pull_two_agents_together() -> None:
    decisive = rank(_duel("a", "b", "llll"), bootstrap=0)
    with_ties = rank(_duel("a", "b", "lltt"), bootstrap=0)

    gap_decisive = decisive[0].rating - decisive[1].rating
    gap_with_ties = with_ties[0].rating - with_ties[1].rating

    assert 0 < gap_with_ties < gap_decisive


def test_an_undefeated_newcomer_does_not_get_an_infinite_rating() -> None:
    # Without the prior this agent's strength diverges and it tops the board on
    # one lucky problem.
    ratings = rank(_duel("newcomer", "veteran", "l"), bootstrap=0)

    assert all(abs(item.rating) < 10_000 for item in ratings)
    assert ratings[0].agent_id == "newcomer"


def test_transitivity_is_inferred_across_opponents() -> None:
    # a and c never meet, but a beats b and b beats c.
    comparisons = _duel("a", "b", "llllr") + _duel("b", "c", "llllr")

    ratings = {item.agent_id: item.rating for item in rank(comparisons, bootstrap=0)}

    assert ratings["a"] > ratings["b"] > ratings["c"]


def test_an_empty_history_ranks_nobody() -> None:
    assert rank([]) == []
    assert fit_bradley_terry([]) == {}


def test_a_comparison_needs_two_different_agents() -> None:
    with pytest.raises(ValueError, match="two different agents"):
        Comparison(left="a", right="a", winner="tie")

    with pytest.raises(ValueError, match="winner must be"):
        Comparison(left="a", right="b", winner="maybe")


# --- confidence intervals ----------------------------------------------------


def test_intervals_are_reproducible_from_the_same_log() -> None:
    # A published bound that shifted on every page render would be worthless.
    comparisons = _duel("a", "b", "llrllr")

    first = rank(comparisons, bootstrap=100)
    second = rank(comparisons, bootstrap=100)

    assert [item.to_dict() for item in first] == [item.to_dict() for item in second]


def test_more_evidence_narrows_the_interval() -> None:
    thin = rank(_duel("a", "b", "llr"), bootstrap=200)[0]
    thick = rank(_duel("a", "b", "llr" * 30), bootstrap=200)[0]

    assert (thick.high - thick.low) < (thin.high - thin.low)


def test_the_point_estimate_sits_inside_its_interval() -> None:
    for item in rank(_duel("a", "b", "llrllr"), bootstrap=200):
        assert item.low <= item.rating <= item.high


def test_agents_that_cannot_be_told_apart_are_flagged() -> None:
    # Two problems is nowhere near enough evidence to separate anyone.
    rows = build_leaderboard(rank(_duel("a", "b", "lr"), bootstrap=200))

    assert rows[0]["rank"] == 1
    assert rows[1]["indistinguishable_from_previous"] is True


def test_a_decisive_history_separates_them() -> None:
    rows = build_leaderboard(rank(_duel("a", "b", "l" * 40 + "r" * 2), bootstrap=200))

    assert rows[1]["indistinguishable_from_previous"] is False


# --- the permanent log -------------------------------------------------------


def test_a_duel_is_recorded_as_one_comparison_per_problem(tmp_path: Path) -> None:
    log = tmp_path / "matches.jsonl"
    append_match(
        log,
        challenge_id="c1",
        king_id="king-1",
        challenger_id="chal-1",
        problem_winners={"p1": "challenger", "p2": "king", "p3": "tie"},
    )

    comparisons = load_comparisons(log)

    # Seven problems must not collapse into a single win: that would discard most
    # of what the challenge paid for.
    assert len(comparisons) == 3
    assert comparisons[0].winner == "right"  # challenger sits on the right
    assert comparisons[1].winner == "left"
    assert comparisons[2].winner == "tie"
    assert comparisons[0].challenge_id == "c1"


def test_the_log_is_append_only_across_challenges(tmp_path: Path) -> None:
    log = tmp_path / "matches.jsonl"
    append_match(log, challenge_id="c1", king_id="k", challenger_id="a", problem_winners={"p1": "king"})
    append_match(log, challenge_id="c2", king_id="k", challenger_id="b", problem_winners={"p1": "challenger"})

    comparisons = load_comparisons(log)

    assert {item.challenge_id for item in comparisons} == {"c1", "c2"}
    assert {item.right for item in comparisons} == {"a", "b"}


def test_a_missing_log_is_an_empty_history_not_an_error(tmp_path: Path) -> None:
    assert load_comparisons(tmp_path / "nothing.jsonl") == []


def test_a_corrupt_log_line_names_itself(tmp_path: Path) -> None:
    log = tmp_path / "matches.jsonl"
    log.write_text('{"king_id": "k"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        load_comparisons(log)


def test_the_baseline_is_just_another_agent(tmp_path: Path) -> None:
    # The control needs no special case: it competes and it ranks.
    comparisons = _duel("king-1", "direct-baseline", "lllllr")

    rows = build_leaderboard(rank(comparisons, bootstrap=100))

    assert rows[0]["agent_id"] == "king-1"
    assert rows[1]["agent_id"] == "direct-baseline"


def test_rating_conversion_is_monotonic() -> None:
    assert to_rating(1.0) == pytest.approx(BASE_RATING)
    assert to_rating(10.0) == pytest.approx(BASE_RATING + 400.0)
    assert to_rating(0.1) == pytest.approx(BASE_RATING - 400.0)
