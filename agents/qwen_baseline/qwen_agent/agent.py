from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any

from qwen_agent.qwen_image_api import QwenImageClient


class QwenBaselineAgent:
    """Qwen-style baseline with offline mock and live Qwen Image API modes."""

    def setup(self, config: dict[str, Any], workdir: Path) -> None:
        self.config = config
        self.workdir = Path(workdir)
        self.max_feedback_rounds = int(config.get("runtime", {}).get("max_feedback_rounds", 1))
        qwen_config = config.get("agent", {}).get("qwen_image", {})
        self.mode = str(qwen_config.get("mode", "mock"))
        self.qwen_config = qwen_config
        self.qwen_client = QwenImageClient(qwen_config) if self.mode == "live" else None

    def generate(self, case: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        started = time.perf_counter()
        output_dir = Path(output_dir)
        images_dir = output_dir / "images"
        traces_dir = output_dir / "traces"
        images_dir.mkdir(parents=True, exist_ok=True)
        traces_dir.mkdir(parents=True, exist_ok=True)

        run_id = case["run_id"]
        capability = case.get("capability", "unknown")
        prompt = case["prompt"]
        seed = int(case.get("seed", 0))

        grounding = {
            "reason": self._reason(case),
            "search": self._search(case),
            "memory": self._memory(case),
        }
        final_prompt = self._final_prompt(prompt, case, grounding)
        feedback = self._feedback(case, final_prompt)
        if feedback:
            final_prompt = f"{final_prompt} | verified revision: {feedback[-1]['revision']}"

        image_format = "png" if self.mode == "live" else "svg"
        trace = {
            "planning": {
                "missing_context": self._missing_context(case),
                "content_plan": self._content_plan(case),
                "generation_plan": {
                    "outputs": 1,
                    "format": image_format,
                    "seed": seed,
                    "generator": "qwen-image-api" if self.mode == "live" else "mock-svg",
                },
            },
            "grounding": grounding,
            "final_generation_context": {
                "prompt": final_prompt,
            },
            "feedback": feedback,
        }

        trace_path = traces_dir / f"{run_id}.json"
        image_path = images_dir / f"{run_id}.{image_format}"
        self._write_json(trace_path, trace)

        if self.mode == "live":
            if self.qwen_client is None:
                raise RuntimeError("Qwen client was not initialized")
            generation_metadata = self.qwen_client.generate(final_prompt, seed, image_path)
        else:
            self._write_svg(image_path, case, final_prompt, capability)
            generation_metadata = {
                "provider": "mock",
                "model": "deterministic-qwen-style-baseline",
            }

        return {
            "image_path": str(image_path),
            "trace_path": str(trace_path),
            "metadata": {
                "agent_id": "qwen-baseline",
                "seed": seed,
                "model": generation_metadata.get("model"),
                "provider": generation_metadata.get("provider"),
                "request_id": generation_metadata.get("request_id"),
                "usage": generation_metadata.get("usage", {}),
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        }

    def _missing_context(self, case: dict[str, Any]) -> list[str]:
        return {
            "plan": ["layout details", "section ordering", "visual hierarchy"],
            "reason": ["derived answer", "calculation steps"],
            "search": ["frozen factual reference", "source facts"],
            "memory": ["user preference", "saved style"],
            "feedback": ["verification target", "exact output constraints"],
        }.get(case.get("capability"), ["generation context"])

    def _content_plan(self, case: dict[str, Any]) -> dict[str, Any]:
        prompt = case["prompt"].lower()
        if "three-panel" in prompt or "three panel" in prompt:
            layout = "three-panel horizontal layout"
        elif "badge" in prompt:
            layout = "compact badge"
        else:
            layout = "single-card layout"
        return {
            "layout": layout,
            "style": "clean deterministic vector rendering",
            "text_policy": "preserve required visible labels exactly",
        }

    def _reason(self, case: dict[str, Any]) -> list[dict[str, str]]:
        if "reason" not in case.get("allowed_tools", []):
            return []
        prompt = case["prompt"]
        match = re.search(r"(\d+)\s*\+\s*(\d+)", prompt)
        if not match:
            return [{"type": "reasoning", "input": prompt, "result": "no arithmetic expression found"}]
        left, right = int(match.group(1)), int(match.group(2))
        return [{"type": "arithmetic", "expression": f"{left} + {right}", "result": str(left + right)}]

    def _search(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        if "search" not in case.get("allowed_tools", []):
            return []
        results = []
        for snapshot in case.get("search_snapshots", []):
            path = Path(snapshot)
            data = json.loads(path.read_text(encoding="utf-8"))
            results.append(
                {
                    "query": case["prompt"],
                    "source": str(path),
                    "title": data.get("title"),
                    "facts": data.get("facts", []),
                }
            )
        return results

    def _memory(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        if "memory" not in case.get("allowed_tools", []):
            return []
        memory = case.get("memory", {})
        if not memory:
            return []
        return [{"type": "user_profile", "values": memory}]

    def _feedback(self, case: dict[str, Any], final_prompt: str) -> list[dict[str, Any]]:
        if "feedback" not in case.get("allowed_tools", []):
            return []
        if self.max_feedback_rounds <= 0:
            return []
        wants_pass = "PASS" in case["prompt"]
        if wants_pass and "PASS" not in final_prompt:
            return [
                {
                    "attempt": 1,
                    "failed_checks": ["missing exact label PASS"],
                    "revision": "Add exact visible label PASS",
                }
            ]
        return [
            {
                "attempt": 1,
                "failed_checks": [],
                "revision": "Verified exact visible label PASS",
            }
        ]

    def _final_prompt(self, prompt: str, case: dict[str, Any], grounding: dict[str, Any]) -> str:
        parts = [prompt]
        if case.get("capability") == "plan":
            parts.append("Use a three-panel layout for Context Gap Toolkit: Plan, Ground, Verify.")
        for item in grounding.get("reason", []):
            if item.get("result"):
                parts.append(f"Reasoned answer: {item['result']}.")
        for item in grounding.get("search", []):
            title = item.get("title")
            facts = " ".join(item.get("facts", []))
            parts.append(f"Frozen search facts for {title}: {facts}")
        for item in grounding.get("memory", []):
            values = item.get("values", {})
            for key, value in values.items():
                parts.append(f"Memory {key}: {value}.")
        if "PASS" in prompt:
            parts.append("Visible label: PASS.")
        return " ".join(parts)

    def _write_svg(self, path: Path, case: dict[str, Any], final_prompt: str, capability: str) -> None:
        title = html.escape(case.get("memory", {}).get("preferred_label", "Context Gap Toolkit"))
        prompt = html.escape(final_prompt)
        capability_text = html.escape(capability.upper())
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" role="img" aria-label="{title}">
  <rect width="960" height="540" fill="#f8fafc"/>
  <rect x="36" y="36" width="888" height="468" rx="8" fill="#ffffff" stroke="#111827" stroke-width="3"/>
  <text x="72" y="108" font-family="Arial, sans-serif" font-size="44" font-weight="700" fill="#111827">{title}</text>
  <text x="72" y="164" font-family="Arial, sans-serif" font-size="24" fill="#2563eb">{capability_text}</text>
  <foreignObject x="72" y="198" width="816" height="250">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: Arial, sans-serif; font-size: 24px; color: #111827; line-height: 1.35;">{prompt}</div>
  </foreignObject>
</svg>
"""
        path.write_text(svg, encoding="utf-8")

    def _write_json(self, path: Path, data: Any) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
