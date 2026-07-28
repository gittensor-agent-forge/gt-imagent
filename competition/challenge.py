from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from imagent_bench.problems import (
    GENERATOR_VERSION,
    Problem,
    generate_problems,
    new_challenge_id,
)
from imagent_scoring import (
    SideResult,
    check_validity,
    decide_problem,
    judge_problem,
    parse_answer_key,
    score_facts,
)

from .promotion import decide_match, disqualification_from_provenance
from .publishing import SideSummary, build_challenge_report, verify_image_hashes
from .ranking import append_match, build_leaderboard, load_comparisons, rank

# One challenge, end to end.
#
#   issue -> run in the room -> verify the attestation -> grade -> judge ->
#   decide -> publish -> rank
#
# Every rule this calls has already been decided elsewhere and tested on its own.
# What lives here is only the order of operations and, more importantly, the
# distinction the whole competition rests on:
#
#   an INFRASTRUCTURE failure aborts the challenge and nobody loses;
#   an AGENT failure loses problems.
#
# Getting that backwards is how a benchmark starts blaming miners for its own
# provider outages.


class ChallengeAborted(RuntimeError):
    """Infrastructure failed. Requeue the challenge; no verdict is recorded."""


@dataclass(frozen=True)
class RoomRun:
    """What a sealed room returns for one agent."""

    agent_id: str
    report: dict[str, Any]
    images: dict[str, bytes]
    provenance: dict[str, Any]
    quote: str = ""
    measurement: str = ""


@runtime_checkable
class Room(Protocol):
    def run(self, *, challenge_id: str, agent_id: str, nonce: str) -> RoomRun:
        """Run one agent over the challenge inside the TEE."""


@dataclass
class ScoringStack:
    """The graders. Each is optional; a problem needing a missing one will say so."""

    loader: Any
    ocr: Any = None
    detector: Any = None
    vqa: Any = None
    judge: Any = None


@dataclass(frozen=True)
class ChallengeResult:
    challenge_id: str
    promoted: bool
    match: dict[str, Any]
    report: dict[str, Any]
    leaderboard: list[dict[str, Any]] = field(default_factory=list)


def issue_challenge() -> tuple[str, bytes, list[Problem]]:
    """Allocate an unpredictable challenge and derive its problems.

    The id must not be sequential: the seed is derived from it, so a guessable id
    would let anyone generate the next challenge's problems in advance.
    """
    challenge_id = new_challenge_id()
    seed = hashlib.sha256(f"imagent-challenge-v1:{challenge_id}".encode("utf-8")).digest()
    return challenge_id, seed, generate_problems(seed)


def verify_run(
    run: RoomRun, *, challenge_id: str, allowed_measurements: set[str]
) -> None:
    """Check the room's answer before trusting a single pixel of it.

    Any failure here aborts: an unverifiable run is not a lost run, it is a run
    that never happened.
    """
    if allowed_measurements and run.measurement not in allowed_measurements:
        raise ChallengeAborted(
            f"{run.agent_id}: room measurement {run.measurement!r} is not allowlisted"
        )
    if not run.quote:
        raise ChallengeAborted(f"{run.agent_id}: run carries no attestation quote")
    if str(run.report.get("challenge_id", "")) != challenge_id:
        raise ChallengeAborted(
            f"{run.agent_id}: attested report answers a different challenge"
        )

    attested = {
        str(item.get("problem_id", "")): str(item.get("image_sha256", ""))
        for item in run.report.get("problems", [])
        if item.get("image_sha256")
    }
    mismatches = verify_image_hashes(run.images, attested)
    if mismatches:
        raise ChallengeAborted(
            f"{run.agent_id}: image bytes do not match the attested hashes: {mismatches}"
        )


def grade_side(
    run: RoomRun,
    problems: list[Problem],
    *,
    stack: ScoringStack,
    image_dir: Path,
    archived_hashes: set[str] = frozenset(),
) -> tuple[dict[str, SideResult], dict[str, dict[str, Any]]]:
    """S1 and S2 for one agent, per problem.

    A problem with no image is a loss for that problem, not an aborted challenge:
    the agent had its chance and produced nothing.
    """
    results: dict[str, SideResult] = {}
    fact_reports: dict[str, dict[str, Any]] = {}

    for problem in problems:
        payload = run.images.get(problem.problem_id)
        if not payload:
            results[problem.problem_id] = SideResult(
                valid=False, error="the agent produced no image for this problem"
            )
            continue

        path = image_dir / f"{run.agent_id}-{problem.problem_id}.img"
        path.write_bytes(payload)

        validity = check_validity(
            path, loader=stack.loader, known_hashes=archived_hashes
        )
        if not validity.valid:
            results[problem.problem_id] = SideResult(
                valid=False, error="; ".join(validity.reasons)
            )
            continue

        report = score_facts(
            path,
            parse_answer_key(problem.answer_key),
            loader=stack.loader,
            ocr=stack.ocr,
            detector=stack.detector,
            vqa=stack.vqa,
        )
        fact_reports[problem.problem_id] = report.to_dict()
        results[problem.problem_id] = SideResult(valid=True, fact_score=report.fact_score)

    return results, fact_reports


