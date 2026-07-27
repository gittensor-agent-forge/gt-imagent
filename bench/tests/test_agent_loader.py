from __future__ import annotations

import sys
from pathlib import Path

import pytest

from imagent_bench.agent_loader import load_agent


def _imagent_repository() -> Path:
    workspace = Path(__file__).resolve().parents[2]
    sibling_repo = workspace / "imagent"
    if (sibling_repo / "agent" / "agent.py").exists():
        return sibling_repo
    if (workspace / "agent" / "agent.py").exists():
        return workspace
    return sibling_repo


def test_load_agent_does_not_duplicate_sys_path_entries() -> None:
    repository = _imagent_repository()
    if not (repository / "agent" / "agent.py").exists():
        pytest.skip("candidate imagent repository not available")

    repository_path = str(repository)
    before = sys.path.count(repository_path)

    load_agent(repository)
    after_first = sys.path.count(repository_path)

    load_agent(repository)
    after_second = sys.path.count(repository_path)

    # A single load adds at most one entry, and a repeated load must never
    # add a duplicate regardless of any pre-existing sys.path state.
    assert after_first <= before + 1
    assert after_second == after_first
