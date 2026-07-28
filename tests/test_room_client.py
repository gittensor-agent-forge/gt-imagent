from __future__ import annotations

import base64
import hmac
import json
import urllib.error
from hashlib import sha256

import pytest

from competition.challenge import ChallengeAborted
from competition.room_client import SIGNATURE_HEADER, AgentSubmission, SealedRoomClient

SECRET = "shared-room-secret"
SUBMISSION = AgentSubmission(
    agent_id="chal-1",
    bundle_b64="YnVuZGxl",
    bundle_sha256="a" * 64,
    sealed_key="04deadbeef",
)


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def _answer(**overrides) -> dict:
    payload = {
        "nonce": "n",
        "project_key": "c1",
        "quote": "0xquote",
        "measurement": "sha256:approved-room",
        "provenance": {"inference_policy": {"model_substitutions": 0}},
        "report": {
            "challenge_id": "c1",
            "problems": [{"problem_id": "p1", "image_sha256": sha256(b"png").hexdigest()}],
            "images": {"p1": base64.b64encode(b"png").decode()},
        },
    }
    payload.update(overrides)
    return payload


def _client(answer=None, *, capture: list | None = None, raiser=None) -> SealedRoomClient:
    def opener(request, timeout):
        if capture is not None:
            capture.append(request)
        if raiser is not None:
            raise raiser
        return _Response(answer if answer is not None else _answer())

    return SealedRoomClient(
        "https://room.example/", SECRET, {"chal-1": SUBMISSION}, opener=opener
    )


# --- the signed request -----------------------------------------------------


def test_the_request_is_signed_over_the_exact_bytes_sent() -> None:
    # The room verifies the signature before parsing, so re-serialising the body
    # would break authentication in a way that only shows up in production.
    captured: list = []
    _client(capture=captured).run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)

    request = captured[0]
    expected = hmac.new(SECRET.encode(), request.data, sha256).hexdigest()
    assert request.headers[SIGNATURE_HEADER.capitalize()] == expected


def test_the_request_carries_the_challenge_bundle_and_sealed_key() -> None:
    captured: list = []
    _client(capture=captured).run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)

    body = json.loads(captured[0].data)
    assert body["project_key"] == "c1"
    assert body["bundle"] == SUBMISSION.bundle_b64
    assert body["bundle_sha256"] == SUBMISSION.bundle_sha256
    assert body["sealed_key"] == SUBMISSION.sealed_key
    assert body["expires_at"] > body["issued_at"]


def test_each_agent_gets_its_own_nonce() -> None:
    # The room burns a nonce before executing, so reusing one across the king and
    # the challenger would make the second call fail as a replay.
    captured: list = []
    client = SealedRoomClient(
        "https://room.example",
        SECRET,
        {
            "king-1": AgentSubmission("king-1", "Yg==", "b" * 64, "04aa"),
            "chal-1": SUBMISSION,
        },
        opener=lambda request, timeout: (captured.append(request), _Response(_answer()))[1],
    )

    client.run(challenge_id="c1", agent_id="king-1", nonce="shared")
    client.run(challenge_id="c1", agent_id="chal-1", nonce="shared")

    nonces = [json.loads(request.data)["nonce"] for request in captured]
    assert nonces[0] != nonces[1]
    assert all(len(nonce) == 32 for nonce in nonces)


def test_an_unsigned_client_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="auth secret is required"):
        SealedRoomClient("https://room.example", "", {})


# --- the answer -------------------------------------------------------------


def test_a_good_answer_becomes_a_room_run() -> None:
    run = _client().run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)

    assert run.agent_id == "chal-1"
    assert run.images == {"p1": b"png"}
    assert run.quote == "0xquote"
    assert run.measurement == "sha256:approved-room"
    assert run.provenance["inference_policy"]["model_substitutions"] == 0


def test_base64_images_are_stripped_from_the_carried_report() -> None:
    # Megabytes of base64 have no place in a published record; the hashes that
    # bind those bytes are already in report["problems"].
    run = _client().run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)

    assert "images" not in run.report
    assert run.report["problems"][0]["image_sha256"] == sha256(b"png").hexdigest()


# --- infrastructure failures abort, they do not blame the miner -------------


def test_an_unreachable_room_aborts() -> None:
    client = _client(raiser=urllib.error.URLError("connection refused"))

    with pytest.raises(ChallengeAborted, match="room unreachable"):
        client.run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)


def test_an_http_error_aborts_and_keeps_the_detail() -> None:
    error = urllib.error.HTTPError(
        "https://room.example/run", 409, "Conflict", {}, None
    )
    error.read = lambda: b'{"error": "nonce already used"}'  # type: ignore[method-assign]

    with pytest.raises(ChallengeAborted, match="nonce already used"):
        _client(raiser=error).run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)


def test_an_answer_without_a_quote_aborts() -> None:
    with pytest.raises(ChallengeAborted, match="no attestation quote"):
        _client(_answer(quote="")).run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)


def test_an_answer_without_a_report_aborts() -> None:
    with pytest.raises(ChallengeAborted, match="carries no report"):
        _client(_answer(report=None)).run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)


def test_an_undecodable_image_aborts() -> None:
    broken = _answer()
    broken["report"]["images"]["p1"] = "!!!not base64!!!"

    with pytest.raises(ChallengeAborted, match="undecodable image"):
        _client(broken).run(challenge_id="c1", agent_id="chal-1", nonce="n" * 32)


def test_an_unregistered_agent_aborts_before_any_call() -> None:
    with pytest.raises(ChallengeAborted, match="no submission registered"):
        _client().run(challenge_id="c1", agent_id="ghost", nonce="n" * 32)
