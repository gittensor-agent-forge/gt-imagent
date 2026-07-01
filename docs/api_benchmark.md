# API Benchmark

The trusted API benchmark runs the Qwen baseline agent in live Qwen Image mode
and evaluates generated images with the OpenAI image judge configured in
`configs/api-gate.yaml`.

The image judge provider is configurable. `configs/api-gate.yaml` uses the OpenAI
judge and reads `OPENAI_API_KEY`. To judge through OpenRouter instead, use the
ready-made `configs/api-gate-openrouter.yaml` (or set
`evaluation.image_judge.provider: openrouter`) and provide `OPENROUTER_API_KEY`;
OpenRouter exposes many vision models through one Chat Completions endpoint.

Configure the `benchmark-api` GitHub Environment with:

```text
DASHSCOPE_API_KEY
OPENAI_API_KEY
```

and one of:

```text
DASHSCOPE_WORKSPACE_ID
DASHSCOPE_ENDPOINT
```

The pull request API workflow runs only for same-repository branches because
candidate agent code receives API credentials. Forked PRs should use the offline
benchmark workflow first, then be tested from a trusted branch if needed.

The main-branch API workflow promotes successful benchmark results into:

```text
baselines/qwen_baseline/ia_bench_v1_api/latest.json
baselines/qwen_baseline/ia_bench_v1_api/history/
```

If the required secrets are not configured, the API workflows skip live
benchmark execution and upload any available diagnostic artifacts.
