"""Run one duel and write the outcome the bot resolves.

Called by the Challenge workflow once `bot tick` has started a challenger. It
assembles the scoring stack, runs the challenger against the king and the
baseline, and writes `challenge-output/outcome.json`.

It always writes that file — including when the challenge aborts — because the
bot reads it to put an aborted challenger back in the queue. A challenger left
labelled `running` because a crash skipped this step would block the queue
forever.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from competition.bot import find_submission, read_bundle  # noqa: E402
from competition.challenge import ChallengeAborted, ScoringStack, run_challenge  # noqa: E402
from competition.room_client import AgentSubmission, SealedRoomClient  # noqa: E402
from competition.status import load_king  # noqa: E402

OUTPUT = Path("challenge-output")


def build_scoring_stack() -> ScoringStack:
    """Assemble the graders, or say precisely which one is missing.

    A missing backend must never become a silent free pass, so this refuses to
    build a partial stack rather than scoring against whichever checks happen to
    be available.
    """
    from imagent_scoring.openrouter import OpenRouterPairwiseJudge, OpenRouterVqa
    from imagent_scoring.pillow_loader import PillowImageLoader

    missing = [
        name
        for name, available in (
            ("object detector + colour classifier", False),
            ("OCR engine", False),
        )
        if not available
    ]
    if missing:
        raise ChallengeAborted(
            "the scoring stack is incomplete: " + ", ".join(missing) + ". "
            "Every GenEval and text-rendering problem needs these, and scoring "
            "without them would grade a candidate on whichever checks happen to "
            "be installed."
        )

    return ScoringStack(
        loader=PillowImageLoader(),
        vqa=OpenRouterVqa(),
        judge=OpenRouterPairwiseJudge(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one Imagent duel.")
    parser.add_argument("--pr", type=int, required=True)
    args = parser.parse_args(argv)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    outcome_path = OUTPUT / "outcome.json"
    bundle = find_submission()
    king = load_king()

    outcome: dict[str, object] = {
        "pull_request": args.pr,
        "promoted": False,
        "bundle_dir": str(bundle) if bundle else "",
        "commit_sha": os.environ.get("GITHUB_SHA", ""),
        "agent_id": f"pr-{args.pr}",
    }

    try:
        if bundle is None:
            raise ChallengeAborted("no submission directory found in the checkout")
        if king is None:
            raise ChallengeAborted("there is no reigning king to challenge")

        _, sealed = read_bundle(bundle)
        room = SealedRoomClient(
            os.environ["KATA_ROOM_URL"],
            os.environ["KATA_ROOM_AUTH_SECRET"],
            {
                f"pr-{args.pr}": AgentSubmission(
                    agent_id=f"pr-{args.pr}",
                    bundle_b64=_pack(bundle),
                    bundle_sha256=_digest(bundle),
                    sealed_key=sealed,
                ),
            },
        )

        result = run_challenge(
            room=room,
            king_id=king.agent_id,
            challenger_id=f"pr-{args.pr}",
            stack=build_scoring_stack(),
            image_dir=OUTPUT / "images",
            allowed_measurements={os.environ.get("IMAGENT_ROOM_MEASUREMENT", "")} - {""},
            match_log=Path("kings/matches.jsonl"),
        )
        outcome.update(
            promoted=result.promoted,
            challenge_id=result.challenge_id,
            match=result.match,
        )
        (OUTPUT / "report.json").write_text(json.dumps(result.report, indent=2), encoding="utf-8")
        (OUTPUT / "leaderboard.json").write_text(
            json.dumps(result.leaderboard, indent=2), encoding="utf-8"
        )
    except ChallengeAborted as error:
        # Not a defeat. The bot reads this and returns the challenger to the queue.
        outcome["aborted"] = str(error)
        print(f"::warning::challenge aborted: {error}")
    finally:
        outcome_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


def _pack(bundle: Path) -> str:
    import base64
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file() and not path.is_symlink():
                archive.add(path, arcname=path.relative_to(bundle).as_posix())
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _digest(bundle: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(bundle.rglob("*")):
        if path.is_file() and not path.is_symlink():
            digest.update(path.relative_to(bundle).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
