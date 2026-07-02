from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

try:
    from .common import relative_to_output
    from .generation import GenerationMixin
    from .grounding import GroundingMixin
    from .image_backend_api import ImageBackendClient
    from .rendering import RenderingMixin
    from .verifier import build_image_verifier
except ImportError:  # pragma: no cover - manifest loader imports this module outside a package
    from common import relative_to_output
    from generation import GenerationMixin
    from grounding import GroundingMixin
    from image_backend_api import ImageBackendClient
    from rendering import RenderingMixin
    from verifier import build_image_verifier


class ImageAgent(GroundingMixin, GenerationMixin, RenderingMixin):
    """General image agent with a structured planning and verification loop."""

    def setup(self, config: dict[str, Any], workdir: Path) -> None:
        self.config = config
        self.workdir = Path(workdir)
        runtime = config.get("runtime", {})
        self.max_feedback_rounds = int(runtime.get("max_feedback_rounds", 1))
        image_config = config.get("agent", {}).get("image_backend", {})
        self.mode = str(image_config.get("mode", "mock"))
        self.image_config = image_config
        self.client = ImageBackendClient(image_config) if self.mode == "live" else None
        self.verifier = build_image_verifier(config, self.workdir)

    def generate(self, case: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        started = time.perf_counter()
        output_dir = Path(output_dir)
        images_dir = output_dir / "images"
        traces_dir = output_dir / "traces"
        images_dir.mkdir(parents=True, exist_ok=True)
        traces_dir.mkdir(parents=True, exist_ok=True)

        run_id = case["run_id"]
        seed = int(case.get("seed", 0))
        grounding_bundle = self._build_grounding_bundle(case)
        grounding = grounding_bundle.grounding
        tool_calls = list(grounding_bundle.tool_calls)
        initial_spec = self._build_generation_spec(case, grounding)
        tool_calls.append(
            {
                "tool": "planner",
                "arguments": {
                    "capability": str(case.get("capability", "unknown")),
                    "prompt": str(case.get("prompt", "")),
                },
                "result_count": 1,
                "result": {
                    "title": initial_spec["title"],
                    "layout": initial_spec["layout"],
                    "must_include_count": len(initial_spec["must_include"]),
                },
            }
        )

        feedback_entries: list[dict[str, Any]] = []
        feedback_attempts: list[dict[str, Any]] = []
        selected_candidate: dict[str, Any] | None = None
        selected_spec = copy.deepcopy(initial_spec)
        working_spec = copy.deepcopy(initial_spec)
        total_generation_cost = 0.0
        total_verifier_cost = 0.0
        total_candidates = 0
        round_count = 1 if self.max_feedback_rounds <= 0 else 2

        for round_index in range(round_count):
            candidates: list[dict[str, Any]] = []
            for candidate_index, candidate_seed in enumerate(self._candidate_seeds(seed, round_index)):
                variant = self._candidate_variant(round_index, candidate_index)
                candidate = self._generate_candidate(
                    case=case,
                    output_dir=output_dir,
                    run_id=run_id,
                    seed=candidate_seed,
                    round_index=round_index,
                    candidate_index=candidate_index,
                    spec=working_spec,
                    variant=variant,
                    grounding=grounding,
                    tool_calls=tool_calls,
                )
                total_generation_cost += float(candidate["metadata"].get("cost_usd", 0.0) or 0.0)
                verification = self._score_candidate(case, output_dir, candidate, working_spec)
                total_verifier_cost += float(verification["cost_usd"])
                candidate.update(verification)
                candidates.append(candidate)
                total_candidates += 1
                feedback_attempts.append(
                    {
                        "round": round_index,
                        "candidate_index": candidate_index,
                        "candidate_image_path": relative_to_output(candidate["image_path"], output_dir),
                        "candidate_prompt": candidate["prompt"],
                        "score": round(float(candidate["score"]), 6),
                        "failed_checks": list(candidate["failed_checks"]),
                        "critique": list(candidate["critique"]),
                        "selected": False,
                    }
                )

            best = max(
                candidates,
                key=lambda item: (
                    float(item["score"]),
                    -float(item["metadata"].get("latency_ms", 0.0) or 0.0),
                    -int(item["candidate_index"]),
                ),
            )
            feedback_entries.append(
                {
                    "round": round_index,
                    "candidate_index": best["candidate_index"],
                    "candidate_image_path": relative_to_output(best["image_path"], output_dir),
                    "candidate_prompt": best["prompt"],
                    "score": round(float(best["score"]), 6),
                    "failed_checks": list(best["failed_checks"]),
                    "critique": list(best["critique"]),
                    "selected": False,
                }
            )

            selected_candidate = best
            selected_spec = copy.deepcopy(working_spec)
            if best["passed"] or round_index == round_count - 1:
                break
            working_spec = self._revise_spec(working_spec, best["failed_checks"])

        if selected_candidate is None:
            raise RuntimeError("agent did not produce any candidate")

        feedback_entries[-1]["selected"] = True
        for attempt in feedback_attempts:
            if (
                int(attempt["round"]) == int(selected_candidate["round"])
                and int(attempt["candidate_index"]) == int(selected_candidate["candidate_index"])
            ):
                attempt["selected"] = True
                break
        final_image_path = self._promote_winner(selected_candidate["image_path"], output_dir / "images", run_id)
        final_trace_path = traces_dir / f"{run_id}.json"
        trace = self._build_trace(
            case=case,
            base_seed=seed,
            output_dir=output_dir,
            final_image_path=final_image_path,
            grounding=grounding,
            tool_calls=tool_calls,
            generation_spec=selected_spec,
            final_prompt=selected_candidate["prompt"],
            feedback=feedback_entries,
            feedback_attempts=feedback_attempts,
            candidate_count=total_candidates,
            round_count=len(feedback_entries),
            selected_candidate=selected_candidate,
        )
        self._write_json(final_trace_path, trace)

        selected_metadata = dict(selected_candidate["metadata"])
        selected_metadata["cost_usd"] = round(total_generation_cost + total_verifier_cost, 6)
        selected_metadata["generation_cost_usd"] = round(total_generation_cost, 6)
        selected_metadata["internal_judge_cost_usd"] = round(total_verifier_cost, 6)
        selected_metadata["candidate_count"] = total_candidates
        selected_metadata["selected_candidate_index"] = int(selected_candidate["candidate_index"])
        selected_metadata["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        selected_metadata["agent_id"] = "image-agent"
        selected_metadata["seed"] = seed

        return {
            "image_path": str(final_image_path),
            "trace_path": str(final_trace_path),
            "metadata": selected_metadata,
        }
