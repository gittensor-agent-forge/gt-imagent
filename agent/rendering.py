from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

try:
    from .common import dedupe_strings
except ImportError:  # pragma: no cover - manifest loader imports modules outside a package
    from common import dedupe_strings


class RenderingMixin:
    def _render_body_lines(self, spec: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        reasoning = spec.get("reasoning_result", {})
        if reasoning.get("display"):
            lines.append(str(reasoning["display"]))
        sections = set(value.lower() for value in spec.get("visual_constraints", {}).get("sections", []))
        for value in spec["visible_text"]:
            if value.lower() not in sections:
                lines.append(value)
        for fact in spec["grounded_facts"][:3]:
            if fact.lower() not in {line.lower() for line in lines}:
                lines.append(fact)
        return dedupe_strings(lines)

    def _write_svg(self, path: Path, spec: dict[str, Any], variant: dict[str, Any]) -> None:
        title = html.escape(str(spec["title"]))
        accent = str(variant["accent"])
        panel_fill = str(variant["panel_fill"])
        layout = str(spec["layout"])
        body_lines = [html.escape(line) for line in self._render_body_lines(spec)]
        sections = [html.escape(section) for section in spec.get("visual_constraints", {}).get("sections", [])[:3]]

        if layout == "three_panel":
            section_svg = []
            x_positions = [72, 336, 600]
            for index, section in enumerate(sections or ["Plan", "Ground", "Verify"]):
                section_svg.append(
                    f'<rect x="{x_positions[index]}" y="168" width="216" height="88" rx="8" fill="{panel_fill}" stroke="{accent}" stroke-width="2"/>'
                )
                section_svg.append(
                    f'<text x="{x_positions[index] + 108}" y="220" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">{section}</text>'
                )
            section_markup = "\n  ".join(section_svg)
            body_y = 312
        else:
            section_markup = ""
            body_y = 180

        line_markup = []
        max_lines = 6 if layout == "badge" else 7
        for index, line in enumerate(body_lines[:max_lines]):
            line_markup.append(
                f'<text x="72" y="{body_y + (index * 34)}" font-family="Arial, sans-serif" font-size="22" fill="#111827">{line}</text>'
            )

        title_size = 40 if layout == "badge" else 44
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" role="img" aria-label="{title}">
  <rect width="960" height="540" fill="#f8fafc"/>
  <rect x="36" y="36" width="888" height="468" rx="8" fill="#ffffff" stroke="#111827" stroke-width="3"/>
  <text x="72" y="108" font-family="Arial, sans-serif" font-size="{title_size}" font-weight="700" fill="#111827">{title}</text>
  <text x="72" y="146" font-family="Arial, sans-serif" font-size="20" fill="{accent}">{html.escape(variant['focus'])}</text>
  {section_markup}
  {' '.join(line_markup)}
</svg>
"""
        path.write_text(svg, encoding="utf-8")

    def _write_json(self, path: Path, data: Any) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
