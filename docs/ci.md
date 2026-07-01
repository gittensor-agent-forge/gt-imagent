# Benchmark CI

The PR benchmark workflow checks out both the base branch and the pull request
head. It installs benchmark code from the base checkout, then evaluates:

- the OpenRouter baseline agent from the base checkout,
- the OpenRouter candidate agent from the pull request checkout.

The comparison step uses acceptance rules from `configs/pr-gate.yaml` in the
base checkout. This prevents a pull request from weakening the benchmark runner,
task suite, evaluator, or thresholds in the same change that it is trying to
merge.

The workflow runs the benchmark for every PR. The strict improvement gate is
enforced only when files under `agents/openrouter_baseline/` change, so
documentation, configuration, or CI-only changes can still be reviewed without
pretending to be agent improvements. In those cases the follow-up verdict
workflow posts a neutral benchmark comment instead of labeling the PR as passed.

The workflow uses `pull_request`, not `pull_request_target`, and does not expose
repository secrets to candidate code.

Trusted live API benchmarks are handled by separate workflows:

- `.github/workflows/benchmark-api-pr.yml`
- `.github/workflows/benchmark-api-main.yml`

These workflows use the protected `benchmark-api` environment. The PR workflow
only runs for same-repository branches that are labeled
`trusted-api-benchmark`, and both workflows skip execution when required API
secrets are not configured.
