from __future__ import annotations

import sys
from pathlib import Path


# The agent is loaded by path, not installed: the benchmark puts the candidate
# repository root on sys.path and imports `agent.agent`. Mirror that here so the
# tests exercise the same import route the engine uses.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
