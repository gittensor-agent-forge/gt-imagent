# Imagent

Imagent is an open research project for image-generation agents. Its core idea
is simple: image generation should be more than a one-shot prompt call. A strong
agent should understand intent, plan, use context, generate, critique, and
improve while the image model remains one component in a larger system.

## Current Status

The active GitHub competition is Leaderboard UI. Contributors improve the public
Leaderboard experience through focused, visual, manually reviewed pull requests.

Agent Benchmark and Generation UI competitions are paused. The agent reference
implementation, winner archive, benchmark reports, and local benchmark tooling
remain available for research and historical reference, but no scheduled agent
benchmark workflow runs in GitHub Actions.

## Why This Exists

Modern image models are powerful, but prompt-to-image generation still struggles
with complex instructions, context-heavy requests, consistency, exact text, and
self-correction. Imagent treats those weaknesses as an agent-design problem.

The long-term research question remains:

Can better planning, orchestration, context use, and verification make the same
image model produce better results?

The project is designed to support modular planners, prompt builders, tool
users, self-critics, regeneration policies, memory systems, benchmark suites,
and trajectory-level evaluation.

## Built Through Gittensor

Imagent is being built through Gittensor. Gittensor supports the open
contributor market that this project is building toward: code, benchmark
history, and design work remain public, reviewable, and reusable.

You do not need Discord access or subnet-specific knowledge to understand the
relationship:

- Gittensor supports the open software market behind the project.
- Imagent exposes image-agent research, benchmark reports, and winner history
  in GitHub and on the public site.
- The active Leaderboard UI competition helps people understand that work and
  contribute through focused pull requests.
- Historical agent winners remain visible in agent/last_winner.py and winners/.

## Repository Layout

- agent/agent.py: basic reference image agent. Contributor benchmark submissions
  are currently paused.
- agent/last_winner.py: latest reference from the prior agent-round system.
- imagent_runtime/: stable runtime and CLI infrastructure for local agents.
- imagent-ui/: product website. The active contributor surface is the Leaderboard
  page UI.
- winners/: public archive of previous winning agent implementations.
- .github/workflows/pr-rules.yml: validates the active Leaderboard UI
  contribution track.
- .github/scripts/round_manager.py: retained transparent reference tooling for
  the paused agent-round system.

Benchmark suites and scoring logic live in
[imagent-bench](https://github.com/imagent-ai/imagent-bench).

## Active Competition: Leaderboard UI

Leaderboard UI submissions are manually reviewed. They are not benchmarked and
are never auto-merged.

The completed Home page is the visual standard. A submission should preserve the
dark product language, intentional motion, readable hierarchy, responsive
behavior, and spacing discipline while improving the Leaderboard page.

Contributors may change only:

- imagent-ui/app/leaderboard/page.tsx
- imagent-ui/app/components/LeaderboardBoard.tsx
- Leaderboard-local .tsx and .css files under imagent-ui/app/leaderboard/
- Leaderboard-local .tsx and .css files under
  imagent-ui/app/leaderboard/components/
- imagent-ui/app/styles.css, limited to Leaderboard selectors

Every contributor submission must:

1. Select Leaderboard UI in the pull request template.
2. Use a conventional commit-style title, such as style: refine leaderboard
   filters.
3. Complete Summary, Motivation, Changes, and Testing in the PR description.
4. Include at least one screenshot or video link showing the updated Leaderboard.
5. Change only the approved UI surface.
6. Keep one focused concern, one atomic commit, and one open Leaderboard UI PR
   per contributor.

The PR rules workflow immediately closes an out-of-scope or duplicate
submission. A scoped PR without visual evidence stays open and receives the
needs-evidence label and an automated comment.

Valid submissions receive leaderboard-ui and leaderboard-ui-pass. Maintainers
compare them and merge the strongest coherent design manually. Valid
non-winning submissions are not closed automatically and can be improved for a
later review.

## Paused Tracks

Agent Benchmark and Generation UI are not active contributor tracks. A
contributor PR that changes agent/agent.py, the Generation page, benchmark
configuration, API routes, runtime code, deployment configuration, or another
unapproved surface is labeled invalid-pr and closed.

Existing legacy PRs are not closed retroactively by this policy. Maintainers can
review or close them deliberately.

## Local Development

Install the root package and run the test suite:

~~~bash
python -m pip install -e ".[dev]"
python -m pytest
~~~

Install and validate the product website:

~~~bash
cd imagent-ui
npm ci
npm run lint
npm run build
~~~

## Local Agent Use

Live generation uses OpenRouter and the project-standard Gemini 3.1 Flash Image
model. Set OPENROUTER_API_KEY before running the CLI:

~~~bash
export OPENROUTER_API_KEY=your-openrouter-api-key
imagent "Create a polished benchmark badge titled CLI PASS."
~~~

Each run creates results/<UTC datetime>/ if needed and stores an image and JSON
trace there. The reference agent fails clearly when OpenRouter is not configured;
it does not fall back to a mock renderer.

## Local Benchmark Research

The benchmark remains useful for local research even though scheduled repository
rounds are paused:

~~~bash
python -m pip install -e ../imagent-bench
imagent-bench run \
  --repository . \
  --config ../imagent-bench/configs/official.json \
  --output-dir benchmark-output \
  --fail-on-policy
~~~

For local OpenRouter vision research, use the OpenRouter benchmark configuration
from the sibling imagent-bench checkout.

## Labels

- leaderboard-ui: contributor PR selected the active Leaderboard UI track.
- leaderboard-ui-pass: PR passed the title, template, and file-scope gate.
- needs-evidence: valid Leaderboard UI PR is missing a screenshot or video.
- invalid-pr: PR was closed because it violates the active contributor policy.
- duplicate-pr: contributor opened more than one active Leaderboard UI PR.

## Design Principles

- Keep the base agent easy to understand.
- Make contribution rules explicit and enforceable.
- Preserve benchmark history and every prior winner.
- Keep active UI contributions isolated from runtime and benchmark behavior.
- Require visual evidence before manual design review.
- Prefer transparent research artifacts over hidden leaderboard tricks.
- Build toward open, Gittensor-compatible image-agent research.
