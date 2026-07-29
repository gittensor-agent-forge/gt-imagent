from __future__ import annotations

import base64
import binascii
import hmac
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .challenge import ChallengeAborted, RoomRun

# The validator's side of the sealed-room contract.
#
# `/run` is the room's privileged endpoint: it decrypts a miner's credential and
# injects it into their agent, so it must only ever be callable by us. The room
# authenticates every request by HMAC over the exact bytes, refuses anything
# outside a short lifetime, and burns the nonce before executing. All three
# matter here, because together they are what stops a miner replaying a
# challenge until they like the images.

SIGNATURE_HEADER = "X-Kata-Signature"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_REQUEST_LIFETIME_SECONDS = 600


@dataclass(frozen=True)
class AgentSubmission:
    """What one competitor brings to a challenge."""

    agent_id: str
    bundle_b64: str
    bundle_sha256: str
    # Ciphertext. The validator never holds the miner's key in the clear, and
    # this value is public - it appears in the pull request.
    sealed_key: str


class SealedRoomClient:
    """Calls a deployed sealed room and returns a verified-shape RoomRun."""

    def __init__(
        self,
        base_url: str,
        auth_secret: str,
        submissions: dict[str, AgentSubmission],
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        lifetime_seconds: int = DEFAULT_REQUEST_LIFETIME_SECONDS,
        opener=urllib.request.urlopen,
    ) -> None:
        if not auth_secret:
            raise ValueError("a room auth secret is required; /run refuses unsigned requests")
        self.base_url = base_url.rstrip("/")
        self._secret = auth_secret.encode()
        self.submissions = submissions
        self.timeout_seconds = timeout_seconds
        self.lifetime_seconds = lifetime_seconds
        self._opener = opener

    def run(self, *, challenge_id: str, agent_id: str, nonce: str) -> RoomRun:
        submission = self.submissions.get(agent_id)
        if submission is None:
            raise ChallengeAborted(f"no submission registered for agent {agent_id!r}")

        issued_at = int(time.time())
        body = {
            # The room binds project_key into the attestation quote, so this is
            # what proves which challenge the images answer.
            "project_key": challenge_id,
            "nonce": _agent_nonce(nonce, agent_id),
            "issued_at": issued_at,
            "expires_at": issued_at + self.lifetime_seconds,
            "bundle": submission.bundle_b64,
            "bundle_sha256": submission.bundle_sha256,
            "sealed_key": submission.sealed_key,
        }
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

        request = urllib.request.Request(
            f"{self.base_url}/run",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                # Signed over the exact bytes we send, because that is the same
                # thing the room verifies before parsing them.
                SIGNATURE_HEADER: hmac.new(self._secret, payload, sha256).hexdigest(),
            },
        )

        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                answer = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:400]
            raise ChallengeAborted(f"room returned HTTP {error.code} for {agent_id}: {detail}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ChallengeAborted(f"room unreachable for {agent_id}: {error}") from error
        except json.JSONDecodeError as error:
            raise ChallengeAborted(f"room returned malformed JSON for {agent_id}") from error

        return _to_room_run(agent_id, answer)


def _agent_nonce(nonce: str, agent_id: str) -> str:
    """A distinct nonce per agent, derived from the challenge's.

    The room burns a nonce before executing, so reusing one across the king, the
    challenger, and the baseline would make the second call fail as a replay.
    """
    return sha256(f"{nonce}:{agent_id}".encode("utf-8")).hexdigest()[:32]


# dstack reports the measured identity of the running image as an event in the
# attestation event log, not as a top-level field. `compose-hash` covers every
# layer of the room image, which is exactly what an allowlist needs to pin.
MEASUREMENT_EVENTS = ("compose-hash", "compose_hash")


def measurement_from_event_log(event_log: Any) -> str:
    """Pull the room image's measured identity out of the attestation event log.

    Returns "" when it cannot be found, which `verify_run` treats as an abort.
    Guessing here would defeat the allowlist: an unidentifiable room is exactly
    the one you must not trust.
    """
    events = event_log
    if isinstance(events, str):
        try:
            events = json.loads(events)
        except json.JSONDecodeError:
            return ""
    if not isinstance(events, list):
        return ""

    for entry in events:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("event", "")).strip().casefold() in MEASUREMENT_EVENTS:
            value = entry.get("digest") or entry.get("event_payload") or ""
            return str(value).strip()
    return ""


def _to_room_run(agent_id: str, answer: Any) -> RoomRun:
    if not isinstance(answer, dict):
        raise ChallengeAborted(f"room answer for {agent_id} was not an object")

    report = answer.get("report")
    if not isinstance(report, dict):
        raise ChallengeAborted(f"room answer for {agent_id} carries no report")

    quote = str(answer.get("quote", ""))
    if not quote:
        raise ChallengeAborted(f"room answer for {agent_id} carries no attestation quote")

    provenance = answer.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}

    raw_images = report.get("images")
    raw_images = raw_images if isinstance(raw_images, dict) else {}
    images: dict[str, bytes] = {}
    for problem_id, encoded in raw_images.items():
        try:
            images[str(problem_id)] = base64.b64decode(str(encoded), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ChallengeAborted(
                f"room returned an undecodable image for {agent_id}/{problem_id}"
            ) from error

    return RoomRun(
        agent_id=agent_id,
        # `images` is stripped from the report the validator carries forward:
        # megabytes of base64 have no business in a published record, and the
        # hashes that bind them are already in report["problems"].
        report={key: value for key, value in report.items() if key != "images"},
        images=images,
        provenance=provenance,
        quote=quote,
        # Derived, not reported: the room has no reason to tell us which image it
        # is, and we would have no reason to believe it if it did.
        measurement=measurement_from_event_log(answer.get("event_log")),
    )
