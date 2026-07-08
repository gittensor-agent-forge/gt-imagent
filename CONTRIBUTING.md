# Contributing

Thanks for contributing to `imagent`. This repository owns the built-in image
agent implementation, the Generation page UI, and the workflow that keeps both
contribution tracks reviewable.

## Gittensor Relationship

Imagent is being built through Gittensor. Gittensor helps power the open
competition model used by this repository: contributors submit image-agent
improvements, benchmark rounds score those submissions, and the highest-quality
work can become the next public winner.

You do not need Discord access or subnet-specific background to participate.
The GitHub workflow is the source of truth:

- Agent benchmark work enters through PRs against `agent/agent.py`.
- Generation page UI work enters through focused PRs under `imagent-ui/`.
- Automated rounds evaluate eligible PRs against the benchmark.
- Winning code is copied into `agent/last_winner.py` and archived in `winners/`.
- Non-winning eligible PRs can stay open for the next round after rebasing.

This makes the Gittensor contribution path visible in GitHub itself and gives
contributors a clear way to help improve the software Gittensor is supporting.

## What to work on

Start from an open [issue](https://github.com/imagent-ai/imagent/issues). Issues
labeled `good first issue` are the easiest entry points, and `crown` marks the
highest-value work. Comment on an issue to claim it before you start.

Prefer substantive agent or Generation page UI improvements over comments,
formatting, or documentation-only changes.

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

## Improving the Generation page

The completed Home page is the visual standard for Generation page
contributions. Generation UI PRs should improve the page while preserving the
project style, dark product feel, card effects, spacing discipline, and clear
interaction model.

Generation UI contributor PRs may only touch approved Generation page UI files,
currently:

- `imagent-ui/app/generation/page.tsx`
- `imagent-ui/app/components/GenerationChat.tsx`
- `imagent-ui/app/components/EffectCard.tsx`
- `imagent-ui/app/components/BorderGlow.tsx`
- `imagent-ui/app/components/BorderGlow.css`
- `imagent-ui/app/components/GlareHover.tsx`
- `imagent-ui/app/components/GlareHover.css`
- `imagent-ui/app/components/ScrollReveal.tsx`
- `imagent-ui/app/styles.css`

Do not edit API routes, runtime code, model configuration, benchmark files,
agent files, dependency metadata, deployment config, unrelated pages, or
workflows in a Generation UI contributor PR.

Every Generation UI PR must include at least one screenshot or video link in
the PR description. If evidence is missing, the bot keeps the PR open, adds
`needs-evidence`, and comments with instructions. UI PRs are never benchmarked
or auto-merged; maintainers review and merge them manually.

## Pull request rules

- **One concern per pull request**, as a single atomic commit.
- Use a conventional commit prefix: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `perf:`, `chore:`, `ci:`, `build:`, `style:`.
- Select exactly one contribution type in the PR template: `Agent Benchmark` or
  `Generation UI`.
- Fill in every required pull request template section. Use `N/A` for
  `Benchmark Impact` in Generation UI PRs.
- Contributor benchmark PRs must change only `agent/agent.py`.
- Contributor Generation UI PRs must touch only the approved Generation page UI
  files listed above.
- Do not edit `agent/last_winner.py`, `winners/`, tests, dependency metadata,
  workflows, `agent/agent.yaml`, unrelated UI pages, API routes, or any other
  file outside the active contribution track.
- Open only one Agent Benchmark PR and one Generation UI PR at a time. Extra
  open PRs from the same contributor in the same track are closed
  automatically during PR validation or round evaluation.
- Agent round submissions must be opened from branches in this repository. Fork
  PRs are not evaluated because the bot must use benchmark secrets and push
  promotion commits. Generation UI PRs may come from forks because they are
  manually reviewed and are not benchmarked.
- Owner and maintainer PRs are excluded from the round workflow and are merged
  manually through PRs.
- PRs that fail these basic rules are automatically labeled `invalid-pr` and closed
  before benchmark spend or manual UI review time is spent.

## Benchmark and merge policy

Valid Agent Benchmark PRs receive the `pr-rules-pass` label. Twice per day, the
round benchmark evaluates all valid same-repository agent PRs. The benchmark
uses OpenRouter image generation and OpenRouter vision judging, then compares
each candidate score against the current top baseline score configured in the
repository.

Valid Generation UI PRs receive `generation-ui` and `generation-ui-pass`
instead. They do not receive `pr-rules-pass`, so the scheduled benchmark
workflow will not evaluate or auto-merge them.

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
