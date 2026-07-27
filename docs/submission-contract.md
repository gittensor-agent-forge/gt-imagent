# Submission Contract

What the benchmark requires of a candidate agent.

## Layout

A candidate repository must contain:

```
agent/
├── agent.yaml     required  (agent.json is also accepted)
└── agent.py       or whatever the manifest entrypoint names
```

## Manifest

```yaml
id: image-agent
name: Image Agent
entrypoint: agent.agent:ImageAgent
version: 0.1.0
```

`entrypoint` is the only field the loader requires. It must be
`module:attribute`, resolved with the repository root on `sys.path`.

> The manifest parser reads top-level scalar keys only. Nested blocks are parsed
> as empty and are informational.

## Interface

```python
class ImageAgent:
    def setup(self, config: dict[str, Any], workdir: Path) -> None:
        ...

    def generate(self, case: dict[str, Any]) -> dict[str, Any]:
        ...
```

`setup` is called once. `generate` is called once per case and returns:

```python
{
    "image_bytes": b"...",          # required, non-empty, max 32 MiB
    "media_type": "image/png",      # optional, defaults to image/png
    "trace": {...},                 # optional, must be JSON-serializable
    "metadata": {"cost_usd": 0.0},  # optional
}
```

**The agent does not write files.** It returns bytes; the engine allocates the
output directory, names the artifact, writes it, and hashes it. An agent that
tries to place its own artifacts has no way to affect where they land.

Likewise the agent does not report its own latency or its own pass/fail. The
engine times the call and applies the policy.

`metadata.cost_usd` is trusted for cost accounting only, and is added to the
judge's own cost.

## Case payload

```json
{
  "id": "product-poster-001",
  "run_id": "product-poster-001",
  "prompt": "…",
  "capability": "plan",
  "seed": 1001,
  "allowed_tools": ["plan"],
  "expected": {"minimum_score": 80.0},
  "assets": ["assets/brief.json"],
  "search_snapshots": ["assets/snapshot.json"],
  "memory": {"preferred_label": "…"}
}
```

`assets` and `search_snapshots` are paths relative to the workdir passed to
`setup`. Resolving them outside that workdir is rejected.

## Scoring

An `image_judge` provider of `openrouter_vision` scores the image across weighted
dimensions. A provider of `none` is smoke mode: the agent runs end to end against
a live image model, and producing a usable image is the whole bar.

A judged case passes when its score reaches `expected.minimum_score`, or the
config's `policy.minimum_score` when the case declares no floor of its own.

## Rules

- Generation is fixed to one image model for every competitor.
- No mock renderers. A missing or invalid `OPENROUTER_API_KEY` fails the run.
- Candidate code is untrusted and must never execute with repository credentials
  in scope.
- No hardcoded answers. An agent that special-cases known prompts is gaming the
  suite, not solving it.

## Open items for the king-of-the-hill rebuild

Known gaps, recorded so the rebuild does not rediscover them:

1. **The suite is public and static.** `openrouter_vision_v1` ships committed
   cases, which is memorizable. Challenges need secret or freshly generated
   problems.
2. **The incumbent is never re-scored.** Ranking compares a fresh candidate score
   against a stored baseline number, so it measures judge drift as much as agent
   quality. The incumbent should run the same problems in the same challenge.
3. **No incumbent state.** There is no record of how many challenges the reigning
   agent has survived, so there is nothing to average over.
4. **No sandbox.** There is no isolation story for running challenger code. The
   bytes-in/bytes-out interface above is the precondition for adding one.
5. **No anti-cheat screening.** Nothing rejects a no-op agent, a constant output,
   or a replayed answer.
