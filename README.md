# Imagent

Imagent is an open research project for image-generation agents. Its core idea is
simple: image generation should be more than a one-shot prompt call. A strong
agent should understand intent, plan, use context, generate, critique, and
improve while the image model remains one component in a larger system.

**This is the competition repository.** It holds the agent that competes and the
rules it competes under.

## The three repositories

| Repository | Role |
|---|---|
| **gt-imagent** (here) | The king-of-the-hill competition and the reigning agent |
| [gt-imagent-bench](https://github.com/gittensor-agent-forge/gt-imagent-bench) | The engine: loads an agent, runs it over a suite, scores it, emits reports |
| [gt-imagent-ui](https://github.com/gittensor-agent-forge/gt-imagent-ui) | The dashboard: public leaderboard, benchmark reports, whitepaper |

The engine is consumed here as a **pinned git tag**, so a challenge is always
judged by a known version of the scorer. The pin lives in
`.github/workflows/ci.yml` as `IMAGENT_BENCH_REF`.

## Current Status

**The workflow is being rebuilt around a king-of-the-hill competition**, where a
challenger must beat the reigning agent head to head on the same problems. The
design is in [`docs/competition.md`](./docs/competition.md); it is a proposal and
is not implemented yet.

There is no open contribution track right now.

## Why This Exists

Modern image models are powerful, but prompt-to-image generation still struggles
with complex instructions, context-heavy requests, consistency, exact text, and
self-correction. Imagent treats those weaknesses as an agent-design problem.

The long-term research question remains:

Can better planning, orchestration, context use, and verification make the same
image model produce better results?

Generation is fixed to one model so results measure the agent, not the model.

## Layout

```
gt-imagent/
├── agent/    the agent under competition   → agent/README.md
├── docs/     architecture, contracts, competition design
└── .github/  CI
```

Two things are worth knowing before you move anything:

- **`agent/agent.yaml` is a protocol path**, hardcoded in the engine's loader.
  Every candidate depends on it.
- **The repository root is not a Python package.** The root `pyproject.toml`
  carries tool configuration only. The agent is stdlib-only and is loaded by
  path, never installed.

Start with [`docs/architecture.md`](./docs/architecture.md), then
[`docs/submission-contract.md`](./docs/submission-contract.md) for what the
engine requires of an agent, then [`docs/competition.md`](./docs/competition.md)
for where this is going.

## Built Through Gittensor

Imagent is being built through Gittensor, which supports the open contributor
market this project is building toward: code, benchmark history, and design work
remain public, reviewable, and reusable.

## Local Development

`pip` may not exist on your machine; `uv` works either way.

```bash
uv venv .venv --python 3.12
VIRTUAL_ENV=.venv uv pip install pytest

# agent tests
.venv/bin/python -m pytest
```

To run or score the agent you also need the engine:

```bash
VIRTUAL_ENV=.venv uv pip install \
  "git+https://github.com/gittensor-agent-forge/gt-imagent-bench@v0.1.0"

export OPENROUTER_API_KEY=your-openrouter-api-key

# one ad-hoc prompt → results/<UTC datetime>/
.venv/bin/imagent-bench try "Create a polished benchmark badge titled CLI PASS."

# a full scored run against this repository's agent
.venv/bin/imagent-bench run \
  --repository . \
  --config <path-to-bench-checkout>/configs/openrouter-vision-benchmark.json \
  --output-dir benchmark-output \
  --fail-on-policy
```

Only `try` and `run` need an API key and spend real credits. Tests do not.

## Design Principles

- Keep the base agent easy to understand.
- Make competition rules explicit, enforceable, and hard to game.
- Score the agent, not the image model — generation stays fixed.
- Preserve benchmark history and every prior incumbent.
- Never run untrusted candidate code with credentials in scope.
- Prefer transparent research artifacts over hidden leaderboard tricks.
- Build toward open, Gittensor-compatible image-agent research.
