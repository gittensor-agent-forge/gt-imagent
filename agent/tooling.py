from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GroundingBundle:
    grounding: dict[str, list[dict[str, Any]]]
    tool_calls: list[dict[str, Any]]


class AgentTool:
    name = "tool"

    def should_run(self, case: dict[str, Any]) -> bool:
        return False

    def run(self, agent: Any, case: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def arguments(self, case: dict[str, Any]) -> dict[str, Any]:
        return {}

    def build_call(self, case: dict[str, Any], outputs: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "arguments": self.arguments(case),
            "result_count": len(outputs),
        }


class AssetTool(AgentTool):
    name = "asset"

    def should_run(self, case: dict[str, Any]) -> bool:
        return bool(case.get("assets"))

    def run(self, agent: Any, case: dict[str, Any]) -> list[dict[str, Any]]:
        return agent._assets(case)

    def arguments(self, case: dict[str, Any]) -> dict[str, Any]:
        return {"asset_count": len(case.get("assets", []) or [])}


class ReasonTool(AgentTool):
    name = "reason"

    def should_run(self, case: dict[str, Any]) -> bool:
        return "reason" in case.get("allowed_tools", [])

    def run(self, agent: Any, case: dict[str, Any]) -> list[dict[str, Any]]:
        return agent._reason(case)

    def arguments(self, case: dict[str, Any]) -> dict[str, Any]:
        return {"prompt": str(case.get("prompt", ""))}


class SearchTool(AgentTool):
    name = "search"

    def should_run(self, case: dict[str, Any]) -> bool:
        return "search" in case.get("allowed_tools", [])

    def run(self, agent: Any, case: dict[str, Any]) -> list[dict[str, Any]]:
        return agent._search(case)

    def arguments(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "prompt": str(case.get("prompt", "")),
            "snapshot_count": len(case.get("search_snapshots", []) or []),
        }


class MemoryTool(AgentTool):
    name = "memory"

    def should_run(self, case: dict[str, Any]) -> bool:
        return "memory" in case.get("allowed_tools", [])

    def run(self, agent: Any, case: dict[str, Any]) -> list[dict[str, Any]]:
        return agent._memory(case)

    def arguments(self, case: dict[str, Any]) -> dict[str, Any]:
        memory = case.get("memory", {})
        keys = sorted(memory.keys()) if isinstance(memory, dict) else []
        return {"memory_keys": keys}


def build_grounding_tools() -> tuple[AgentTool, ...]:
    return (AssetTool(), ReasonTool(), SearchTool(), MemoryTool())
