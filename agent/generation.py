from __future__ import annotations

import copy
import json
import shutil
import time
from pathlib import Path
from typing import Any

try:
    from .common import dedupe_strings, relative_to_output
    from .constants import VARIANT_CONFIGS
except ImportError:  # pragma: no cover - manifest loader imports modules outside a package
    from common import dedupe_strings, relative_to_output
    from constants import VARIANT_CONFIGS


class GenerationMixin:
    def _candidate_seeds(self, seed: int, round_index: int) -> list[int]:
        base = seed if round_index == 0 else seed + 100
        return [base, base + 1]

    def _candidate_variant(self, round_index: int, candidate_index: int) -> dict[str, Any]:
        variant = dict(VARIANT_CONFIGS[candidate_index % len(VARIANT_CONFIGS)])
        if round_index > 0:
            variant["focus"] = "revised exact-text validation emphasis"
        return variant

    def _build_candidate_prompt(
        self,
        spec: dict[str, Any],
        variant: dict[str, Any],
        round_index: int,
        candidate_index: int,
    ) -> str:
        lines = [
            "Create a polished image from the structured generation spec.",
            f"Round: {round_index}",
            f"Candidate: {candidate_index}",
            f"Title: {spec['title']}",
            f"Layout: {spec['layout'].replace('_', '-')}",
            f"Style: {spec['style']}",
            f"Variant focus: {variant['focus']}",
        ]
        if spec["layout"] == "three_panel":
            lines.append("Use three visibly separated panels or columns.")
        elif spec["layout"] == "badge":
            lines.append("Use a compact badge-like composition centered on the main label.")
        else:
            lines.append("Use a single card or poster surface, not multiple separate panels.")
        lines.append("Must include these exact visible strings:")
        lines.extend(f"- {value}" for value in spec["must_include"])
        if spec["visible_text"]:
            lines.append("Visible supporting text:")
            lines.extend(f"- {value}" for value in spec["visible_text"])
        reasoning = spec.get("reasoning_result", {})
        if reasoning.get("display"):
            lines.append(f"Reasoning result to display: {reasoning['display']}")
        if spec["grounded_facts"]:
            lines.append("Grounded facts to display without invention:")
            lines.extend(f"- {fact}" for fact in spec["grounded_facts"])
        if spec["visual_constraints"]:
            lines.append(
                "Visual constraints: "
                + json.dumps(spec["visual_constraints"], sort_keys=True, ensure_ascii=True)
            )
        if spec["avoid"]:
            lines.append("Avoid:")
            lines.extend(f"- {item}" for item in spec["avoid"])
        lines.append("Exact visible text is more important than decoration.")
        return "\n".join(lines)

    def _generate_candidate(
        self,
        case: dict[str, Any],
        output_dir: Path,
        run_id: str,
        seed: int,
        round_index: int,
        candidate_index: int,
        spec: dict[str, Any],
        variant: dict[str, Any],
        grounding: dict[str, list[dict[str, Any]]],
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        candidate_prompt = self._build_candidate_prompt(spec, variant, round_index, candidate_index)
        candidate_dir = output_dir / "images" / "candidates" / run_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        candidate_image_path = candidate_dir / f"round-{round_index}-candidate-{candidate_index}.png"

        started = time.perf_counter()
        if self.mode == "live":
            if self.client is None:
                raise RuntimeError("image backend client was not initialized")
            metadata = self.client.generate(candidate_prompt, seed, candidate_image_path)
            candidate_image_path = Path(metadata["image_path"])
        else:
            self._write_svg(candidate_image_path.with_suffix(".svg"), spec, variant)
            candidate_image_path = candidate_image_path.with_suffix(".svg")
            metadata = {
                "image_path": str(candidate_image_path),
                "provider": "mock",
                "model": "deterministic-image-agent-mock",
                "usage": {},
                "cost_usd": 0.0,
            }
        metadata = dict(metadata)
        metadata["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        case_id = str(case.get("id") or case.get("run_id") or "unknown-case")

        return {
            "case_id": case_id,
            "round": round_index,
            "candidate_index": candidate_index,
            "prompt": candidate_prompt,
            "image_path": candidate_image_path,
            "metadata": metadata,
            "trace": {
                "planning": {
                    "missing_context": self._missing_context(case),
                    "content_plan": self._content_plan(spec),
                    "generation_plan": {
                        "outputs": 2,
                        "format": candidate_image_path.suffix.lstrip("."),
                        "seed": seed,
                        "generator": "live-image-backend" if self.mode == "live" else "mock-svg",
                        "round": round_index,
                        "candidate_index": candidate_index,
                    },
                    "generation_spec": spec,
                },
                "grounding": grounding,
                "tool_calls": tool_calls,
                "final_generation_context": {"prompt": candidate_prompt},
                "feedback": [],
            },
        }

    def _score_candidate(
        self,
        case: dict[str, Any],
        output_dir: Path,
        candidate: dict[str, Any],
        spec: dict[str, Any],
    ) -> dict[str, Any]:
        checks = self._verification_checks(case, spec)
        if not checks:
            return {"score": 1.0, "passed": True, "failed_checks": [], "critique": [], "cost_usd": 0.0}

        verifier_case = {
            "id": str(case.get("id") or case.get("run_id") or "unknown-case"),
            "prompt": case["prompt"],
        }
        before_cost = float(getattr(self.verifier, "total_cost_usd", 0.0) or 0.0)
        verdicts = self.verifier.evaluate_image_checks(
            verifier_case,
            {"image_path": str(candidate["image_path"])},
            candidate["trace"],
            checks,
        )
        after_cost = float(getattr(self.verifier, "total_cost_usd", 0.0) or 0.0)

        passed = 0
        failed_checks: list[str] = []
        for index, check in enumerate(checks):
            verdict = verdicts.get(index)
            if verdict and verdict.get("passed"):
                passed += 1
            else:
                failed_checks.append(str(check["value"]))

        failed_checks = dedupe_strings(failed_checks)
        critique = [f"Add exact visible text: {value}" for value in failed_checks]
        score = passed / len(checks)
        return {
            "score": score,
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "critique": critique,
            "cost_usd": max(0.0, after_cost - before_cost),
        }

    def _verification_checks(self, case: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, str]]:
        expected = case.get("expected", {})
        if isinstance(expected, dict):
            public_checks = [
                check
                for check in expected.get("checks", [])
                if isinstance(check, dict) and check.get("type") == "image_contains" and check.get("value")
            ]
            if public_checks:
                return [{"type": "image_contains", "value": str(check["value"])} for check in public_checks]
        return [{"type": "image_contains", "value": value} for value in self._verification_values(spec)]

    def _verification_values(self, spec: dict[str, Any]) -> list[str]:
        return dedupe_strings([str(value) for value in spec.get("must_include", [])])

    def _revise_spec(self, spec: dict[str, Any], failed_checks: list[str]) -> dict[str, Any]:
        revised = copy.deepcopy(spec)
        revised["must_include"] = dedupe_strings(list(revised["must_include"]) + list(failed_checks))
        visible_text = list(revised["visible_text"])
        for value in failed_checks:
            if value != revised["title"]:
                visible_text.append(value)
        revised["visible_text"] = dedupe_strings(visible_text)
        revised["avoid"] = dedupe_strings(
            list(revised["avoid"]) + ["Do not omit exact must-include strings.", "Prioritize visible labels over style."]
        )
        revised["visual_constraints"] = dict(revised["visual_constraints"])
        revised["visual_constraints"]["revision_focus"] = "exact visible text"
        return revised

    def _promote_winner(self, winner_path: Path, images_dir: Path, run_id: str) -> Path:
        final_path = images_dir / f"{run_id}{winner_path.suffix}"
        shutil.copy2(winner_path, final_path)
        return final_path

    def _build_trace(
        self,
        case: dict[str, Any],
        base_seed: int,
        output_dir: Path,
        final_image_path: Path,
        grounding: dict[str, list[dict[str, Any]]],
        tool_calls: list[dict[str, Any]],
        generation_spec: dict[str, Any],
        final_prompt: str,
        feedback: list[dict[str, Any]],
        feedback_attempts: list[dict[str, Any]],
        candidate_count: int,
        round_count: int,
        selected_candidate: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "planning": {
                "missing_context": self._missing_context(case),
                "content_plan": self._content_plan(generation_spec),
                "generation_plan": {
                    "outputs": candidate_count,
                    "format": final_image_path.suffix.lstrip("."),
                    "seed": base_seed,
                    "generator": "live-image-backend" if self.mode == "live" else "mock-svg",
                    "rounds": round_count,
                    "selected_candidate_index": selected_candidate["candidate_index"],
                },
                "generation_spec": generation_spec,
            },
            "grounding": grounding,
            "tool_calls": tool_calls,
            "final_generation_context": {
                "prompt": final_prompt,
            },
            "feedback": feedback,
            "feedback_attempts": feedback_attempts,
        }
