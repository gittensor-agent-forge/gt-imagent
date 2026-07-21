from __future__ import annotations

from imagent_bench.models import BenchmarkCase


def test_from_record_tolerates_non_integer_id_and_seed() -> None:
    case = BenchmarkCase.from_record(
        {
            "id": "case-1",
            "ID": "not-a-number",
            "seed": "also-not-a-number",
            "prompt": "draw a cat",
        }
    )

    assert case.id == "case-1"
    assert case.numeric_id == 0
    assert case.seed == 0
