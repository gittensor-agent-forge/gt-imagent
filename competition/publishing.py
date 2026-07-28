from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

# Assembling what a challenge publishes.
#
# The governing rule: a published report must let anyone re-derive the objective
# half of the verdict, and must not leak the problem pool. Those pull in opposite
# directions, and the resolution is that prompts appear only as hashes until the
# generator version rotates. Everything else - images, per-requirement pass/fail,
# the judge's raw answers, the attested provenance - is published in full.
#
# Once a generator version is retired, publishing its seeds turns every past
# report into a fully reproducible one. Until then the seed alone is the receipt.

REPORT_SCHEMA_VERSION = "imagent-challenge-1.0"


class LeakError(RuntimeError):
    """Raised when a report would publish something that must stay withheld."""


@dataclass(frozen=True)
class SideSummary:
    """One competitor's contribution to a published challenge report."""

    agent_id: str
    role: str  # "king", "challenger", or "baseline"
    # Per problem id: the fact report as returned by FactReport.to_dict().
    fact_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Per problem id: sha256 of the image bytes, as attested by the room.
    image_hashes: dict[str, str] = field(default_factory=dict)
    # The room's attestation: quote, measurement, and inference provenance.
    attestation: dict[str, Any] = field(default_factory=dict)

    def mean_fact_score(self) -> float:
        scores = [
            float(report.get("fact_score", 0.0)) for report in self.fact_reports.values()
        ]
        return sum(scores) / len(scores) if scores else 0.0


def build_challenge_report(
    *,
    challenge_id: str,
    seed: bytes,
    versions: dict[str, str],
    sides: list[SideSummary],
    match: dict[str, Any],
    judge_verdicts: dict[str, dict[str, Any]],
    prompts: dict[str, str],
) -> dict[str, Any]:
    """Assemble the published record of one challenge.

    `prompts` is used only to compute hashes. It is never carried into the
    result, and `assert_no_prompt_leak` re-checks that before publication.
    """
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "challenge_id": challenge_id,
        # The seed is the receipt: with the generator version, it regenerates
        # every problem once the pool rotates.
        "seed_sha256": hashlib.sha256(seed).hexdigest(),
        "versions": dict(sorted(versions.items())),
        "problems": [
            {
                "problem_id": problem_id,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "judge": judge_verdicts.get(problem_id),
                "sides": {
                    side.role: {
                        "agent_id": side.agent_id,
                        "image_sha256": side.image_hashes.get(problem_id, ""),
                        "facts": side.fact_reports.get(problem_id),
                    }
                    for side in sides
                },
            }
            for problem_id, prompt in sorted(prompts.items())
        ],
        "match": match,
        "agents": [
            {
                "agent_id": side.agent_id,
                "role": side.role,
                "mean_fact_score": round(side.mean_fact_score(), 6),
                "attestation": side.attestation,
            }
            for side in sides
        ],
    }

    assert_no_prompt_leak(report, prompts.values())
    return report


def assert_no_prompt_leak(report: dict[str, Any], prompts) -> None:
    """Fail loudly if any raw prompt survived into the report.

    A leaked prompt is not a cosmetic problem: publishing one report would burn
    the problem it came from, and a pool is only unmemorisable while it is
    unpublished. Cheap to check, so it is checked every time rather than trusted.
    """
    serialised = json.dumps(report, sort_keys=True)
    for prompt in prompts:
        text = str(prompt).strip()
        if len(text) >= 12 and text in serialised:
            raise LeakError(f"report would publish a raw prompt: {text[:60]!r}")


def verify_image_hashes(
    received: dict[str, bytes], attested: dict[str, str]
) -> list[str]:
    """Check delivered image bytes against the hashes the room attested.

    The quote covers the report, and the report carries a hash per image. So
    swapped bytes fail here, and a swapped hash fails the quote. Returns the
    problem ids that did not match; an empty list means every image is accounted
    for.
    """
    mismatches: list[str] = []
    for problem_id, expected in sorted(attested.items()):
        payload = received.get(problem_id)
        if payload is None:
            mismatches.append(problem_id)
            continue
        if hashlib.sha256(payload).hexdigest() != expected:
            mismatches.append(problem_id)
    # Anything delivered that the room never attested is also a mismatch: an
    # extra image is an image nobody signed for.
    for problem_id in sorted(received):
        if problem_id not in attested:
            mismatches.append(problem_id)
    return sorted(set(mismatches))
