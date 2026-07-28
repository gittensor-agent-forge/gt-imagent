from __future__ import annotations

import base64
import json
import sys
import urllib.error
from pathlib import Path

import pytest

# The crowned agent is loaded by path, exactly as the sealed room loads it.
KING_DIR = Path(__file__).resolve().parents[1] / "kings" / "current"
sys.path.insert(0, str(KING_DIR))

from agent import ImageAgent  # noqa: E402


ENDPOINT = "http://gateway/p/token/inference"


def _agent() -> ImageAgent:
    agent = ImageAgent()
    agent.setup({}, str(KING_DIR))
    return agent


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def _image_reply(data: bytes = b"png-bytes") -> dict:
    return {"data": [{"b64_json": base64.b64encode(data).decode(), "media_type": "image/png"}]}


def _patch(monkeypatch, *replies, capture=None, raiser=None):
    queue = list(replies)

    def opener(request, timeout):
        if capture is not None:
            capture.append(json.loads(request.data))
        if raiser is not None:
            value = raiser() if callable(raiser) else raiser
            if value is not None:
                raise value
        return _Response(queue.pop(0) if queue else _image_reply())

    monkeypatch.setattr("agent.urllib.request.urlopen", opener)


def test_the_agent_returns_image_bytes(monkeypatch) -> None:
    _patch(monkeypatch, _image_reply())

    result = _agent().generate(
        {"id": "p1", "prompt": "a photo of three cakes", "inference_api": ENDPOINT}
    )

    assert result["image_bytes"] == b"png-bytes"
    assert result["media_type"] == "image/png"


def test_the_agent_posts_to_the_room_not_to_a_provider(monkeypatch) -> None:
    # It holds no API key and has no route to the internet; the only address it
    # can reach is the one the room budgeted for this problem.
    captured: list = []
    _patch(monkeypatch, _image_reply(), capture=captured)

    _agent().generate({"id": "p1", "prompt": "a red cup", "inference_api": ENDPOINT})

    assert "prompt" in captured[0]
    assert "api_key" not in json.dumps(captured[0])


def test_a_missing_inference_api_fails_loudly(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="missing inference_api"):
        _agent().generate({"id": "p1", "prompt": "a red cup"})


def test_counts_from_the_prompt_are_restated_in_the_instruction(monkeypatch) -> None:
    captured: list = []
    _patch(monkeypatch, _image_reply(), capture=captured)

    _agent().generate(
        {"id": "p1", "prompt": "a photo of three cakes", "inference_api": ENDPOINT}
    )

    assert "exactly 3 cakes" in captured[0]["prompt"]


def test_quoted_text_is_called_out_as_must_be_spelled_correctly(monkeypatch) -> None:
    captured: list = []
    _patch(monkeypatch, _image_reply(), capture=captured)

    _agent().generate(
        {
            "id": "p1",
            "prompt": 'a sign with the word "MERIDIAN" on it',
            "inference_api": ENDPOINT,
        }
    )

    assert '"MERIDIAN"' in captured[0]["prompt"]
    assert "spelled correctly" in captured[0]["prompt"]


def test_a_spatial_relation_is_restated(monkeypatch) -> None:
    captured: list = []
    _patch(monkeypatch, _image_reply(), capture=captured)

    _agent().generate(
        {"id": "p1", "prompt": "a cup to the left of a banana", "inference_api": ENDPOINT}
    )

    assert "to the left of" in captured[0]["prompt"]
    assert "unmistakable" in captured[0]["prompt"]


def test_the_agent_retries_once_within_its_budget(monkeypatch) -> None:
    calls = {"n": 0}
    captured: list = []

    def raiser():
        calls["n"] += 1
        if calls["n"] == 1:
            error = urllib.error.HTTPError("u", 500, "boom", {}, None)
            error.read = lambda: b"upstream error"
            return error
        return None

    _patch(monkeypatch, _image_reply(), capture=captured, raiser=raiser)

    result = _agent().generate({"id": "p1", "prompt": "a red cup", "inference_api": ENDPOINT})

    assert result["image_bytes"] == b"png-bytes"
    # The retry sharpens the instruction rather than repeating it verbatim.
    assert captured[1]["prompt"] != captured[0]["prompt"]


def test_the_agent_gives_up_inside_the_room_s_generation_cap(monkeypatch) -> None:
    error = urllib.error.HTTPError("u", 429, "budget", {}, None)
    error.read = lambda: b"generation budget exhausted"
    captured: list = []
    _patch(monkeypatch, capture=captured, raiser=error)

    with pytest.raises(RuntimeError, match="no usable image"):
        _agent().generate({"id": "p1", "prompt": "a red cup", "inference_api": ENDPOINT})

    # Two attempts, well inside the room's cap of four.
    assert len(captured) == 2


def test_a_response_with_no_image_is_an_error(monkeypatch) -> None:
    _patch(monkeypatch, {"data": []}, {"data": []})

    with pytest.raises(RuntimeError, match="no usable image"):
        _agent().generate({"id": "p1", "prompt": "a red cup", "inference_api": ENDPOINT})


def test_a_data_url_response_is_decoded(monkeypatch) -> None:
    encoded = base64.b64encode(b"jpeg-bytes").decode()
    _patch(monkeypatch, {"data": [{"url": f"data:image/jpeg;base64,{encoded}"}]})

    result = _agent().generate({"id": "p1", "prompt": "a red cup", "inference_api": ENDPOINT})

    assert result["image_bytes"] == b"jpeg-bytes"
    assert result["media_type"] == "image/jpeg"


def test_the_manifest_points_at_the_implementation() -> None:
    manifest = (KING_DIR / "agent.yaml").read_text(encoding="utf-8")

    assert "entrypoint: agent:ImageAgent" in manifest
