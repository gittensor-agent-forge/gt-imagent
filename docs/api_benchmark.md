# API Benchmark

The trusted API benchmark runs the OpenRouter baseline agent in live OpenRouter
image mode and evaluates generated images with the OpenRouter image judge
configured in `configs/api-gate.yaml`.

The same `OPENROUTER_API_KEY` covers both generation and judging. OpenRouter
exposes image generation through `/api/v1/images` and vision judging through the
Chat Completions endpoint; `configs/api-gate.yaml` defaults to
`openai/gpt-image-1` for generation and `openai/gpt-4o` for judging.

Configure the `benchmark-api` GitHub Environment with:

```text
OPENROUTER_API_KEY
```

The pull request API workflow runs only for same-repository branches that carry
the `trusted-api-benchmark` label because candidate agent code receives API
credentials. Forked PRs should use the offline benchmark workflow first, then be
tested from a trusted branch after a maintainer explicitly opts into the trusted
API run.

The main-branch API workflow promotes successful benchmark results into:

```text
baselines/openrouter_baseline/ia_bench_v1_api/latest.json
baselines/openrouter_baseline/ia_bench_v1_api/history/
```

If the required secrets are not configured, the API workflows skip live
benchmark execution and upload any available diagnostic artifacts.
