from __future__ import annotations

import ast
import html
import json
import re
import time
from pathlib import Path
from typing import Any


class BaseImageAgent:
    """Small reference agent that contributors can replace in PRs."""

    def setup(self, config: dict[str, Any], workdir: Path) -> None:
        self.config = config
        self.workdir = Path(workdir).expanduser().resolve()

    def generate(self, case: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        started = time.perf_counter()
        output_dir = Path(output_dir)
        images_dir = output_dir / "images"
        traces_dir = output_dir / "traces"
        images_dir.mkdir(parents=True, exist_ok=True)
        traces_dir.mkdir(parents=True, exist_ok=True)

        run_id = _safe_run_id(case.get("run_id") or case.get("id") or "case")
        spec = self._build_spec(case)
        image_path = images_dir / f"{run_id}.svg"
        trace_path = traces_dir / f"{run_id}.json"

        image_path.write_text(self._render_svg(spec), encoding="utf-8")
        trace = {
            "agent": "base",
            "prompt": case.get("prompt", ""),
            "spec": spec,
        }
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        return {
            "image_path": str(image_path),
            "trace_path": str(trace_path),
            "metadata": {
                "agent_id": "base-image-agent",
                "provider": "mock-svg",
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "cost_usd": 0.0,
            },
        }

    def _build_spec(self, case: dict[str, Any]) -> dict[str, Any]:
        prompt = str(case.get("prompt", ""))
        memory = case.get("memory") if isinstance(case.get("memory"), dict) else {}
        assets = self._read_assets(case.get("assets", []))
        facts = self._read_search_facts(case.get("search_snapshots", []), prompt)
        title = (
            str(memory.get("preferred_label") or "").strip()
            or self._title_from_prompt(prompt)
            or assets.get("title")
            or ("Image-Agent" if facts else "")
            or "Image Agent"
        )
        sections = self._sections_from_prompt(prompt) or assets.get("sections", [])
        required_text = [title, *sections, *assets.get("required_text", [])]
        if "reason" in case.get("allowed_tools", []):
            display = self._reasoning_display(prompt)
            if display:
                required_text.extend([display["answer"], display["display"]])
        if "PASS" in prompt.upper():
            required_text.append("PASS")
        if facts:
            required_text.extend(["Image-Agent", "context gap"])

        return {
            "title": title,
            "sections": _dedupe(sections),
            "lines": _dedupe([*required_text, *facts[:2]]),
            "style": str(memory.get("preferred_style") or "simple reference rendering"),
        }

    def _read_assets(self, values: Any) -> dict[str, Any]:
        for value in values or []:
            path = self._case_path(value)
            if path.suffix.lower() != ".json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            return {
                "title": str(data.get("title") or ""),
                "sections": [str(item) for item in data.get("sections", []) if str(item).strip()],
                "required_text": [str(item) for item in data.get("required_text", []) if str(item).strip()],
            }
        return {"title": "", "sections": [], "required_text": []}

    def _read_search_facts(self, values: Any, prompt: str) -> list[str]:
        prompt_words = set(re.findall(r"[a-z0-9]+", prompt.lower()))
        facts: list[str] = []
        for value in values or []:
            path = self._case_path(value)
            if path.suffix.lower() != ".json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for fact in data.get("facts", []) if isinstance(data, dict) else []:
                text = str(fact)
                fact_words = set(re.findall(r"[a-z0-9]+", text.lower()))
                if prompt_words & fact_words:
                    facts.append(text)
        return _dedupe(facts)

    def _case_path(self, value: Any) -> Path:
        path = Path(str(value)).expanduser()
        candidate = path if path.is_absolute() else self.workdir / path
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(self.workdir)
        return resolved

    def _title_from_prompt(self, prompt: str) -> str:
        quoted = re.search(r'\btitled\s+["\']([^"\']+)["\']', prompt, re.IGNORECASE)
        if quoted:
            return quoted.group(1).strip()
        match = re.search(r"\btitled\s+(.+?)(?:\s+with\b|\.|$)", prompt, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _sections_from_prompt(self, prompt: str) -> list[str]:
        match = re.search(r"\bsections?\s+(.+?)(?:\.|$)", prompt, re.IGNORECASE)
        if not match:
            return []
        raw = re.sub(r"\band\b", ",", match.group(1), flags=re.IGNORECASE)
        return [part.strip(" .") for part in re.split(r"[,;/|]+", raw) if part.strip(" .")]

    def _reasoning_display(self, prompt: str) -> dict[str, str] | None:
        expression = _extract_expression(prompt)
        if not expression:
            return None
        try:
            value = _safe_eval(expression)
        except (ValueError, ZeroDivisionError):
            return None
        answer = _format_number(value)
        return {"answer": answer, "display": f"{expression} = {answer}"}

    def _render_svg(self, spec: dict[str, Any]) -> str:
        title = html.escape(spec["title"])
        lines = [html.escape(line) for line in spec["lines"] if line]
        line_markup = "\n".join(
            f'<text x="72" y="{170 + index * 38}" font-family="Arial, sans-serif" font-size="24" fill="#111827">{line}</text>'
            for index, line in enumerate(lines[:8])
        )
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" role="img" aria-label="{title}">
  <rect width="960" height="540" fill="#f8fafc"/>
  <rect x="36" y="36" width="888" height="468" rx="8" fill="#ffffff" stroke="#111827" stroke-width="3"/>
  <text x="72" y="110" font-family="Arial, sans-serif" font-size="44" font-weight="700" fill="#111827">{title}</text>
  {line_markup}
</svg>
"""


def _safe_run_id(value: Any) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", text):
        raise ValueError("run_id must be filename safe")
    return text


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _extract_expression(prompt: str) -> str:
    number = r"(?:\d+(?:\.\d*)?|\.\d+)"
    for match in re.finditer(rf"(?<![A-Za-z0-9_.])(?:{number}|\()[0-9()\s+\-*/.]*", prompt):
        candidate = match.group(0).strip().rstrip(".")
        if any(char.isdigit() for char in candidate) and any(op in candidate for op in "+-*/"):
            ast.parse(candidate, mode="eval")
            return candidate
    return ""


def _safe_eval(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
        if isinstance(node, ast.BinOp):
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
        raise ValueError(f"unsupported expression: {type(node).__name__}")

    return visit(tree)


def _format_number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.6f}".rstrip("0").rstrip(".")


ImageAgent = BaseImageAgent
