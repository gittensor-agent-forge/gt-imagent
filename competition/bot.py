from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .github import GitHubClient
from .lifecycle import PENDING, RUNNING, Submission, plan_outcome, plan_screening, plan_start
from .screening import screen_submission
from .status import crown, load_king

# The bot's entry points. Everything it decides lives elsewhere — this is wiring,
# and it is kept thin on purpose so the decisions stay testable without GitHub.
#
# The commands are split along a trust boundary, and that split is the whole
# design:
#
#   screen    runs in the pull request's context, where a fork's untrusted code
#             is checked out. It has NO token and NO secrets. It only writes a
#             verdict file.
#   apply     runs afterwards in the base repository, where the token lives. It
#             reads that verdict and never checks out the submission.
#
# Merging those two would mean handing write access to a job that has untrusted
# code on disk. That is the mistake this layout exists to prevent.

SEALED_FILENAME = "sealed_inference_key"
VERDICT_VERSION = "imagent-verdict-1.0"


# --- reading a submission ----------------------------------------------------


def read_bundle(directory: str | Path) -> tuple[dict[str, bytes], str]:
    """Load a submission's files and its sealed credential.

    The credential is returned separately because it is not part of the bundle
    the miner sealed against — including it in the hashed files would make every
    binding self-referential.
    """
    root = Path(directory)
    if not root.is_dir():
        raise SystemExit(f"not a submission directory: {root}")

    files: dict[str, bytes] = {}
    sealed = ""
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == SEALED_FILENAME:
            sealed = path.read_text(encoding="utf-8").strip()
            continue
        files[relative] = path.read_bytes()
    return files, sealed


def find_submission(root: str | Path = "submissions") -> Path | None:
    """The one submission directory a challenge pull request adds."""
    directory = Path(root)
    candidates = [
        entry for entry in sorted(directory.glob("*")) if entry.is_dir() and not entry.name.startswith(".")
    ]
    return candidates[-1] if candidates else None


# --- the commands ------------------------------------------------------------


def command_screen(args: argparse.Namespace) -> int:
    """Untrusted context. Decide, write a verdict, touch nothing."""
    bundle = Path(args.bundle) if args.bundle else find_submission()
    if bundle is None:
        raise SystemExit("no submission directory found")

    files, sealed = read_bundle(bundle)
    reasons = screen_submission(
        bundle_files=files,
        sealed_key=sealed,
        archived_hashes=_archived_hashes(args.archive),
    )

    verdict = {
        "version": VERDICT_VERSION,
        "pull_request": args.pr,
        "author": args.author,
        "bundle_dir": str(bundle),
        "passed": not reasons,
        "reasons": reasons,
    }
    Path(args.out).write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for reason in reasons:
        print(f"::error::{reason}")
    print(f"screening {'passed' if not reasons else 'failed'} for #{args.pr}")
    # Exit 0 either way: a rejected submission is a normal outcome, and a red X
    # on every bad submission tells a miner less than the comment the bot leaves.
    return 0


def command_apply(args: argparse.Namespace) -> int:
    """Trusted context. Apply a verdict written by the untrusted job."""
    verdict = json.loads(Path(args.verdict).read_text(encoding="utf-8"))
    if verdict.get("version") != VERDICT_VERSION:
        raise SystemExit(f"unsupported verdict file: {verdict.get('version')!r}")

    client = _client(args)
    number = int(verdict["pull_request"])
    author = str(verdict["author"])
    open_submissions = client.list_submissions()
    current = next(
        (item for item in open_submissions if item.number == number),
        Submission(number=number, author=author),
    )

    actions = plan_screening(
        current,
        reasons=list(verdict.get("reasons", [])),
        open_submissions=open_submissions,
    )
    for line in client.apply(actions):
        print(line)
    return 0


