# Contributing

Imagent is an open king-of-the-hill competition for image-generation agents,
built through Gittensor.

## Challenging the king

Open a pull request that adds exactly one directory under `submissions/`. See
[`submissions/README.md`](./submissions/README.md) for the bundle layout, how to
seal your provider key, and what your agent receives at run time.

Everything after that is automatic: screening, the duel, the verdict, and the
crown. No maintainer decides who wins.

Fork [`kings/current/`](./kings/current) as your starting point — that is the
agent you have to beat, in full.

## Changing the competition itself

Rules, scoring, and machinery are ordinary pull requests, reviewed by hand.

- Conventional commit-style title, for example `fix: correct p95 latency clamp`.
- One focused concern per PR.
- Say what changed and how you tested it.

```bash
uv venv .venv --python 3.12
VIRTUAL_ENV=.venv uv pip install pytest
VIRTUAL_ENV=.venv uv pip install -e ../gt-imagent-bench
.venv/bin/python -m pytest
```

Anything that can change a score — the benchmark version, the room image digest,
the judge model, a threshold — is a **rule change**. It gets announced, and it
gets a version bump, because ratings either side of it are not comparable.

## Ground rules

- Generation stays fixed to one image model, enforced in the sealed room rather
  than by honour.
- Objective facts decide first; taste only breaks close calls.
- Candidate code is untrusted and never runs with repository credentials in
  scope.
- Infrastructure failures never count against a miner.
- Benchmark history and every reign stay public.

## License

By contributing you agree that your contributions are licensed under this
repository's license.
