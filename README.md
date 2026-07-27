# Imagent

Imagent is an open research project for image-generation agents. Its core idea is
simple: image generation should be more than a one-shot prompt call. A strong
agent should understand intent, plan, use context, generate, critique, and
improve while the image model remains one component in a larger system.

## Current Status

**The workflow is being rebuilt around a king-of-the-hill competition.** The
previous contribution tracks — Agent Benchmark rounds, Generation UI, and
Leaderboard UI — have been removed along with their automation, labels, and
templates.

There is no open contribution track right now. The reference agent, the benchmark
engine, and the public site remain in place as the foundation the new competition
will be built on.

## Why This Exists

Modern image models are powerful, but prompt-to-image generation still struggles
with complex instructions, context-heavy requests, consistency, exact text, and
self-correction. Imagent treats those weaknesses as an agent-design problem.

The long-term research question remains:

Can better planning, orchestration, context use, and verification make the same
image model produce better results?

Generation is fixed to one model so results measure the agent, not the model.

## Repository Layout

```
gt-imagent/
├── agent/    the image agent under competition   → agent/README.md
├── bench/    the engine that runs and scores it  → bench/README.md
├── web/      public site and leaderboard         → web/README.md
├── docs/     architecture and contracts          → docs/architecture.md
└── .github/  CI
```

Each component is self-contained: its own README, its own tests, and its own
packaging where it is a distributable. The dependency direction is strictly
one-way — `bench` loads `agent`, and `web` only ever reads report JSON.

The split is by **who owns the result**: an agent returns image bytes and a
trace, and the engine decides where artifacts land, how long the call took, and
whether it passed.

Two things are worth knowing before you move anything:

- **`agent/agent.yaml` is a protocol path**, hardcoded in the benchmark's agent
  loader. Every candidate depends on it.
- **The repository root is not a Python package.** The root `pyproject.toml`
  carries tool configuration only. `bench/` is the only installable and carries
  its own Apache-2.0 licence; the rest of the repository is MIT.

See [`docs/architecture.md`](./docs/architecture.md) for the full picture and
[`docs/submission-contract.md`](./docs/submission-contract.md) for what the
benchmark requires of an agent.

## Built Through Gittensor

Imagent is being built through Gittensor, which supports the open contributor
market this project is building toward: code, benchmark history, and design work
remain public, reviewable, and reusable.

## Local Development

```bash
# agent (stdlib only, loaded by path — nothing to install)
python -m pip install pytest
python -m pytest

# engine
python -m pip install -e "./bench[dev]"
cd bench && python -m pytest

# public site
cd web && npm ci && npm run lint && npm run build
```

CI runs all three on every pull request.

## Running the Agent

Live generation uses OpenRouter and the project-standard Gemini 3.1 Flash Image
model.

```bash
python -m pip install -e ./bench
export OPENROUTER_API_KEY=your-openrouter-api-key

# one ad-hoc prompt
imagent-bench try "Create a polished benchmark badge titled CLI PASS."

# a full scored run
imagent-bench run \
  --repository . \
  --config bench/configs/openrouter-vision-benchmark.json \
  --output-dir benchmark-output \
  --fail-on-policy
```

The agent fails clearly when OpenRouter is not configured; there is no mock
renderer.

See [`bench/README.md`](./bench/README.md) for the configuration matrix, the
report contract, and current known issues with the scoring gate.

## Design Principles

- Keep the base agent easy to understand.
- Make competition rules explicit, enforceable, and hard to game.
- Score the agent, not the image model — generation stays fixed.
- Preserve benchmark history and every prior incumbent.
- Never run untrusted candidate code with credentials in scope.
- Prefer transparent research artifacts over hidden leaderboard tricks.
- Build toward open, Gittensor-compatible image-agent research.
