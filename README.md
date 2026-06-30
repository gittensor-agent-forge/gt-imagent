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

## Qwen Baseline

The repository includes a Qwen-style baseline agent with a deterministic mock
mode for local testing:

```bash
python -m imagent_bench.runner \
  --config configs/qwen-smoke.yaml \
  --agent agents/qwen_baseline \
  --output results/qwen-smoke
```

Live Qwen Image generation is configured through `agent.qwen_image.mode: live`
and requires `DASHSCOPE_API_KEY` plus either `DASHSCOPE_WORKSPACE_ID` or
`DASHSCOPE_ENDPOINT`.

Trusted API benchmark runs can use GPT-5.5 as an image judge through
`configs/api-gate.yaml`. This mode requires `OPENAI_API_KEY` in addition to the
Qwen Image credentials.

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
the PR base branch, runs the base Qwen baseline and PR Qwen candidate, then
compares the results with `configs/pr-gate.yaml` when the Qwen baseline agent
changes.

Clean main-branch benchmark results can be promoted into baseline history with:

```bash
python -m imagent_bench.promote_baseline \
  --result results/api-main/results.json \
  --baseline-dir baselines/qwen_baseline/ia_bench_v1_api
```
