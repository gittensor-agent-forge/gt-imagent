# API Benchmark

The trusted API benchmark runs the Qwen baseline agent in live Qwen Image mode
and evaluates generated images with the OpenRouter image judge configured in
`configs/api-gate.yaml`.

The image judge uses the OpenRouter Chat Completions API and reads
`OPENROUTER_API_KEY`. OpenRouter exposes many vision models through one
endpoint; `configs/api-gate.yaml` defaults to `openai/gpt-4o`.

Configure the `benchmark-api` GitHub Environment with:

```text
DASHSCOPE_API_KEY
OPENROUTER_API_KEY
```

and one of:

```text
DASHSCOPE_WORKSPACE_ID
DASHSCOPE_ENDPOINT
```

The pull request API workflow runs only for same-repository branches that carry
the `trusted-api-benchmark` label because candidate agent code receives API
credentials. Forked PRs should use the offline benchmark workflow first, then be
tested from a trusted branch after a maintainer explicitly opts into the trusted
API run.

The main-branch API workflow promotes successful benchmark results into:

```text
baselines/qwen_baseline/ia_bench_v1_api/latest.json
baselines/qwen_baseline/ia_bench_v1_api/history/
```

If the required secrets are not configured, the API workflows skip live
benchmark execution and upload any available diagnostic artifacts.
