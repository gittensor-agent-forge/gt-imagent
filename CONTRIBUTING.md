# Contributing

Imagent is built through Gittensor as an open environment for image-agent
research. The active GitHub contribution track is a manual Leaderboard UI
competition. It makes the benchmark archive easier to understand without
changing benchmark results, agent code, runtime behavior, or the Generation
page.

## Active Competition

Contributors may submit one focused Leaderboard UI pull request at a time.
The completed Home page is the visual standard: preserve the dark product
language, deliberate spacing, readable hierarchy, responsive behavior, and
intentional motion.

The PR rules workflow accepts only these files:

- imagent-ui/app/leaderboard/page.tsx
- imagent-ui/app/components/LeaderboardBoard.tsx
- Leaderboard-local .tsx and .css files under imagent-ui/app/leaderboard/
- Leaderboard-local .tsx and .css files under
  imagent-ui/app/leaderboard/components/
- imagent-ui/app/styles.css, limited to selectors used by the Leaderboard

Do not change API routes, report parsing, agent code, runtime code, benchmark
logic, dependency metadata, deployment configuration, shared navigation, the
Generation page, or unrelated pages. PRs outside the approved surface are
labeled invalid-pr and closed automatically.

Every Leaderboard UI PR must:

- Use a conventional title, such as style: improve leaderboard filter states.
- Select Leaderboard UI in the PR template.
- Complete Summary, Motivation, Changes, and Testing.
- Include at least one screenshot or video link in the PR description.
- Keep one atomic concern and one atomic commit.
- Keep only one open Leaderboard UI PR at a time.

The validator adds leaderboard-ui and leaderboard-ui-pass to a valid
submission. If visual evidence is missing, it leaves the PR open, adds
needs-evidence, and posts instructions. The competition is manually reviewed:
no Leaderboard UI PR is benchmarked or auto-merged. Maintainers select and merge
the strongest coherent design; valid non-winning submissions stay open for a
later update or review.

## Paused Tracks

Agent Benchmark and Generation UI competitions are paused. Contributor PRs for
agent/agent.py, the Generation page, or any other non-Leaderboard scope are
closed by the active contributor gate. The agent implementation, winner archive,
benchmark tooling, and historical reports remain available as reference
material; they are not active contribution targets.

Existing legacy PRs are not retroactively closed by this policy. Maintainers can
review or close them deliberately.

## Gittensor Relationship

Gittensor supports the open software market Imagent is building toward. The
current Leaderboard UI competition makes the project legible in public: people
can see the benchmark archive, understand how prior image-agent work was
evaluated, and improve the interface through focused GitHub pull requests.

You do not need Discord access or subnet-specific knowledge to participate. The
GitHub workflow and the public site are the source of truth for the active
competition.

## Maintainer Work

Owners, members, and collaborators are excluded from contributor-track
validation. Maintainers must still use reviewable PRs and merge them manually.
Use maintainer PRs for infrastructure, documentation, model/runtime changes,
agent experiments, benchmark maintenance, and changes outside the Leaderboard UI
surface.

## Local Development

Install the root package and test suite:

~~~bash
python -m pip install -e ".[dev]"
python -m pytest
~~~

For the website:

~~~bash
cd imagent-ui
npm ci
npm run lint
npm run build
~~~

Live image generation requires OPENROUTER_API_KEY. The local agent CLI and
imagent-bench remain available for research, but no scheduled agent benchmark
round currently runs in GitHub Actions.

## Labels

- leaderboard-ui: PR selected the active Leaderboard UI track.
- leaderboard-ui-pass: PR passed the automated title, template, and file scope
  gate.
- needs-evidence: valid Leaderboard UI PR is missing a screenshot or video.
- invalid-pr: PR was closed because it violates the active contributor policy.
- duplicate-pr: contributor opened more than one active Leaderboard UI PR.
