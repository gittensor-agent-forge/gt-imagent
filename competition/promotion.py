from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from imagent_scoring.ladder import ProblemVerdict, mean_fact_score

# Turning a run of benchmark verdicts into a decision about the crown.
#
# The benchmark answers "which image is better". This answers "does that add up
# to a new king", which is a different and more conservative question: a
# leaderboard that churns on noise tells nobody anything.

# How far a challenger's mean fact score may sit below the king's and still be
# promoted. Not zero, because judge-decided wins carry noise; small, because the
# whole point is that instruction-following must not regress.
MAX_FACT_REGRESSION = 0.03
# A challenger must win clearly. One net win is inside the noise of a seven
# problem duel; two is the smallest margin worth a crown.
PROMOTION_MARGIN = 2


@dataclass(frozen=True)
class MatchVerdict:
    promoted: bool
    wins: int
    losses: int
    ties: int
    margin: int
    king_mean_fact: float
    challenger_mean_fact: float
    reasons: tuple[str, ...]
    problems: tuple[ProblemVerdict, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "promoted": self.promoted,
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "margin": self.margin,
            "king_mean_fact": round(self.king_mean_fact, 6),
            "challenger_mean_fact": round(self.challenger_mean_fact, 6),
            "reasons": list(self.reasons),
            "problems": [problem.to_dict() for problem in self.problems],
        }


def decide_match(
    verdicts: list[ProblemVerdict],
    *,
    disqualification: str | None = None,
    margin: int = PROMOTION_MARGIN,
    max_fact_regression: float = MAX_FACT_REGRESSION,
) -> MatchVerdict:
    """Tally a duel and decide whether the crown moves.

    Ties count for the king. That incumbent advantage is not sentiment: without
    it, a seven-problem duel between two equal agents flips the crown far too
    often.

    `disqualification` carries a violation the sealed room observed — an agent
    that asked for a different model, or blew its budget. It ends the match
    regardless of the score, because those results were never comparable.
    """
    wins = sum(1 for verdict in verdicts if verdict.winner == "challenger")
    losses = sum(1 for verdict in verdicts if verdict.winner == "king")
    ties = sum(1 for verdict in verdicts if verdict.winner == "tie")

    king_mean = mean_fact_score(verdicts, side="king")
    challenger_mean = mean_fact_score(verdicts, side="challenger")

    reasons: list[str] = []
    if disqualification:
        reasons.append(f"disqualified: {disqualification}")
    if not verdicts:
        reasons.append("no problems were decided")
    if wins - losses < margin:
        reasons.append(
            f"net wins {wins - losses} is below the required margin of {margin}"
            f" (won {wins}, lost {losses}, tied {ties})"
        )
    regression = king_mean - challenger_mean
    if regression > max_fact_regression:
        reasons.append(
            f"mean fact score regressed by {regression:.3f}"
            f" (allowed {max_fact_regression:.3f}): {challenger_mean:.3f} vs {king_mean:.3f}"
        )

    return MatchVerdict(
        promoted=not reasons,
        wins=wins,
        losses=losses,
        ties=ties,
        margin=wins - losses,
        king_mean_fact=king_mean,
        challenger_mean_fact=challenger_mean,
        reasons=tuple(reasons),
        problems=tuple(verdicts),
    )


def disqualification_from_provenance(provenance: dict[str, Any]) -> str | None:
    """Read the sealed room's attested account and decide if the run was legal.

    These are not scores; they are observations the room made about the agent,
    signed by hardware. An agent that asked for a different model did not lose on
    quality — its run was never a comparable run at all.
    """
    policy = provenance.get("inference_policy")
    if not isinstance(policy, dict):
        return "attested inference policy is missing from the run provenance"

    substitutions = policy.get("model_substitutions", 0)
    if isinstance(substitutions, int) and substitutions > 0:
        requested = policy.get("requested_models") or []
        return (
            f"agent requested a non-pinned model {substitutions} time(s): "
            f"{', '.join(str(model) for model in requested) or 'unknown'}"
        )

    statuses = policy.get("statuses")
    if isinstance(statuses, dict):
        if statuses.get("payment_required"):
            return "the miner's provider key ran out of credit during the run"
        if statuses.get("unauthorized"):
            return "the miner's provider key was rejected by the provider"

    return None
