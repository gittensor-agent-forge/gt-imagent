from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .lifecycle import PENDING, RUNNING, Submission
from .ranking import build_leaderboard, load_comparisons, rank

# Who holds the crown, who is waiting, and how everyone stands.
#
# `kings/current/` is a full copy of the winning agent, not a pointer to it. A
# challenger forks that directory and the room runs exactly those bytes when the
# king defends, so the crown cannot drift away from the code that won it.
#
# There is no archive. Every past king is already preserved twice — its pull
# request stays in `submissions/`, and git history holds every state this
# directory has been in. A third copy would be a third thing to keep in sync.
#
# The defence record is the exception: how many challenges an agent has survived
# is the one thing not recoverable from the code, so it is written down.

KINGS_DIR = Path("kings")
CURRENT_KING_PATH = KINGS_DIR / "current.json"
CURRENT_AGENT_DIR = KINGS_DIR / "current"
SCHEMA_VERSION = "imagent-king-1.0"

MANIFEST_NAME = "agent.yaml"
# The miner's sealed credential is deliberately NOT carried into the crown. It is
# bound to their submission and paid for by them; a king's defences are funded by
# the project. Copying it would bill every future defence to whoever last won.
EXCLUDED_FROM_CROWN = frozenset({"sealed_inference_key"})
EXCLUDED_DIRS = frozenset({".git", "__pycache__"})


@dataclass(frozen=True)
class King:
    agent_id: str
    submission: int
    commit_sha: str
    crowned_at: str
    defenses: int = 0
    challenges: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "agent_id": self.agent_id,
            "submission": self.submission,
            "commit_sha": self.commit_sha,
            "crowned_at": self.crowned_at,
            "defenses": self.defenses,
            "challenges": list(self.challenges),
        }


class KingError(RuntimeError):
    """Raised when the reign record or the crowned agent cannot be read or written."""


def load_king(path: str | Path = CURRENT_KING_PATH) -> King | None:
    """Read the reigning agent, or None before the first crowning."""
    king_path = Path(path)
    if not king_path.exists():
        return None
    try:
        raw = json.loads(king_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise KingError(f"{king_path}: reign record is unreadable: {error}") from error
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        raise KingError(f"{king_path}: unsupported reign record")
    try:
        return King(
            agent_id=str(raw["agent_id"]),
            submission=int(raw["submission"]),
            commit_sha=str(raw["commit_sha"]),
            crowned_at=str(raw["crowned_at"]),
            defenses=int(raw.get("defenses", 0)),
            challenges=tuple(str(item) for item in raw.get("challenges", [])),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise KingError(f"{king_path}: reign record is missing fields: {error}") from error


def record_defense(
    king: King, challenge_id: str, *, path: str | Path = CURRENT_KING_PATH
) -> King:
    """A successful defence. This is the number a reign is actually measured in."""
    defended = King(
        agent_id=king.agent_id,
        submission=king.submission,
        commit_sha=king.commit_sha,
        crowned_at=king.crowned_at,
        defenses=king.defenses + 1,
        challenges=(*king.challenges, challenge_id),
    )
    _write(Path(path), defended)
    return defended


def install_agent(bundle_dir: str | Path, target_dir: str | Path = CURRENT_AGENT_DIR) -> list[str]:
    """Copy a winning bundle into the crown, completely and verbatim.

    Staged then swapped: the new copy is built beside the target and only
    replaces it once it is complete. A half-copied crown would leave the
    competition with an agent that cannot load and no obvious way to tell.

    Returns the file names installed.
    """
    source = Path(bundle_dir)
    if not source.is_dir():
        raise KingError(f"not a bundle directory: {source}")
    if not (source / MANIFEST_NAME).is_file():
        raise KingError(f"bundle has no {MANIFEST_NAME}: {source}")

    target = Path(target_dir)
    staging = target.parent / f".{target.name}.incoming"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    installed: list[str] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file():
            shutil.rmtree(staging, ignore_errors=True)
            raise KingError(f"a crowned bundle may contain only regular files: {relative}")
        if relative.as_posix() in EXCLUDED_FROM_CROWN:
            continue
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        installed.append(relative.as_posix())

    if MANIFEST_NAME not in installed:
        shutil.rmtree(staging, ignore_errors=True)
        raise KingError(f"bundle has no {MANIFEST_NAME} to install")

    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    return installed


def crown(
    *,
    agent_id: str,
    submission: int,
    commit_sha: str,
    crowned_at: str,
    challenge_id: str,
    bundle_dir: str | Path,
    path: str | Path = CURRENT_KING_PATH,
    agent_dir: str | Path = CURRENT_AGENT_DIR,
) -> King:
    """Install the winning agent and record the new reign.

    The code is installed FIRST. A reign record pointing at an agent that was
    never copied is a crown nobody can defend; the reverse is a stale record
    beside working code, which is visible and fixable.
    """
    install_agent(bundle_dir, agent_dir)

    incoming = King(
        agent_id=agent_id,
        submission=submission,
        commit_sha=commit_sha,
        crowned_at=crowned_at,
        defenses=0,
        challenges=(challenge_id,),
    )
    _write(Path(path), incoming)
    return incoming


def status(
    *,
    submissions: list[Submission],
    king_path: str | Path = CURRENT_KING_PATH,
    agent_dir: str | Path = CURRENT_AGENT_DIR,
    match_log: str | Path | None = None,
) -> dict[str, Any]:
    """One snapshot of the competition: the crown, the queue, the standings."""
    king = load_king(king_path)
    pending = [item for item in submissions if PENDING in item.labels]
    running = [item for item in submissions if RUNNING in item.labels]

    leaderboard: list[dict[str, Any]] = []
    if match_log is not None and Path(match_log).exists():
        leaderboard = build_leaderboard(rank(load_comparisons(match_log)))

    return {
        "king": king.to_dict() if king else None,
        # A reign record with no agent beside it is a crown nobody can defend, so
        # it is worth surfacing rather than discovering mid-challenge.
        "king_agent_installed": (Path(agent_dir) / MANIFEST_NAME).is_file(),
        "queue": {
            "running": [item.number for item in running],
            "pending": [
                item.number
                for item in sorted(pending, key=lambda entry: (entry.created_at, entry.number))
            ],
            "depth": len(pending),
            # One duel at a time, so the queue is either moving or blocked.
            "accepting": not running,
        },
        "leaderboard": leaderboard,
    }


def _write(path: Path, king: King) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(king.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = [
    "King",
    "KingError",
    "crown",
    "install_agent",
    "load_king",
    "record_defense",
    "status",
]
