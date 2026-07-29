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
KING_DIR = Path("kings/current")
BASELINE_DIR = Path("kings/baseline")
BASELINE_ID = "direct-baseline"
# The project funds the king's defences and the control. A sealed credential is
# bound to the hash of the bundle it ships with, so these are per-bundle files —
# one ciphertext cannot serve two different bundles.
SEALED_FILENAME = "sealed_inference_key"


def build_scoring_stack() -> ScoringStack:
    """Assemble the graders.

    Object checks prefer a local detector, because its answers are deterministic
    and anyone holding the image can re-derive them. Where no detector is
    installed, a vision model answers the same questions and every result it
    produces is flagged non-deterministic in the published report.

    OCR has no such fallback: reading text is exactly the thing a vision model is
    least reliable at, and a text-rendering score nobody can reproduce is worse
    than no text-rendering score. If it is missing, that is an abort.
    """
    from imagent_scoring.openrouter import (
        OpenRouterObjectVerifier,
        OpenRouterPairwiseJudge,
        OpenRouterVqa,
    )
    from imagent_scoring.pillow_loader import PillowImageLoader

    detector = _optional_detector()
    ocr = _optional_ocr()
    if ocr is None:
        if os.environ.get("IMAGENT_ALLOW_NO_OCR", "").strip() not in ("1", "true", "yes"):
            raise ChallengeAborted(
                "no OCR engine is installed, so text-rendering problems cannot be graded "
                "reproducibly. Install pytesseract and the tesseract binary, or set "
                "IMAGENT_ALLOW_NO_OCR=1 to fall back to a vision model — which is fine "
                "for smoke-testing a deployment and not fine for deciding a crown."
            )
        from imagent_scoring.openrouter import OpenRouterOcr

        print("::warning::grading text with a vision model; results are not reproducible")
        ocr = OpenRouterOcr()

    return ScoringStack(
        loader=PillowImageLoader(),
        ocr=ocr,
        detector=detector,
        verifier=None if detector else OpenRouterObjectVerifier(),
        vqa=OpenRouterVqa(),
        judge=OpenRouterPairwiseJudge(),
    )


def _optional_detector():
    """A local object detector, if this machine has one."""
    try:
        from imagent_scoring.local_detector import LocalObjectDetector
    except ImportError:
        return None
    return LocalObjectDetector()


def _optional_ocr():
    try:
        from imagent_scoring.local_ocr import TesseractOcr
    except ImportError:
        return None
    return TesseractOcr()


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

        _, challenger_sealed = read_bundle(bundle)

        # The king and the baseline are the project's own code, so the project
        # funds them. Their runs use a credential the maintainers sealed to the
        # room, not the challenger's — a miner pays for their own attempt and
        # nothing else.
        room = SealedRoomClient(
            os.environ["KATA_ROOM_URL"],
            os.environ["KATA_ROOM_AUTH_SECRET"],
            {
                f"pr-{args.pr}": _submission(f"pr-{args.pr}", bundle, challenger_sealed),
                king.agent_id: _submission(king.agent_id, KING_DIR, _project_credential(KING_DIR)),
                BASELINE_ID: _submission(
                    BASELINE_ID, BASELINE_DIR, _project_credential(BASELINE_DIR)
                ),
            },
        )

        result = run_challenge(
            room=room,
            king_id=king.agent_id,
            challenger_id=f"pr-{args.pr}",
            stack=build_scoring_stack(),
            image_dir=OUTPUT / "images",
            baseline_id=BASELINE_ID,
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


def _submission(agent_id: str, bundle: Path, sealed: str) -> AgentSubmission:
    if not bundle.is_dir():
        raise ChallengeAborted(f"bundle directory is missing: {bundle}")
    return AgentSubmission(
        agent_id=agent_id,
        bundle_b64=_pack(bundle),
        bundle_sha256=_digest(bundle),
        sealed_key=sealed,
    )


def _project_credential(bundle: Path) -> str:
    """The maintainers' sealed key for one project-owned bundle.

    A credential is bound to the hash of every file in its bundle, so the king
    and the baseline need separate ones — and crowning a new king invalidates the
    king's, because the bundle it was bound to no longer exists. Re-sealing is
    therefore part of crowning, not a one-time setup step.

    This fails before the run starts rather than halfway through, so a missing
    credential never costs a challenger their credit.
    """
    path = bundle / SEALED_FILENAME
    if not path.is_file():
        raise ChallengeAborted(
            f"{path} is missing. Seal the project's provider key to the room:\n"
            f"  python imagent_seal.py --room <url> --bundle {bundle} --measurement <id>\n"
            "and commit the ciphertext. Crowning a new king invalidates the previous "
            "king's credential, so this must be redone after every promotion."
        )
    return path.read_text(encoding="utf-8").strip()


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
