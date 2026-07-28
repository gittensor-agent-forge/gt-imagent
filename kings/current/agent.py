"""The reigning Imagent agent.

This is the reference implementation and the seed king. Fork it, improve it,
beat it.

The whole thesis is here: the image model is fixed for everyone, so the only way
to win is to give it a better instruction. This agent reads the request, decides
what the image must contain, writes a deliberate generation prompt, and spends a
second call fixing the result if the first one came back unusable.

Two rules the sealed room enforces, so you do not have to implement them:

  * You never see an API key. Post to ``case["inference_api"]`` instead. The
    token in that URL carries this problem's generation budget.
  * You never choose the model. Whatever you ask for is rewritten to the pinned
    one, and asking for something else is recorded and disqualifies the run.

Stdlib only. Nothing else is installed in the agent container.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from typing import Any

# The room caps generations per problem. Staying under the cap is not optional;
# going over just returns 429 and wastes the wall clock.
MAX_ATTEMPTS = 2
REQUEST_TIMEOUT_SECONDS = 120

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


class ImageAgent:
    """Plan the instruction, generate, and retry once if nothing usable came back."""

    def setup(self, config: dict[str, Any], workdir: str) -> None:
        self.config = config or {}
        self.workdir = workdir

    def generate(self, case: dict[str, Any]) -> dict[str, Any]:
        endpoint = str(case.get("inference_api", "")).strip()
        if not endpoint:
            raise RuntimeError("case is missing inference_api; the room did not budget this problem")

        prompt = str(case.get("prompt", "")).strip()
        plan = self.plan(prompt)
        instruction = self.compose(prompt, plan)

        last_error = ""
        for attempt in range(MAX_ATTEMPTS):
            try:
                payload = self._request(endpoint, instruction)
                image, media_type = self._decode(payload)
                return {"image_bytes": image, "media_type": media_type, "trace": {"plan": plan}}
            except RuntimeError as error:
                last_error = str(error)
                # One retry, with the instruction sharpened rather than repeated.
                # Sending the identical prompt again mostly buys the same failure.
                instruction = f"{instruction}\nThe previous attempt failed. Render a clean, complete image."

        raise RuntimeError(f"no usable image after {MAX_ATTEMPTS} attempts: {last_error}")

    # --- the part worth improving -------------------------------------------

    def plan(self, prompt: str) -> dict[str, Any]:
        """Pull out what the image must contain, so the instruction can say it twice.

        Benchmark problems are compositional: counts, colours, positions, and
        exact text. Naming those explicitly in the instruction measurably beats
        passing the raw request through, which is the entire claim this project
        is testing.
        """
        return {
            "counts": self._counts(prompt),
            "quoted_text": re.findall(r'"([^"]+)"', prompt),
            "relations": [
                phrase
                for phrase in ("to the left of", "to the right of", "above", "below")
                if phrase in prompt.lower()
            ],
        }

    def compose(self, prompt: str, plan: dict[str, Any]) -> str:
        lines = [
            "Create one photorealistic image that follows this request exactly.",
            f"Request: {prompt}",
        ]
        if plan["counts"]:
            counted = ", ".join(f"exactly {number} {noun}" for noun, number in plan["counts"])
            lines.append(f"Counts that must be exact: {counted}.")
        if plan["quoted_text"]:
            quoted = ", ".join(f'"{text}"' for text in plan["quoted_text"])
            lines.append(
                f"Text that must be spelled correctly and legible: {quoted}. "
                "Render it once, large and unobstructed."
            )
        if plan["relations"]:
            lines.append(
                f"Spatial arrangement that must hold: {', '.join(plan['relations'])}. "
                "Place the objects so the relation is unmistakable."
            )
        lines.append(
            "Include every named object. Do not add objects that were not asked for. "
            "Avoid duplicated or misspelled text, clutter, and cropped subjects."
        )
        return "\n".join(lines)

    def _counts(self, prompt: str) -> list[tuple[str, int]]:
        found: list[tuple[str, int]] = []
        for word, number in _NUMBER_WORDS.items():
            for match in re.finditer(rf"\b{word}\s+([a-z]+)", prompt.lower()):
                found.append((match.group(1), number))
        for match in re.finditer(r"\b(\d+)\s+([a-z]+)", prompt.lower()):
            found.append((match.group(2), int(match.group(1))))
        return found

    # --- talking to the room ------------------------------------------------

    def _request(self, endpoint: str, instruction: str) -> dict[str, Any]:
        # `model` is sent for shape only: the room rewrites it to the pinned one
        # whatever it says, and asking for a different model is recorded.
        body = json.dumps(
            {"model": self.config.get("model", ""), "prompt": instruction, "n": 1}
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"inference HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"inference unreachable: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError("inference returned malformed JSON") from error

    def _decode(self, payload: dict[str, Any]) -> tuple[bytes, str]:
        data = payload.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise RuntimeError("inference response carried no image data")

        item = data[0]
        media_type = str(item.get("media_type") or "image/png")

        encoded = item.get("b64_json")
        if isinstance(encoded, str) and encoded.strip():
            try:
                return base64.b64decode(encoded, validate=True), media_type
            except (ValueError, TypeError) as error:
                raise RuntimeError("inference returned invalid base64") from error

        url = item.get("url")
        if isinstance(url, str) and url.startswith("data:"):
            header, _, encoded = url.partition(",")
            media_type = header.removeprefix("data:").split(";", 1)[0] or media_type
            try:
                return base64.b64decode(encoded, validate=True), media_type
            except (ValueError, TypeError) as error:
                raise RuntimeError("inference returned an invalid data URL") from error

        # A plain http(s) URL is unreachable from here on purpose: the agent
        # container has no route to the internet.
        raise RuntimeError("inference response carried no inline image")
