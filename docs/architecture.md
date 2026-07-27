# Architecture

Three components. Each is self-contained: its own README, its own tests, its own
packaging where it is a distributable.

```
gt-imagent/
├── agent/    the image agent under competition    (loaded by path, not installed)
├── bench/    the engine that runs and scores it   (imagent-bench, Apache-2.0)
├── web/      the public site                      (Next.js, private)
└── docs/     architecture and contracts
```

## Dependency direction

```
bench ──loads──▶ agent
  │
  └──writes──▶ benchmark-report.json ──imported by──▶ web
```

Strictly one-way. `agent` imports nothing from `bench`; `web` imports neither
Python package and only ever reads report JSON. That is what makes it safe to let
an untrusted contributor change `agent/` and nothing else.

## The agent/engine split

The dividing line is **who owns the result**.

An agent takes a case and returns image bytes plus a trace. It does not choose
file paths, does not name artifacts, does not time itself, and does not decide
whether it passed. The engine does all of that:

| Responsibility | Owner |
|---|---|
| Interpret the prompt, build context, call the image model | agent |
| Return bytes + trace + provider metadata | agent |
| Allocate the output directory, name artifacts, write files | bench |
| Time the call, hash artifacts, enforce size limits | bench |
| Score the image, apply the policy, decide pass/fail | bench |

This is why there is no separate "runtime" component. An earlier layout split the
harness into its own distribution, but the harness reached into four private
members of the agent (`_build_context`, `_build_generation_prompt`,
`_request_openrouter_image`, `backend_config`) while the agent imported the
harness — a circular dependency through private API dressed up as a contract.
Persistence belongs to the engine, so it now lives in
`bench/src/imagent_bench/artifacts.py`.

The practical payoff: because the agent never writes to the engine's output
tree, it can later be moved behind a sandbox boundary without changing its
interface.

## Why the agent is loaded, not installed

`bench/src/imagent_bench/agent_loader.py` puts the candidate repository root on
`sys.path`, reads `agent/agent.yaml`, and imports the declared `module:attribute`
entrypoint. Two consequences worth stating plainly:

1. `agent/agent.yaml` is a protocol path, hardcoded in the loader. Renaming
   `agent/` breaks every candidate that exists.
2. The repository root has no `[project]` table. The root `pyproject.toml`
   carries tool configuration only.

## Components

| Component | Distribution | License | Third-party deps |
|---|---|---|---|
| `agent/` | none — loaded by path | MIT (repo) | none |
| `bench/` | `imagent-bench` | Apache-2.0 | none |
| `web/` | private npm package | MIT (repo) | Next.js, React, lucide |

Both Python surfaces are stdlib-only by design: a scored run should have no
third-party supply chain between a candidate agent and the number recorded.

The licence split is deliberate — `bench/` carries Apache-2.0 and its own
`LICENSE`; the rest of the repository is MIT.

## Fixed model

Image generation is pinned to one model for every competitor, reached through
OpenRouter. The competition measures planning, prompt construction, context use,
and self-correction — not who picked the better model.

## Artifact flow

1. `bench` runs a candidate over a suite and writes `benchmark-report.json` and
   `benchmark-summary.md`, shaped by `bench/schemas/benchmark-report.schema.json`.
2. `web/scripts/import-report.mjs` validates a report and copies it into
   `web/data/reports/`.
3. `/leaderboard` renders dynamically, so an imported report appears without a
   rebuild.

## Planned: king-of-the-hill

The competition workflow is being rebuilt so a challenger must beat the reigning
agent head to head on the same problems. Open gaps are recorded at the end of
[`submission-contract.md`](./submission-contract.md).
