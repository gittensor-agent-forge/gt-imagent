from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any


class EchoAgent:
    def setup(self, config: dict[str, Any], workdir: Path) -> None:
        self.config = config
        self.workdir = Path(workdir)

    def generate(self, case: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        started = time.perf_counter()
        output_dir = Path(output_dir)
        run_id = case["run_id"]
        final_prompt = self._final_prompt(case)
        trace = {
            "planning": {
                "missing_context": self._missing_context(case),
            },
            "grounding": {
                "reason": self._reason(case),
                "search": self._search(case),
                "memory": self._memory(case),
            },
            "final_generation_context": {
                "prompt": final_prompt,
            },
            "feedback": self._feedback(case),
        }
        trace_path = output_dir / "traces" / f"{run_id}.json"
        image_path = output_dir / "images" / f"{run_id}.svg"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        image_path.write_text(self._svg(final_prompt), encoding="utf-8")
        return {
            "image_path": str(image_path),
            "trace_path": str(trace_path),
            "metadata": {
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "seed": case["seed"],
            },
        }

    def _missing_context(self, case: dict[str, Any]) -> list[str]:
        return {
            "plan": ["layout details"],
            "reason": ["derived answer"],
            "search": ["frozen factual reference"],
            "memory": ["user preference"],
            "feedback": ["verification target"],
        }.get(case.get("capability"), ["generation context"])

    def _reason(self, case: dict[str, Any]) -> list[dict[str, str]]:
        if "reason" not in case.get("allowed_tools", []):
            return []
        prompt = case["prompt"]
        add = re.search(r"(\d+)\s*\+\s*(\d+)", prompt)
        mult = re.search(r"(\d+)\s*\*\s*(\d+)", prompt)
        if add:
            return [{"type": "arithmetic", "result": str(int(add.group(1)) + int(add.group(2)))}]
        if mult:
            return [{"type": "arithmetic", "result": str(int(mult.group(1)) * int(mult.group(2)))}]
        return [{"type": "reasoning", "result": "not applicable"}]

    def _search(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        if "search" not in case.get("allowed_tools", []):
            return []
        results = []
        for snapshot in case.get("search_snapshots", []):
            data = json.loads(Path(snapshot).read_text(encoding="utf-8"))
            results.append({"title": data.get("title"), "facts": data.get("facts", [])})
        return results

    def _memory(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        if "memory" not in case.get("allowed_tools", []):
            return []
        return [{"values": case.get("memory", {})}]

    def _feedback(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        if "feedback" not in case.get("allowed_tools", []):
            return []
        return [{"attempt": 1, "failed_checks": [], "revision": "Verified exact visible label PASS"}]

    def _final_prompt(self, case: dict[str, Any]) -> str:
        parts = [case["prompt"]]
        if case.get("capability") == "plan":
            parts.append("Context Gap Toolkit three-panel layout: Plan, Ground, Verify.")
        for item in self._reason(case):
            parts.append(f"Answer: {item['result']}.")
        for item in self._search(case):
            parts.append(f"{item['title']}: {' '.join(item['facts'])}")
        for item in self._memory(case):
            parts.append(json.dumps(item["values"], sort_keys=True))
        if "PASS" in case["prompt"]:
            parts.append("PASS")
        return " ".join(parts)

    def _svg(self, text: str) -> str:
        safe_text = html.escape(text)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
  <rect width="640" height="360" fill="#ffffff"/>
  <text x="32" y="64" font-family="Arial" font-size="22" fill="#111827">{safe_text}</text>
</svg>
"""
