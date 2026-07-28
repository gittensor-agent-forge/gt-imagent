from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# The competition's state machine.
#
# Everything here is pure: it takes the current state and returns a list of
# actions someone else performs. Nothing in this module touches the network.
#
# That split matters more than it looks. This bot merges pull requests, closes
# them, and rewrites who holds the crown. Those are not actions you want decided
# inside the same function that performs them, because then the only way to see
# what the bot would do is to let it do it.

PENDING = "challenger:pending"
RUNNING = "challenger:running"
DEFEATED = "challenger:defeated"
INVALID = "challenger:invalid"
KING = "king"
PAST_KING = "king:past"

CHALLENGER_LABELS = (PENDING, RUNNING, DEFEATED, INVALID)

ActionKind = Literal["label", "unlabel", "comment", "close", "merge"]


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    pull_request: int
    value: str = ""

    def describe(self) -> str:
        if self.kind in ("label", "unlabel"):
            return f"#{self.pull_request}: {self.kind} {self.value}"
        if self.kind == "comment":
            return f"#{self.pull_request}: comment ({len(self.value)} chars)"
        return f"#{self.pull_request}: {self.kind}"


@dataclass(frozen=True)
class Submission:
    number: int
    author: str
    labels: tuple[str, ...] = ()
    created_at: str = ""


def plan_screening(
    submission: Submission,
    *,
    reasons: list[str],
    open_submissions: list[Submission],
) -> tuple[Action, ...]:
    """What to do with a freshly opened or updated submission.

    One open submission per contributor. Without that rule a single author can
    flood the queue and starve everyone else, and since each challenge costs real
    money the flooding is also expensive.
    """
    duplicates = [
        other
        for other in open_submissions
        if other.author == submission.author and other.number != submission.number
    ]

    all_reasons = list(reasons)
    if duplicates:
        others = ", ".join(f"#{other.number}" for other in sorted(duplicates, key=lambda s: s.number))
        all_reasons.append(
            f"@{submission.author} already has an open submission ({others}); "
            "close it before opening another"
        )

    if all_reasons:
        return (
            *_clear_challenger_labels(submission),
            Action("label", submission.number, INVALID),
            Action("comment", submission.number, format_rejection(all_reasons)),
            Action("close", submission.number),
        )

    return (
        *_clear_challenger_labels(submission),
        Action("label", submission.number, PENDING),
        Action("comment", submission.number, format_queued()),
    )


def plan_start(
    *, pending: list[Submission], running: list[Submission]
) -> tuple[Action, ...]:
    """Pick the next duel, or none.

    One duel at a time. The king cannot be fighting two challengers, or two
    promotions could race and one would silently overwrite the other.
    """
    if running:
        return ()
    if not pending:
        return ()

    # Oldest first, so the queue is a queue and not a lottery.
    nominee = sorted(pending, key=lambda item: (item.created_at, item.number))[0]
    return (
        Action("unlabel", nominee.number, PENDING),
        Action("label", nominee.number, RUNNING),
        Action("comment", nominee.number, format_started()),
    )


def plan_outcome(
    submission: Submission,
    *,
    promoted: bool,
    match: dict[str, Any],
    challenge_id: str,
    king_submission: Submission | None = None,
    aborted: str = "",
) -> tuple[Action, ...]:
    """What to do once a duel resolves.

    `aborted` carries an infrastructure failure. It is not a defeat: the
    challenger goes back to the front of the queue and nothing is recorded,
    because a run that could not complete is not a run the miner lost.
    """
    if aborted:
        return (
            Action("unlabel", submission.number, RUNNING),
            Action("label", submission.number, PENDING),
            Action("comment", submission.number, format_aborted(aborted)),
        )

    if not promoted:
        return (
            Action("unlabel", submission.number, RUNNING),
            Action("label", submission.number, DEFEATED),
            Action("comment", submission.number, format_result(match, challenge_id, promoted=False)),
            Action("close", submission.number),
        )

    actions = [
        Action("unlabel", submission.number, RUNNING),
        Action("label", submission.number, KING),
        Action("comment", submission.number, format_result(match, challenge_id, promoted=True)),
        Action("merge", submission.number),
    ]
    if king_submission is not None and king_submission.number != submission.number:
        actions += [
            Action("unlabel", king_submission.number, KING),
            Action("label", king_submission.number, PAST_KING),
            # The dethroned king gets one immediate rematch. It is the cheapest
            # correction available: a challenger that won on luck loses the crown
            # straight back, without buying a larger duel every time.
            Action("comment", king_submission.number, format_dethroned(submission.number)),
        ]
    return tuple(actions)


def _clear_challenger_labels(submission: Submission) -> tuple[Action, ...]:
    return tuple(
        Action("unlabel", submission.number, label)
        for label in CHALLENGER_LABELS
        if label in submission.labels
    )


# --- what the bot says ------------------------------------------------------


def format_rejection(reasons: list[str]) -> str:
    lines = ["**Submission rejected before any credits were spent.**", ""]
    lines += [f"- {reason}" for reason in reasons]
    lines += ["", "Fix these and open a new pull request."]
    return "\n".join(lines)


def format_queued() -> str:
    return (
        "**Screening passed.** Queued as a challenger.\n\n"
        "Your agent will run against the reigning king on 7 freshly generated "
        "problems, inside the sealed room, funded by your sealed inference key. "
        "Duels run one at a time, oldest first."
    )


def format_started() -> str:
    return (
        "**Duel started.** Your agent and the reigning king are answering the "
        "same 7 problems, on the same fixed model, under the same limits."
    )


def format_aborted(reason: str) -> str:
    return (
        f"**Challenge aborted — not a defeat.** {reason}\n\n"
        "This was an infrastructure failure, so no result was recorded. "
        "You are back in the queue."
    )


def format_dethroned(challenger_number: int) -> str:
    return (
        f"**Dethroned by #{challenger_number}.** Automatically requeued for one "
        "immediate rematch."
    )


def format_result(match: dict[str, Any], challenge_id: str, *, promoted: bool) -> str:
    wins = match.get("wins", 0)
    losses = match.get("losses", 0)
    ties = match.get("ties", 0)
    headline = "**Promoted — you are the new king.**" if promoted else "**Defeated.**"

    lines = [
        headline,
        "",
        f"Challenge `{challenge_id}`",
        "",
        f"| | |",
        f"|---|---|",
        f"| Won | {wins} |",
        f"| Lost | {losses} |",
        f"| Tied | {ties} |",
        f"| Net | {match.get('margin', wins - losses):+d} |",
        f"| Mean fact score | {match.get('challenger_mean_fact', 0.0):.3f} "
        f"(king {match.get('king_mean_fact', 0.0):.3f}) |",
    ]

    reasons = match.get("reasons") or []
    if reasons:
        lines += ["", "**Why it did not promote:**"]
        lines += [f"- {reason}" for reason in reasons]

    lines += [
        "",
        "Ties count for the king. A challenger must win by 2 or more and must not "
        "regress on the objective fact checks.",
        "",
        "The full report — both images per problem, every answer-key check, the "
        "judge's raw verdicts, and the attestation — is attached to the workflow run.",
    ]
    return "\n".join(lines)
