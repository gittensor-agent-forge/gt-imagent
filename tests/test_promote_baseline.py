from __future__ import annotations

import json
from pathlib import Path

from imagent_bench.promote_baseline import promote
from imagent_bench.runner import run


def test_promote_writes_latest_and_history(tmp_path: Path) -> None:
    result = run(Path("configs/qwen-smoke.yaml").resolve(), "agents/qwen_baseline", tmp_path / "run")
    promoted = promote(tmp_path / "run" / "results.json", tmp_path / "baseline", "abcdef1234567890")

    latest_path = tmp_path / "baseline" / "latest.json"
    history_files = list((tmp_path / "baseline" / "history").glob("*.json"))

    assert promoted["commit"] == "abcdef1234567890"
    assert latest_path.exists()
    assert len(history_files) == 1
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest["agent"]["id"] == result["agent"]["id"]
    assert latest["metrics"]["ia_score"] == result["metrics"]["ia_score"]
