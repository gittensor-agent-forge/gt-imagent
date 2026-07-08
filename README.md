# Imagent

Imagent is an open competition and research repo for image-generation agents.
The core idea is simple: image generation should not be only a one-shot prompt
call. A strong image agent should understand intent, plan, use context, generate,
critique, and improve its output while keeping the underlying image model as one
component in a larger system.

This repository owns the candidate agent template and the automated round
workflow. Contributors compete by improving one file, `agent/agent.py`. Twice per
day, the benchmark evaluates valid candidate PRs, promotes the highest-scoring
threshold-passing agent, and archives the winner for everyone to study.

## Why This Exists

Modern image models are powerful, but prompt-to-image generation still fails
often on multi-step instructions, exact text, context-heavy tasks, consistency,
and self-correction. Imagent treats those weaknesses as an agent-design problem.

Instead of asking contributors to change the underlying model, Imagent asks a
more useful research question:

Can better planning, orchestration, context use, and verification make the same
image model produce better results?

The long-term goal is to become an open platform for building and comparing
image-generation agents: modular planners, prompt builders, tool users,
self-critics, regeneration policies, memory systems, benchmark suites, and
trajectory-level evaluators.

## Built Through Gittensor

Imagent is being built through Gittensor. Gittensor helps power the open
competition loop behind this project: contributors submit image-agent code,
automated benchmark rounds evaluate the work, and the best implementations are
merged, archived, and made visible for everyone to study.

You do not need to be in Discord or understand subnet internals to see how
Gittensor is involved. The relationship is explicit:

- Gittensor supports the open contributor market that Imagent is building
  toward.
- Imagent turns image-agent research into benchmarked GitHub PRs.
- Winning code is promoted into `agent/last_winner.py` and archived under
  `winners/`.
- Contributors can inspect prior winners, improve the base agent, and compete
  in future benchmark rounds.

The current GitHub round system is the first practical version of a
Gittensor-style open intelligence market: contributors submit agents, objective
evaluation assigns scores, and the best work becomes visible, reusable, and
rewardable.

In the future, Imagent can evolve toward deeper Gittensor integration where:

- Miners or contributors submit image-agent strategies.
- Validators evaluate agents against public and private benchmark suites.
- Scores reflect measurable improvement over the current best agent.
- Winning trajectories and code are archived for transparent research.
- Rewards can favor real capability gains instead of benchmark overfitting.

The immediate repository workflow is intentionally strict and simple so this can
become a reliable foundation for that larger ecosystem.

## Repository Layout

- `agent/agent.py`: the basic reference agent and the only file contributor
  benchmark PRs may change.
- `agent/last_winner.py`: bot-managed copy of the latest winning agent. It starts
  empty and is updated only by the round bot.
- `imagent_runtime/`: stable runtime and CLI infrastructure used to execute
  agents locally and in framework flows. Contributor benchmark PRs should not
  edit this package.
- `winners/`: bot-managed archive of previous winning agents, intended as a
  public reference library for contributors.
- `.github/workflows/pr-rules.yml`: validates contributor PRs and closes invalid
  submissions before benchmark spend.
- `.github/workflows/benchmark.yml`: runs two scheduled benchmark rounds per day.
- `.github/scripts/round_manager.py`: evaluates PRs, enforces thresholds,
  selects the round winner, promotes winner code, labels non-winners, and merges.

