from __future__ import annotations

import json
from pathlib import Path

from .models import BenchmarkCase


def suite_dir(name: str) -> Path:
    path = Path(__file__).parent / "suites" / name
    if not path.exists():
        raise FileNotFoundError(f"unknown benchmark suite: {name}")
    return path


def load_cases(name: str) -> list[BenchmarkCase]:
    cases_path = suite_dir(name) / "cases.jsonl"
    if not cases_path.exists():
        raise FileNotFoundError(f"benchmark suite is missing cases.jsonl: {cases_path}")

    cases: list[BenchmarkCase] = []
    with cases_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            if not isinstance(record, dict):
                raise ValueError(f"case line {line_number} must be a JSON object")
            cases.append(BenchmarkCase.from_record(record))
    if not cases:
        raise ValueError(f"benchmark suite has no cases: {cases_path}")
    return cases
