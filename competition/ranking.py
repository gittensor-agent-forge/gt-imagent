from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# Ranking every agent that has ever competed, from the permanent match log.
#
# Not Elo. Elo is sequential: the same matches in a different order give
# different ratings, and it is sensitive to an arbitrary K-factor. LMArena
# started there and moved to Bradley-Terry for exactly that reason. Bradley-Terry
# fits every rating at once from the whole history, so the order matches were
# played in cannot change the answer, and bootstrapping gives an honest interval
# instead of a falsely precise number.
#
#     P(i beats j) = strength_i / (strength_i + strength_j)
#
# Comparisons are recorded per PROBLEM, not per duel: a seven-problem duel is
# seven observations, and throwing six of them away to record a single win would
# waste most of what the challenge paid for.
#
# Ranking and promotion answer different questions. Promotion asks "did this
# challenger clearly beat the incumbent today?"; ranking asks "how strong is
# everyone, given everything ever played?". They can disagree, and that is fine.

BASE_RATING = 1000.0
# The Elo convention: 400 points is 10:1 odds. Keeping it makes the numbers
# legible to anyone who has seen a chess or arena rating.
RATING_SCALE = 400.0
# A weak prior pulling every agent toward average, expressed as this many virtual
# wins and losses against a fictional average opponent. Without it an agent that
# has never lost has infinite strength, and a newcomer's first lucky win would
# top the board.
DEFAULT_PRIOR = 1.0
DEFAULT_BOOTSTRAP = 500
MAX_ITERATIONS = 500
TOLERANCE = 1e-9


@dataclass(frozen=True)
class Comparison:
    """One problem, judged between two agents."""

    left: str
    right: str
    winner: str  # "left", "right", or "tie"
    challenge_id: str = ""
    problem_id: str = ""

    def __post_init__(self) -> None:
        if self.winner not in {"left", "right", "tie"}:
            raise ValueError(f"winner must be left/right/tie, got {self.winner!r}")
        if self.left == self.right:
            raise ValueError("a comparison needs two different agents")


@dataclass(frozen=True)
class Rating:
    agent_id: str
    rating: float
    low: float
    high: float
    comparisons: int
    wins: float
    losses: float
    ties: int

    def overlaps(self, other: "Rating") -> bool:
        """True when the two intervals cannot be told apart.

        The dashboard must say so rather than printing a confident ordering it
        cannot support.
        """
        return self.low <= other.high and other.low <= self.high

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "rating": round(self.rating, 2),
            "ci_low": round(self.low, 2),
            "ci_high": round(self.high, 2),
            "comparisons": self.comparisons,
            "wins": round(self.wins, 1),
            "losses": round(self.losses, 1),
            "ties": self.ties,
        }


def fit_bradley_terry(
    comparisons: Iterable[Comparison], *, prior: float = DEFAULT_PRIOR
) -> dict[str, float]:
    """Maximum-likelihood strengths, by minorisation-maximisation (Zermelo's).

    Iterative and derivative-free, so it needs no numerical library — which
    matters, because this package stays stdlib-only.

    Returns strengths normalised to a geometric mean of 1.
    """
    records = list(comparisons)
    agents = sorted({agent for record in records for agent in (record.left, record.right)})
    if not agents:
        return {}

    wins: dict[str, float] = {agent: 0.0 for agent in agents}
    pairs: dict[tuple[str, str], int] = {}
    for record in records:
        # A tie is half a win each. Discarding ties would throw away the
        # observation that two agents were indistinguishable, which is
        # information about their strengths.
        if record.winner == "left":
            wins[record.left] += 1.0
        elif record.winner == "right":
            wins[record.right] += 1.0
        else:
            wins[record.left] += 0.5
            wins[record.right] += 0.5
        key = (record.left, record.right) if record.left < record.right else (record.right, record.left)
        pairs[key] = pairs.get(key, 0) + 1

    opponents: dict[str, list[tuple[str, int]]] = {agent: [] for agent in agents}
    for (first, second), count in pairs.items():
        opponents[first].append((second, count))
        opponents[second].append((first, count))

    strength = {agent: 1.0 for agent in agents}
    for _ in range(MAX_ITERATIONS):
        updated: dict[str, float] = {}
        for agent in agents:
            denominator = sum(
                count / (strength[agent] + strength[other])
                for other, count in opponents[agent]
            )
            # The prior is `prior` wins and `prior` losses against a fictional
            # opponent of strength 1, which is what keeps an undefeated agent
            # finite.
            denominator += 2.0 * prior / (strength[agent] + 1.0)
            updated[agent] = (wins[agent] + prior) / denominator if denominator > 0 else strength[agent]

        updated = _normalise(updated)
        shift = max(abs(updated[agent] - strength[agent]) for agent in agents)
        strength = updated
        if shift < TOLERANCE:
            break

    return strength


def _normalise(strength: dict[str, float]) -> dict[str, float]:
    """Scale to a geometric mean of 1, so ratings centre on BASE_RATING."""
    positive = {agent: max(value, 1e-12) for agent, value in strength.items()}
    log_mean = sum(math.log(value) for value in positive.values()) / len(positive)
    factor = math.exp(-log_mean)
    return {agent: value * factor for agent, value in positive.items()}


def to_rating(strength: float) -> float:
    return BASE_RATING + RATING_SCALE * math.log10(max(strength, 1e-12))


