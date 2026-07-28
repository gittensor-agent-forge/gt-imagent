# Contributing

Imagent is an open research project for image-generation agents, built through
Gittensor.

## There is no open contribution track right now

The previous tracks — Agent Benchmark rounds, Generation UI, and Leaderboard UI —
have been retired along with their automation, labels, and PR templates. The
workflow is being rebuilt around a king-of-the-hill competition where a
challenger agent must beat the reigning agent head to head on the same problems.

Until that lands, unsolicited pull requests will not be benchmarked, scored, or
merged. Please open an issue to discuss anything you want to work on first.

## What still applies

If you do open a PR:

- Use a conventional commit-style title, for example `fix: correct p95 latency
  clamp`.
- Keep one focused concern per PR and one atomic commit.
- Describe what changed and how you tested it.
- Run the checks below before pushing.

```bash
uv venv .venv --python 3.12
VIRTUAL_ENV=.venv uv pip install pytest
.venv/bin/python -m pytest
```

CI also verifies the agent still satisfies the submission contract by loading it
with the pinned engine.

The scoring engine and the dashboard live in their own repositories:

- [gt-imagent-bench](https://github.com/gittensor-agent-forge/gt-imagent-bench)
- [gt-imagent-ui](https://github.com/gittensor-agent-forge/gt-imagent-ui)

## Ground rules for the rebuild

These constraints are settled and will carry into the new competition:

- Generation stays fixed to one image model. The competition measures agent
  design, not model choice.
- Candidate agent code is untrusted. It never runs with repository credentials
  in scope.
- Benchmark history and every prior incumbent stay public.
- Scoring must be reproducible from published artifacts.

## License

By contributing you agree that your contributions are licensed under this
repository's license.
