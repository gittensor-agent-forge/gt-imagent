from __future__ import annotations

import hashlib

# The free checks, run on every submission pull request before a single
# credit is spent. Everything here is deliberately cheap: a challenge costs
# real money, so a broken, oversized, or replayed submission must never reach
# one.


def screen_submission(
    *,
    bundle_files: dict[str, bytes],
    sealed_key: str,
    archived_hashes: set[str],
    max_files: int = 16,
    max_bytes: int = 256 * 1024,
) -> list[str]:
    """The free checks, before a single credit is spent.

    Returns the reasons to reject; empty means the submission may be queued.
    Everything here is cheap on purpose: a challenge costs real money, so a
    broken or duplicated submission must never reach one.
    """
    reasons: list[str] = []

    if not sealed_key.strip():
        reasons.append("submission is missing its sealed inference key")
    if "agent.yaml" not in bundle_files:
        reasons.append("bundle is missing agent.yaml")
    if not any(name.endswith(".py") for name in bundle_files):
        reasons.append("bundle contains no Python entrypoint")
    if len(bundle_files) > max_files:
        reasons.append(f"bundle has {len(bundle_files)} files, the limit is {max_files}")

    total = sum(len(payload) for payload in bundle_files.values())
    if total > max_bytes:
        reasons.append(f"bundle is {total} bytes, the limit is {max_bytes}")

    digest = hashlib.sha256(
        b"".join(
            name.encode() + b"\x00" + bundle_files[name] for name in sorted(bundle_files)
        )
    ).hexdigest()
    if digest in archived_hashes:
        reasons.append("bundle is byte-identical to a previously submitted agent")

    return reasons