def rank(
    comparisons: Iterable[Comparison],
    *,
    prior: float = DEFAULT_PRIOR,
    bootstrap: int = DEFAULT_BOOTSTRAP,
    confidence: float = 0.95,
) -> list[Rating]:
    """Fit, bootstrap, and sort. Highest rating first.

    The interval comes from refitting on resampled matches. Publishing a rank
    without one invites readers to believe a two-point gap means something.
    """
    records = list(comparisons)
    if not records:
        return []

    strengths = fit_bradley_terry(records, prior=prior)
    intervals = _bootstrap_intervals(records, prior=prior, rounds=bootstrap, confidence=confidence)
    tallies = _tally(records)

    ratings = []
    for agent, strength in strengths.items():
        point = to_rating(strength)
        low, high = intervals.get(agent, (point, point))
        won, lost, tied, total = tallies[agent]
        ratings.append(
            Rating(
                agent_id=agent,
                rating=point,
                low=low,
                high=high,
                comparisons=total,
                wins=won,
                losses=lost,
                ties=tied,
            )
        )
    # Ties in rating broken by agent id, so the published order never depends on
    # dictionary iteration order.
    return sorted(ratings, key=lambda item: (-item.rating, item.agent_id))


def _tally(records: list[Comparison]) -> dict[str, tuple[float, float, int, int]]:
    tallies: dict[str, list[float]] = {}
    for record in records:
        for agent in (record.left, record.right):
            tallies.setdefault(agent, [0.0, 0.0, 0.0, 0.0])
        winner = record.left if record.winner == "left" else record.right
        loser = record.right if record.winner == "left" else record.left
        if record.winner == "tie":
            tallies[record.left][2] += 1
            tallies[record.right][2] += 1
        else:
            tallies[winner][0] += 1
            tallies[loser][1] += 1
        tallies[record.left][3] += 1
        tallies[record.right][3] += 1
    return {
        agent: (values[0], values[1], int(values[2]), int(values[3]))
        for agent, values in tallies.items()
    }


def _bootstrap_intervals(
    records: list[Comparison], *, prior: float, rounds: int, confidence: float
) -> dict[str, tuple[float, float]]:
    if rounds <= 0:
        return {}

    # Resampling is seeded from the match log itself, so a published interval is
    # reproducible by anyone holding the same log. An unseeded bootstrap would
    # print slightly different confidence bounds on every page render.
    seed = hashlib.sha256(
        json.dumps(
            [[record.left, record.right, record.winner] for record in records], sort_keys=True
        ).encode("utf-8")
    ).digest()

    samples: dict[str, list[float]] = {}
    size = len(records)
    for round_index in range(rounds):
        resampled = [records[index] for index in _indices(seed, round_index, size)]
        for agent, strength in fit_bradley_terry(resampled, prior=prior).items():
            samples.setdefault(agent, []).append(to_rating(strength))

    tail = (1.0 - confidence) / 2.0
    intervals: dict[str, tuple[float, float]] = {}
    for agent, values in samples.items():
        ordered = sorted(values)
        intervals[agent] = (_percentile(ordered, tail), _percentile(ordered, 1.0 - tail))
    return intervals


def _indices(seed: bytes, round_index: int, size: int) -> list[int]:
    """Deterministic resampling indices, SHA-256 in counter mode."""
    out: list[int] = []
    counter = 0
    while len(out) < size:
        digest = hashlib.sha256(seed + f":{round_index}:{counter}".encode("ascii")).digest()
        for offset in range(0, 32, 4):
            if len(out) >= size:
                break
            out.append(int.from_bytes(digest[offset : offset + 4], "big") % size)
        counter += 1
    return out


def _percentile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


# --- the permanent match log ------------------------------------------------


def append_match(
    path: str | Path,
    *,
    challenge_id: str,
    king_id: str,
    challenger_id: str,
    problem_winners: dict[str, str],
) -> None:
    """Append one duel. Append-only: the history is the evidence.

    `problem_winners` maps problem id to "king", "challenger", or "tie".
    """
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "challenge_id": challenge_id,
        "king_id": king_id,
        "challenger_id": challenger_id,
        "problems": problem_winners,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def load_comparisons(path: str | Path) -> list[Comparison]:
    """Read the log into problem-level comparisons."""
    log_path = Path(path)
    if not log_path.exists():
        return []

    comparisons: list[Comparison] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                king = str(record["king_id"])
                challenger = str(record["challenger_id"])
                problems = record["problems"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError(f"{log_path}: malformed match on line {line_number}: {exc}") from exc

            for problem_id, winner in sorted(problems.items()):
                comparisons.append(
                    Comparison(
                        left=king,
                        right=challenger,
                        winner={"king": "left", "challenger": "right"}.get(str(winner), "tie"),
                        challenge_id=str(record.get("challenge_id", "")),
                        problem_id=str(problem_id),
                    )
                )
    return comparisons


def build_leaderboard(ratings: list[Rating]) -> list[dict[str, Any]]:
    """Published rows, each flagged when it cannot be told apart from the one above."""
    rows: list[dict[str, Any]] = []
    for position, rating in enumerate(ratings, start=1):
        row = rating.to_dict()
        row["rank"] = position
        row["indistinguishable_from_previous"] = (
            position > 1 and rating.overlaps(ratings[position - 2])
        )
        rows.append(row)
    return rows