Benchmark suites, scoring, and evaluation logic live in
[`imagent-bench`](https://github.com/imagent-ai/imagent-bench). This repo stays
focused on the candidate agent and promotion workflow.

## Contributor Workflow

Contributor benchmark PRs are intentionally constrained:

- Change only `agent/agent.py`.
- Do not edit tests, workflows, dependency metadata, `agent/last_winner.py`, or
  `winners/`.
- Open only one PR at a time.
- Use the PR template and explain the expected benchmark impact.
- Rebase when the bot applies `needs-rebase`.

This constraint keeps the competition fair. Every candidate is evaluated as an
agent implementation, not as a test change, dependency change, workflow change,
or benchmark change.

Owner and maintainer PRs are excluded from the round workflow. They are used for
manual repository maintenance, documentation, infrastructure, benchmark pins, and
base-template changes.

## Round System

Rounds run twice per day in UTC:

- `00:00 UTC`
- `12:00 UTC`

Each round follows this lifecycle:

1. Collect open same-repository contributor PRs labeled `pr-rules-pass`.
2. Skip maintainer PRs, draft PRs, fork PRs, and PRs labeled `needs-rebase`.
3. Enforce one open candidate PR per contributor.
4. Evaluate each valid PR in an isolated temporary git worktree and virtualenv.
5. Close PRs that fail tests, compilation, benchmark quality policy, or the
   configured improvement threshold.
6. Mark threshold-passing PRs as `round-eligible`.
7. Select the highest-scoring eligible PR as the round winner.
8. Copy the winning `agent/agent.py` into `agent/last_winner.py`.
9. Archive the same code under `winners/<round>_pr_<number>_<sha>.py`.
10. Restore the base template so `agent/agent.py` remains a clean starting point.
11. Squash-merge the promoted winner PR.
12. Label non-winning eligible PRs as `needs-rebase` so contributors update them
    before the next round.

The round threshold is controlled by the repository variable
`IMAGENT_ROUND_THRESHOLD`. A candidate must improve by more than that threshold
to stay eligible.

## Bot-Managed Winner Files

`agent/last_winner.py` and `winners/` are not submission targets. They are public
reference material.

Use them to understand what has worked before:

- Read `agent/last_winner.py` to see the current best merged strategy.
- Browse `winners/` to study earlier winning approaches.
- Copy ideas into your own `agent/agent.py` implementation.
- Do not edit winner files directly in contributor PRs.

When your PR wins, the bot will update those files for you.

## Local Development

Install the package and run tests:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Run a quick local demo with the CLI:

```bash
export OPENROUTER_API_KEY=<your-openrouter-api-key>

imagent "Create a three-panel infographic titled Context Gap Toolkit with sections Plan, Ground, Verify."
```

The CLI defaults to `agent.agent:ImageAgent`, so contributors can test the
reference agent or their own local edits to `agent/agent.py`. To run another
agent class, pass `--agent module.path:ClassName`. The same CLI can also be run
without installing the console script:

```bash
python -m imagent_runtime \
  "Create a polished benchmark badge titled CLI PASS."
```

Each CLI run creates `results/<UTC datetime>/` automatically if it does not
exist. The generated image and trace are saved under:

- `results/<UTC datetime>/images/<UTC datetime>.<ext>`
- `results/<UTC datetime>/traces/<UTC datetime>.json`

Pass `--run-id` and `--output-dir` only when you need custom artifact names or a
custom results location. The older `--prompt "..."` flag remains supported, but
the preferred format is `imagent "..."`.

Run the same flow from Python:

```python
import os
from pathlib import Path

from agent.agent import ImageAgent

os.environ["OPENROUTER_API_KEY"] = "<your-openrouter-api-key>"

agent = ImageAgent()
agent.setup({}, Path("."))

result = agent.generate(
    {
        "run_id": "demo-card",
        "capability": "plan",
        "prompt": "Create a three-panel infographic titled Context Gap Toolkit with sections Plan, Ground, Verify.",
        "seed": 1001,
        "allowed_tools": ["plan"],
    },
    Path("results/demo"),
)

print(result)
```

The base agent calls OpenRouter's dedicated Image API with
`google/gemini-3.1-flash-image`, saves the generated image, and writes a JSON
trace. If `OPENROUTER_API_KEY` is not configured, generation fails clearly
instead of falling back to any local mock renderer.

`BaseImageAgent` in `agent/agent.py` is the contributor-facing reference
strategy. `AgentRuntime` lives outside the contributor surface in
`imagent_runtime/agent_runtime.py` and executes the trajectory: prepare
artifacts, collect context, construct the prompt, call OpenRouter, persist the
image, and write the trace.

## Local Benchmark

From sibling checkouts of `imagent` and `imagent-bench`:

```bash
python -m pip install -e ../imagent-bench
imagent-bench run \
  --repository . \
  --config ../imagent-bench/configs/official.json \
  --output-dir benchmark-output \
  --fail-on-policy
```

For the OpenRouter vision benchmark used by scheduled rounds:

```bash
export OPENROUTER_API_KEY=<your-openrouter-api-key>
export IMAGENT_BASELINE_SCORE=<current-winner-score>

imagent-bench run \
  --repository . \
  --config ../imagent-bench/configs/openrouter-vision-benchmark.json \
  --baseline-score "$IMAGENT_BASELINE_SCORE" \
  --output-dir benchmark-output-openrouter-vision
```

## Labels

- `pr-rules-pass`: contributor PR passed the submission gate.
- `invalid-pr`: PR was closed before benchmark because it violated submission
  rules.
- `duplicate-pr`: contributor opened more than one active candidate PR.
- `round-benchmark-running`: candidate is currently being evaluated.
- `round-eligible`: candidate exceeded the threshold this round.
- `round-winner`: candidate won the round and was selected for promotion.
- `below-threshold`: candidate did not improve enough and was closed.
- `benchmark-fail`: candidate failed tests, compilation, benchmark execution, or
  benchmark quality policy.
- `needs-rebase`: candidate stayed open after another PR won and must be rebased
  before entering another round.

## Design Principles

- Keep the base agent easy to understand.
- Make competition rules explicit and enforceable.
- Benchmark in isolated environments.
- Promote only measurable improvements.
- Preserve every winning implementation.
- Prefer transparent research artifacts over hidden leaderboard tricks.
- Build toward open, Gittensor-compatible agent markets without compromising the
  simple GitHub workflow that works today.
