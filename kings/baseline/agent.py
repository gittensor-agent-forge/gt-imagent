"""The control: a plain prompt to the fixed model, with no agent at all.

This is the scientific control for the whole project. Every challenge runs it
alongside the king and the challenger, on the same problems with the same seed,
so the leaderboard can answer the question the project exists to ask:

    does an agent actually beat prompting the model directly?

It deliberately does nothing clever. It does not plan, does not restate the
request, does not look at what came back, and never retries. One prompt, one
call. Changing that would make it a competitor rather than a baseline, and the
comparison would stop meaning anything.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

REQUEST_TIMEOUT_SECONDS = 120


class ImageAgent:
    def setup(self, config: dict[str, Any], workdir: str) -> None:
        self.config = config or {}

    def generate(self, case: dict[str, Any]) -> dict[str, Any]:
        endpoint = str(case.get("inference_api", "")).strip()
        if not endpoint:
            raise RuntimeError("case is missing inference_api")

        # The raw request, passed through untouched. That is the entire point.
        body = json.dumps({"model": "", "prompt": str(case.get("prompt", "")), "n": 1}).encode()
        request = urllib.request.Request(
            endpoint, data=body, method="POST", headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"inference HTTP {error.code}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"inference unreachable: {error.reason}") from error

        data = payload.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise RuntimeError("inference response carried no image data")

        item = data[0]
        encoded = item.get("b64_json")
        if not isinstance(encoded, str) or not encoded.strip():
            raise RuntimeError("inference response carried no inline image")

        return {
            "image_bytes": base64.b64decode(encoded, validate=True),
            "media_type": str(item.get("media_type") or "image/png"),
            "trace": {"agent": "direct-baseline", "strategy": "raw prompt, one call"},
        }