def command_tick(args: argparse.Namespace) -> int:
    """Start the oldest waiting challenger, if the queue is free.

    Scheduled rather than triggered by the pull request: the queue must run one
    duel at a time, and a schedule makes that a property of the system instead of
    something every trigger has to remember.
    """
    client = _client(args)
    submissions = client.list_submissions()
    pending = [item for item in submissions if PENDING in item.labels]
    running = [item for item in submissions if RUNNING in item.labels]

    actions = plan_start(pending=pending, running=running)
    for line in client.apply(actions):
        print(line)

    started = next((action.pull_request for action in actions if action.kind == "label"), None)
    if started is None:
        print("nothing to start" if not pending else f"a duel is already running: {running[0].number}")
        # No challenger and no error. The workflow reads this file to decide
        # whether there is anything to run.
        Path(args.out).write_text(json.dumps({"started": None}) + "\n", encoding="utf-8")
        return 0

    chosen = next(item for item in pending if item.number == started)
    Path(args.out).write_text(
        json.dumps({"started": started, "author": chosen.author}) + "\n", encoding="utf-8"
    )
    print(f"started #{started}")
    return 0


def command_resolve(args: argparse.Namespace) -> int:
    """Apply a finished duel: label, comment, close or merge, and crown."""
    outcome = json.loads(Path(args.outcome).read_text(encoding="utf-8"))
    client = _client(args)
    number = int(outcome["pull_request"])

    submissions = client.list_submissions()
    challenger = next(
        (item for item in submissions if item.number == number),
        Submission(number=number, author=str(outcome.get("author", ""))),
    )
    king_record = load_king(args.king_path)
    king_submission = next(
        (item for item in submissions if king_record and item.number == king_record.submission),
        None,
    )

    promoted = bool(outcome.get("promoted"))
    aborted = str(outcome.get("aborted", ""))

    # Crown BEFORE announcing it. A comment saying "you are the new king" beside a
    # crown that was never installed is the one inconsistency a miner would be
    # right to distrust.
    if promoted and not aborted:
        king = crown(
            agent_id=str(outcome["agent_id"]),
            submission=number,
            commit_sha=str(outcome["commit_sha"]),
            crowned_at=_now(),
            challenge_id=str(outcome["challenge_id"]),
            bundle_dir=Path(outcome["bundle_dir"]),
            path=args.king_path,
            agent_dir=args.king_agent_dir,
        )
        print(f"crowned {king.agent_id} from #{number}")

    actions = plan_outcome(
        challenger,
        promoted=promoted,
        match=outcome.get("match", {}),
        challenge_id=str(outcome.get("challenge_id", "")),
        king_submission=king_submission,
        aborted=aborted,
    )
    for line in client.apply(actions):
        print(line)
    return 0


# --- helpers -----------------------------------------------------------------


def _client(args: argparse.Namespace) -> GitHubClient:
    return GitHubClient(
        args.repository or os.environ.get("GITHUB_REPOSITORY", ""),
        os.environ.get("GITHUB_TOKEN", ""),
        dry_run=args.dry_run,
    )


def _archived_hashes(path: str | None) -> set[str]:
    if not path or not Path(path).is_file():
        return set()
    return {
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="competition.bot", description="The Imagent lifecycle bot.")
    parser.add_argument("--repository", default="", help="owner/name (default: $GITHUB_REPOSITORY)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    sub = parser.add_subparsers(dest="command", required=True)

    screen = sub.add_parser("screen", help="untrusted: screen a submission and write a verdict")
    screen.add_argument("--pr", type=int, required=True)
    screen.add_argument("--author", required=True)
    screen.add_argument("--bundle", default="")
    screen.add_argument("--archive", default="kings/archived-hashes.txt")
    screen.add_argument("--out", default="verdict.json")
    screen.set_defaults(func=command_screen)

    apply_ = sub.add_parser("apply", help="trusted: act on a verdict")
    apply_.add_argument("--verdict", default="verdict.json")
    apply_.set_defaults(func=command_apply)

    tick = sub.add_parser("tick", help="trusted: start the oldest waiting challenger")
    tick.add_argument("--out", default="started.json")
    tick.set_defaults(func=command_tick)

    resolve = sub.add_parser("resolve", help="trusted: apply a finished duel and crown")
    resolve.add_argument("--outcome", default="challenge-output/outcome.json")
    resolve.add_argument("--king-path", default="kings/current.json")
    resolve.add_argument("--king-agent-dir", default="kings/current")
    resolve.set_defaults(func=command_resolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
