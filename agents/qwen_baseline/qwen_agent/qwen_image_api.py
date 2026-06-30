from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class QwenImageError(RuntimeError):
    """Raised when the Qwen Image API call fails."""


class QwenImageClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.model = str(config.get("model", "qwen-image-2.0-pro"))
        self.api_key_env = str(config.get("api_key_env", "DASHSCOPE_API_KEY"))
        self.workspace_id_env = str(config.get("workspace_id_env", "DASHSCOPE_WORKSPACE_ID"))
        self.api_key = os.environ.get(self.api_key_env)
        self.workspace_id = os.environ.get(self.workspace_id_env)
        self.endpoint = self._endpoint()
        self.timeout_seconds = int(config.get("timeout_seconds", 300))
        self.download_timeout_seconds = int(config.get("download_timeout_seconds", 120))

    def generate(self, prompt: str, seed: int, output_path: Path) -> dict[str, Any]:
        if not self.api_key:
            raise QwenImageError(f"{self.api_key_env} is required for live Qwen Image generation")

        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt,
                            }
                        ],
                    }
                ]
            },
            "parameters": self._parameters(seed),
        }
        response = self._post_json(payload)
        image_url = self._extract_image_url(response)
        self._download_image(image_url, output_path)
        return {
            "provider": "dashscope",
            "model": self.model,
            "endpoint": self.endpoint,
            "request_id": response.get("request_id"),
            "usage": response.get("usage", {}),
            "image_url_saved": True,
        }

    def _endpoint(self) -> str:
        if self.config.get("endpoint"):
            return str(self.config["endpoint"])
        endpoint_env = str(self.config.get("endpoint_env", "DASHSCOPE_ENDPOINT"))
        endpoint = os.environ.get(endpoint_env)
        if endpoint:
            return endpoint
        if not self.workspace_id:
            raise QwenImageError(
                f"{self.workspace_id_env} or {endpoint_env} is required for live Qwen Image generation"
            )
        region = str(self.config.get("region", "ap-southeast-1"))
        return (
            f"https://{self.workspace_id}.{region}.maas.aliyuncs.com"
            "/api/v1/services/aigc/multimodal-generation/generation"
        )

    def _parameters(self, seed: int) -> dict[str, Any]:
        params = {
            "n": int(self.config.get("n", 1)),
            "negative_prompt": str(
                self.config.get(
                    "negative_prompt",
                    "Low resolution, blurry text, malformed letters, distorted layout, extra artifacts.",
                )
            ),
            "prompt_extend": bool(self.config.get("prompt_extend", True)),
            "watermark": bool(self.config.get("watermark", False)),
            "size": str(self.config.get("size", "2048*2048")),
            "seed": seed,
        }
        extra = self.config.get("parameters", {})
        if isinstance(extra, dict):
            params.update(extra)
        return params

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise QwenImageError(f"Qwen Image HTTP {exc.code}: {body}") from exc
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise QwenImageError("Qwen Image response must be a JSON object")
        if data.get("code"):
            raise QwenImageError(f"Qwen Image API error {data.get('code')}: {data.get('message')}")
        return data

    def _extract_image_url(self, response: dict[str, Any]) -> str:
        choices = response.get("output", {}).get("choices", [])
        for choice in choices:
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            for item in message.get("content", []):
                if isinstance(item, dict) and item.get("image"):
                    return str(item["image"])
        results = response.get("output", {}).get("results", [])
        for result in results:
            if isinstance(result, dict) and result.get("url"):
                return str(result["url"])
        raise QwenImageError("Qwen Image response did not include an image URL")

    def _download_image(self, image_url: str, output_path: Path) -> None:
        request = urllib.request.Request(image_url, method="GET")
        with urllib.request.urlopen(request, timeout=self.download_timeout_seconds) as response:
            data = response.read()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
