# Architecture

Three repositories, one per concern.

| Repository | Contains | Distribution |
|---|---|---|
| `gt-imagent` (this one) | `agent/`, `docs/`, competition workflow | not packaged |
| `gt-imagent-bench` | the engine | `imagent-bench`, Apache-2.0 |
| `gt-imagent-ui` | the dashboard | private npm package |

```
gt-imagent/
├── agent/    the image agent under competition   (loaded by path, not installed)
└── docs/     architecture, contracts, competition design
```

## Dependency direction

```
gt-imagent-bench ──loads──▶ gt-imagent/agent
       │
       └──writes──▶ benchmark-report.json ──imported by──▶ gt-imagent-ui
```

Strictly one-way, and now enforced by repository boundaries rather than
convention. The engine is consumed here as a pinned git tag
(`IMAGENT_BENCH_REF` in CI), so scoring is reproducible: a challenge is always
judged by a known version.

The agent imports nothing from the engine; the dashboard imports neither Python
package and only ever reads report JSON. That is what makes it safe to let an
untrusted contributor change `agent/` and nothing else.

## The agent/engine split

The dividing line is **who owns the result**.

An agent takes a case and returns image bytes plus a trace. It does not choose
file paths, does not name artifacts, does not time itself, and does not decide
whether it passed. The engine does all of that:

| Responsibility | Owner |
|---|---|
| Interpret the prompt, build context, call the image model | agent |
| Return bytes + trace + provider metadata | agent |
| Allocate the output directory, name artifacts, write files | engine |
| Time the call, hash artifacts, enforce size limits | engine |
| Score the image, apply the policy, decide pass/fail | engine |

This is why there is no separate "runtime" component. An earlier layout split the
harness into its own distribution, but the harness reached into four private
members of the agent (`_build_context`, `_build_generation_prompt`,
`_request_openrouter_image`, `backend_config`) while the agent imported the
harness — a circular dependency through private API dressed up as a contract.
Persistence belongs to the engine, so it lives in the engine repository as
`src/imagent_bench/artifacts.py`.

The practical payoff: because the agent never writes to the engine's output
tree, it can later be moved behind a sandbox boundary without changing its
interface.

## Why the agent is loaded, not installed

The engine's `agent_loader.py` puts the candidate repository root on `sys.path`,
reads `agent/agent.yaml`, and imports the declared `module:attribute` entrypoint. Two consequences worth stating plainly:

1. `agent/agent.yaml` is a protocol path, hardcoded in the loader. Renaming
   `agent/` breaks every candidate that exists.
2. The repository root has no `[project]` table. The root `pyproject.toml`
   carries tool configuration only.

## Components

| Component | Distribution | License | Third-party deps |
|---|---|---|---|
| agent | none — loaded by path | MIT | none |
| engine | `imagent-bench` | Apache-2.0 | none |
| dashboard | private npm package | MIT | Next.js, React, lucide |

Both Python surfaces are stdlib-only by design: a scored run should have no
third-party supply chain between a candidate agent and the number recorded.

The licence split is deliberate — the engine repository carries Apache-2.0; the
other two are MIT.

## Fixed model

Image generation is pinned to one model for every competitor, reached through
OpenRouter. The competition measures planning, prompt construction, context use,
and self-correction — not who picked the better model.

## Artifact flow

1. The engine runs a candidate over a suite and writes `benchmark-report.json`
   and `benchmark-summary.md`, shaped by its `schemas/benchmark-report.schema.json`.
2. The dashboard's `scripts/import-report.mjs` validates a report and copies it
   into `data/reports/`.
3. `/leaderboard` renders dynamically, so an imported report appears without a
   rebuild.

## Planned: king-of-the-hill

The competition workflow is being rebuilt so a challenger must beat the reigning
agent head to head on the same problems. Open gaps are recorded at the end of
[`submission-contract.md`](./submission-contract.md).
