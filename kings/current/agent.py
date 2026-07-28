"""The reigning Imagent agent.

This is the reference implementation and the seed king. Fork it, improve it,
beat it.

The whole thesis is here: the image model is fixed for everyone, so the only way
to win is to give it a better instruction. This agent reads the request, decides
what the image must contain, writes a deliberate generation prompt, and spends a
second call fixing the result if the first one came back unusable.

Two rules the sealed room enforces, so you do not have to implement them:

  * You never see an API key. Post to ``case["inference_api"]`` to generate, and
    to ``case["reason_api"]`` to look at what you generated and think about it.
    Each carries its own per-problem budget.
  * You never choose either model. Whatever you ask for is rewritten to the
    pinned one, and asking for something else is recorded and disqualifies the run.
  * You never choose the seed. Both competitors get the same one, so a duel
    measures the agent rather than who drew the luckier sample.

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
        reason_endpoint = str(case.get("reason_api", "")).strip()

        prompt = str(case.get("prompt", "")).strip()
        plan = self.plan(prompt)
        instruction = self.compose(prompt, plan)

        best: tuple[bytes, str] | None = None
        trace: dict[str, Any] = {"plan": plan, "attempts": []}
        last_error = ""

        for attempt in range(MAX_ATTEMPTS):
            try:
                image, media_type = self._decode(self._request(endpoint, instruction))
            except RuntimeError as error:
                last_error = str(error)
                trace["attempts"].append({"error": last_error})
                instruction += "\nThe previous attempt failed. Render a clean, complete image."
                continue

            best = (image, media_type)
            # Look at what came back. Accepting the first image without checking
            # is what separates a prompt wrapper from an agent.
            verdict = self._critique(reason_endpoint, prompt, plan, image, media_type)
            trace["attempts"].append(verdict)
            if verdict.get("satisfied", True):
                break
            instruction = self.compose(prompt, plan, fix=str(verdict.get("fix", "")))

        if best is None:
            raise RuntimeError(f"no usable image after {MAX_ATTEMPTS} attempts: {last_error}")
        return {"image_bytes": best[0], "media_type": best[1], "trace": trace}

    def _critique(
        self, endpoint: str, prompt: str, plan: dict[str, Any], image: bytes, media_type: str
    ) -> dict[str, Any]:
        """Ask the reasoning model whether the image actually satisfies the request.

        A failure here is not fatal: it means this attempt goes unchecked, which
        is worse than checking but far better than losing the image.
        """
        if not endpoint:
            return {"satisfied": True, "reason": "no reasoning endpoint available"}

        wanted = []
        if plan["counts"]:
            wanted += [f"exactly {number} {noun}" for noun, number in plan["counts"]]
        if plan["quoted_text"]:
            wanted += [f'the text "{text}" spelled correctly' for text in plan["quoted_text"]]
        if plan["relations"]:
            wanted += [f"the arrangement {phrase}" for phrase in plan["relations"]]

        question = (
            "Does this image satisfy the request? Check each requirement.\n"
            f"Request: {prompt}\n"
            + ("Requirements: " + "; ".join(wanted) + "\n" if wanted else "")
            + 'Reply with JSON only: {"satisfied": true|false, "fix": "one short instruction"}'
        )
        payload = {
            "model": "",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,"
                                + base64.b64encode(image).decode("ascii")
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 200,
        }
        try:
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                answer = json.loads(response.read().decode("utf-8"))
            content = answer["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
            parsed = json.loads(content)
            return {
                "satisfied": bool(parsed.get("satisfied", True)),
                "fix": str(parsed.get("fix", ""))[:200],
            }
        except Exception as error:  # noqa: BLE001 - an unchecked attempt beats a lost one
            return {"satisfied": True, "reason": f"critique unavailable: {error}"[:200]}

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

    def compose(self, prompt: str, plan: dict[str, Any], fix: str = "") -> str:
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
        if fix:
            # What the critique said was wrong, stated as an instruction rather
            # than a complaint.
            lines.append(f"The previous attempt was wrong. Correct it: {fix}")
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
