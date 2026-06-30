from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def promote(result_path: Path, baseline_dir: Path, commit_sha: str | None = None) -> dict[str, Any]:
    result = _load_json(result_path)
    commit = commit_sha or os.environ.get("GITHUB_SHA") or "unknown"
    promoted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date = promoted_at[:10]
    short_commit = commit[:12] if commit != "unknown" else "unknown"

    promoted = {
        "promoted": True,
        "promoted_at": promoted_at,
        "commit": commit,
        "agent": result.get("agent", {}),
        "suite": result.get("suite", {}),
        "config": result.get("config", {}),
        "runtime": result.get("runtime", {}),
        "evaluation": result.get("evaluation", {}),
        "metrics": result.get("metrics", {}),
        "source_result": str(result_path),
    }

    history_path = baseline_dir / "history" / f"{date}-main-{short_commit}.json"
    latest_path = baseline_dir / "latest.json"
    _write_json(history_path, promoted)
    _write_json(latest_path, promoted | {"history_path": str(history_path)})
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a benchmark result to baseline history.")
    parser.add_argument("--result", required=True)
    parser.add_argument("--baseline-dir", required=True)
    parser.add_argument("--commit-sha", default=None)
    args = parser.parse_args()

    promoted = promote(Path(args.result), Path(args.baseline_dir), args.commit_sha)
    print(
        "Promoted baseline:",
        promoted.get("agent", {}).get("id"),
        promoted.get("suite", {}).get("id"),
        promoted.get("metrics", {}).get("ia_score"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
