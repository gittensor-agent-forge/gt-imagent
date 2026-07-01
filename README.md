# imagent

`imagent` provides an open benchmark foundation for image agents. The initial
benchmark runner focuses on deterministic, inspectable evaluations so future
agent implementations and CI gates can build on a stable contract.

## Quick Start

```bash
python -m pip install -e ".[dev]"
python -m imagent_bench.config validate configs/local-smoke.yaml
python -m imagent_bench.runner \
  --config configs/local-smoke.yaml \
  --agent tests/fixtures/echo_agent \
  --output results/local-smoke
```

The smoke suite writes normalized JSON results, per-case traces, image artifacts,
and a Markdown summary under the selected output directory.

These commands assume a source checkout of this repository. The published Python
wheel includes the `imagent_bench` package and bundled task data, but it does
not install the repository-local `configs/` files or bundled baseline agent
directories.

## OpenRouter Baseline

The repository includes an OpenRouter-backed baseline agent with a deterministic
mock mode for local testing:

```bash
python -m imagent_bench.runner \
  --config configs/openrouter-smoke.yaml \
  --agent agents/openrouter_baseline \
  --output results/openrouter-smoke
```

Live generation is configured through `agent.openrouter_image.mode: live` and
requires `OPENROUTER_API_KEY`. It calls OpenRouter's image API and records the
gateway-reported spend as `cost_usd`.

Trusted API benchmark runs use the OpenRouter image judge configured in
`configs/api-gate.yaml`. This mode also uses the OpenRouter baseline agent, so
`OPENROUTER_API_KEY` covers both generation and judging.

The offline smoke and PR gate configs use the deterministic `mock_text` image
judge by default. That provider inspects generated file text for stable contract
testing; it is not a real visual-quality or semantic image assessment.

The image judge runs through the OpenRouter Chat Completions API (default model
`openai/gpt-4o`). This mode reads `OPENROUTER_API_KEY` and reaches many
vision-capable models through a single credential.

## Result Comparison

Benchmark results can be compared with configurable acceptance rules:

```bash
python -m imagent_bench.compare \
  --config configs/pr-gate.yaml \
  --baseline results/base/results.json \
  --candidate results/pr/results.json \
  --output results/comparison.json
```

## Continuous Benchmarking

Pull requests are evaluated by the offline benchmark workflow in
`.github/workflows/benchmark-pr.yml`. The workflow installs benchmark code from
the PR base branch, runs the base OpenRouter baseline and PR OpenRouter
candidate, then compares the results with `configs/pr-gate.yaml` when the
OpenRouter baseline agent changes.

Clean main-branch benchmark results can be promoted into baseline history with:

```bash
python -m imagent_bench.promote_baseline \
  --result results/api-main/results.json \
  --baseline-dir baselines/openrouter_baseline/ia_bench_v1_api
```

See `docs/api_benchmark.md` for the trusted OpenRouter benchmark workflow setup.
