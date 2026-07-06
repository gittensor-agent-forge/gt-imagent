# Contributing

Thanks for contributing to `imagent`. This repository owns the built-in image
agent implementation.

## What to work on

Start from an open [issue](https://github.com/imagent-ai/imagent/issues). Issues
labeled `good first issue` are the easiest entry points, and `crown` marks the
highest-value work. Comment on an issue to claim it before you start.

Prefer substantive agent code over comments, formatting, or documentation-only
changes.

## Adding or improving an agent

The built-in agent lives under `agent/` with an `agent.yaml` manifest and Python source files:

```python
class MyAgent:
    def setup(self, config: dict, workdir: Path) -> None:
        ...

    def generate(self, case: dict, output_dir: Path) -> dict:
        # returns {"image_path": ..., "trace_path": ..., "metadata": {...}}
        ...
```

`generate` receives a public case payload and must write both an image and a
JSON trace. Contributor PRs must improve `agent/agent.py`; the bot copies the
round winner into `agent/last_winner.py` and `winners/` during promotion.
`agent/last_winner.py` and `winners/` are read-only references for contributors
and must not be edited directly.

Contributor benchmark PRs may not add dependencies. If the base agent needs new
dependencies or infrastructure changes, a maintainer should open a manual PR.

## Pull request rules

- **One concern per pull request**, as a single atomic commit.
- Use a conventional commit prefix: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `perf:`, `chore:`, `ci:`, `build:`, `style:`.
- Fill in every required pull request template section, including `Benchmark Impact`.
- Contributor benchmark PRs must change only `agent/agent.py`.
- Do not edit `agent/last_winner.py`, `winners/`, tests, dependency metadata,
  workflows, `agent/agent.yaml`, or any other file.
- Open only one PR at a time. Extra open PRs from the same contributor are
  closed automatically during PR validation or round evaluation.
- Round submissions must be opened from branches in this repository. Fork PRs
  are not evaluated because the bot must use benchmark secrets and push
  promotion commits.
- Owner and maintainer PRs are excluded from the round workflow and are merged
  manually through PRs.
- PRs that fail these basic rules are automatically labeled `invalid-pr` and closed
  before benchmark spend is allowed.

## Benchmark and merge policy

Valid PRs receive the `pr-rules-pass` label. Twice per day, the round benchmark
evaluates all valid same-repository PRs. The benchmark uses OpenRouter image
generation and OpenRouter vision judging, then compares each candidate score
against the current top baseline score configured in the repository.

Merge eligibility requires:

- PR rules pass.
- Code quality checks pass before benchmark spend.
- Benchmark policy passes.
- Candidate score improves the current top baseline by more than
  `IMAGENT_ROUND_THRESHOLD`.
- Candidate has the highest score among threshold-passing PRs in the round.

When those conditions are met, the round workflow copies the winning
`agent/agent.py` into `agent/last_winner.py`, archives the same code under
`winners/`, restores the repository to the base template plus those winner
files, and attempts a squash merge. If branch protection prevents the bot merge,
a maintainer must merge manually.

After promotion, the workflow updates `IMAGENT_BASELINE_SCORE`,
`IMAGENT_BASELINE_COMMIT`, `IMAGENT_LAST_ROUND_ID`, and
`IMAGENT_LAST_WINNER_PR`, so the next round compares against the new top agent.

Benchmark labels:

- `round-benchmark-running`: candidate is being evaluated.
- `below-threshold`: candidate did not improve by more than the round threshold.
- `round-eligible`: candidate passed the threshold but has not yet won the round.
- `round-winner`: candidate won the round and was selected for promotion.
- `needs-rebase`: candidate stayed open after another PR won and must be rebased
  onto `main` before it can enter a future round.

## Running locally

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Live generation requires `OPENROUTER_API_KEY`.

Benchmark configs, task suites, and gating logic are intentionally out of scope
for this repository. They live in `imagent-bench`.

The GitHub Actions benchmark workflow pins a specific `imagent-bench` commit.
When maintainers adopt benchmark changes from `imagent-bench`, they must update
that pin in `.github/workflows/benchmark.yml` so CI stays aligned with local
benchmark expectations.

From sibling checkouts:

```bash
python -m pip install -e ../imagent-bench
imagent-bench run \
  --repository . \
  --config ../imagent-bench/configs/official.json \
  --output-dir benchmark-output \
  --fail-on-policy
```

Pull requests first run the metadata/file rule gate. Valid same-repository PRs
then enter the next scheduled round.