def run_challenge(
    *,
    room: Room,
    king_id: str,
    challenger_id: str,
    stack: ScoringStack,
    image_dir: Path,
    baseline_id: str | None = "direct-baseline",
    allowed_measurements: set[str] = frozenset(),
    archived_hashes: set[str] = frozenset(),
    match_log: Path | None = None,
    votes: int = 3,
    scoring_version: str = "scoring-v1.0.0",
) -> ChallengeResult:
    """Run one duel and return its verdict, published report, and leaderboard."""
    challenge_id, seed, problems = issue_challenge()
    image_dir.mkdir(parents=True, exist_ok=True)
    nonce = hashlib.sha256(f"{challenge_id}:nonce".encode()).hexdigest()[:32]

    runs: dict[str, RoomRun] = {}
    for role, agent_id in (("king", king_id), ("challenger", challenger_id)):
        try:
            run = room.run(challenge_id=challenge_id, agent_id=agent_id, nonce=nonce)
        except ChallengeAborted:
            raise
        except Exception as exc:  # noqa: BLE001 - the room itself failing is infrastructure
            raise ChallengeAborted(f"{role} run failed: {exc}") from exc
        verify_run(run, challenge_id=challenge_id, allowed_measurements=allowed_measurements)
        runs[role] = run

    # The control. It is validator-funded and never decides a promotion, so a
    # baseline failure must not cost the challengers their duel.
    if baseline_id:
        try:
            baseline = room.run(challenge_id=challenge_id, agent_id=baseline_id, nonce=nonce)
            verify_run(baseline, challenge_id=challenge_id, allowed_measurements=allowed_measurements)
            runs["baseline"] = baseline
        except Exception:  # noqa: BLE001
            pass

    graded: dict[str, tuple[dict[str, SideResult], dict[str, dict[str, Any]]]] = {
        role: grade_side(
            run, problems, stack=stack, image_dir=image_dir, archived_hashes=archived_hashes
        )
        for role, run in runs.items()
    }

    verdicts = []
    judge_payloads: dict[str, dict[str, Any]] = {}
    for problem in problems:
        king_result = graded["king"][0][problem.problem_id]
        challenger_result = graded["challenger"][0][problem.problem_id]

        verdict_judge = None
        # Only pay a judge when both sides produced something to compare.
        if stack.judge is not None and king_result.valid and challenger_result.valid:
            verdict_judge = judge_problem(
                judge=stack.judge,
                challenge_id=challenge_id,
                problem_id=problem.problem_id,
                prompt=problem.prompt,
                king_image=image_dir / f"{king_id}-{problem.problem_id}.img",
                challenger_image=image_dir / f"{challenger_id}-{problem.problem_id}.img",
                votes=votes,
            )
            judge_payloads[problem.problem_id] = verdict_judge.to_dict()

        verdicts.append(
            decide_problem(
                problem_id=problem.problem_id,
                king=king_result,
                challenger=challenger_result,
                judge=verdict_judge,
            )
        )

    match = decide_match(
        verdicts,
        disqualification=disqualification_from_provenance(runs["challenger"].provenance),
    )

    sides = [
        SideSummary(
            agent_id=runs[role].agent_id,
            role=role,
            fact_reports=graded[role][1],
            image_hashes={
                problem_id: hashlib.sha256(payload).hexdigest()
                for problem_id, payload in runs[role].images.items()
            },
            attestation={
                "quote": runs[role].quote,
                "measurement": runs[role].measurement,
                "inference_policy": runs[role].provenance.get("inference_policy", {}),
            },
        )
        for role in ("king", "challenger", "baseline")
        if role in runs
    ]

    report = build_challenge_report(
        challenge_id=challenge_id,
        seed=seed,
        versions={"generator": GENERATOR_VERSION, "scoring": scoring_version},
        sides=sides,
        match=match.to_dict(),
        judge_verdicts=judge_payloads,
        prompts={problem.problem_id: problem.prompt for problem in problems},
    )

    leaderboard: list[dict[str, Any]] = []
    if match_log is not None:
        append_match(
            match_log,
            challenge_id=challenge_id,
            king_id=king_id,
            challenger_id=challenger_id,
            problem_winners={verdict.problem_id: verdict.winner for verdict in verdicts},
        )
        if "baseline" in runs:
            append_match(
                match_log,
                challenge_id=challenge_id,
                king_id=king_id,
                challenger_id=runs["baseline"].agent_id,
                problem_winners=_baseline_outcomes(graded, problems),
            )
        leaderboard = build_leaderboard(rank(load_comparisons(match_log)))

    return ChallengeResult(
        challenge_id=challenge_id,
        promoted=match.promoted,
        match=match.to_dict(),
        report=report,
        leaderboard=leaderboard,
    )


def _baseline_outcomes(graded, problems: list[Problem]) -> dict[str, str]:
    """Score the control on facts alone.

    The baseline never competes for the crown, so it is not worth a judge call.
    Comparing fact scores is enough to answer the only question it exists to
    answer: is an agent doing better than a plain prompt?
    """
    outcomes: dict[str, str] = {}
    for problem in problems:
        king = graded["king"][0][problem.problem_id]
        baseline = graded["baseline"][0][problem.problem_id]
        if not baseline.valid:
            outcomes[problem.problem_id] = "king"
        elif not king.valid:
            outcomes[problem.problem_id] = "challenger"
        elif abs(king.fact_score - baseline.fact_score) < 0.02:
            outcomes[problem.problem_id] = "tie"
        else:
            outcomes[problem.problem_id] = (
                "king" if king.fact_score > baseline.fact_score else "challenger"
            )
    return outcomes
