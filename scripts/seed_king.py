"""Crown the reference agent as the first king.

Run once, when the competition opens. Every challenge needs an incumbent to
fight; without a reign record the first duel aborts before it starts.

The genesis king has submission number 0 because it arrived by no pull request.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from competition.status import crown, load_king  # noqa: E402

GENESIS = "genesis"


def main() -> int:
    if load_king() is not None:
        print("a king already reigns; refusing to overwrite the reign record")
        return 1

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()

    king = crown(
        agent_id="reference-agent",
        submission=0,
        commit_sha=commit or "unknown",
        crowned_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        challenge_id=GENESIS,
        bundle_dir=Path("kings/current"),
    )
    print(f"crowned {king.agent_id} at {king.crowned_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
