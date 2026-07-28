"""Install the winning agent as the new king.

Run only after a duel promoted. Reads the challenge output the workflow wrote and
copies the challenger's bundle into `kings/current/` in full.

This is the one irreversible step in a challenge, so it does exactly one thing
and refuses anything ambiguous.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from competition.status import crown  # noqa: E402

PROMOTED = Path("challenge-output/promoted.json")


def main() -> int:
    if not PROMOTED.is_file():
        print(f"{PROMOTED} is missing; nothing was promoted", file=sys.stderr)
        return 1

    record = json.loads(PROMOTED.read_text(encoding="utf-8"))
    bundle = Path(record["bundle_dir"])
    if not bundle.is_dir():
        print(f"winning bundle not found: {bundle}", file=sys.stderr)
        return 1

    king = crown(
        agent_id=str(record["agent_id"]),
        submission=int(record["submission"]),
        commit_sha=str(record["commit_sha"]),
        crowned_at=str(record["crowned_at"]),
        challenge_id=str(record["challenge_id"]),
        bundle_dir=bundle,
    )
    print(f"crowned {king.agent_id} from submission #{king.submission}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
