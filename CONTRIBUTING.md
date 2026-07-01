# Contributing

Thanks for contributing to `imagent`. This repository is an open benchmark for
image agents: contributions are **agent improvements**, and every pull request is
scored by the benchmark. This repo participates in Gittensor (Bittensor Subnet 74),
so merged pull requests are recognized contributions.

## How contributions are evaluated

Every pull request runs the benchmark in CI (`.github/workflows/benchmark-pr.yml`).
The workflow installs the benchmark and tasks from the **base branch** (never from
the PR), runs the current baseline agent, then runs your candidate agent, and
compares the two with the acceptance rules in `configs/pr-gate.yaml`.

- A candidate agent **must not regress** the baseline, and an agent change is
  expected to **improve** the primary metric (`ia_score`).
- Pull requests that pass the gate are eligible to **merge**; changes that regress
  the benchmark are **closed**.

Because the benchmark, tasks, and thresholds always come from the base branch, you
cannot weaken the gate in the same pull request that changes the agent.

## What to work on

Start from an open [issue](https://github.com/imagent-ai/imagent/issues). Issues
labeled `good first issue` are the easiest entry points, and `crown` marks the
highest-value work. Comment on an issue to claim it before you start.

Prefer substantive agent code — new functions, classes, and capabilities — over
comments, formatting, or documentation-only changes.

## Adding or improving an agent

Agents live under `agents/<agent_id>/` with an `agent.yaml` manifest and a Python
class implementing two methods:

```python
class MyAgent:
    def setup(self, config: dict, workdir: Path) -> None:
        ...

    def generate(self, case: dict, output_dir: Path) -> dict:
        # returns {"image_path": ..., "trace_path": ..., "metadata": {...}}
        ...
```

`generate` receives only public case fields (expected answers and evaluator notes
are stripped by the runner) and must write both an image and a JSON **trace** with
`planning`, `grounding`, `final_generation_context`, and `feedback` sections. The
benchmark scores how the agent bridges the context gap, not just whether it emits an
image. See `agents/openrouter_baseline` for a full example.

If your agent needs extra packages, add `agents/<agent_id>/requirements.txt`.

## Pull request rules

- **One concern per pull request**, as a single atomic commit.
- Use a conventional commit prefix: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `perf:`, `chore:`, `ci:`, `build:`, `style:`.
- Keep the diff minimal — unrelated changes risk rejection.
- Fill in the pull request template and make sure CI is green.

## Running locally

```bash
python -m pip install -e ".[dev]"
python -m imagent_bench.config validate configs/local-smoke.yaml
python -m imagent_bench.runner \
  --config configs/openrouter-smoke.yaml \
  --agent agents/openrouter_baseline \
  --output results/openrouter-smoke
python -m pytest
```

The offline smoke suite is deterministic and needs no credentials.
