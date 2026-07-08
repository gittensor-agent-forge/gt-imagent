# Image Bench

<p align="center">
  <a href="https://www.apache.org/licenses/LICENSE-2.0"><img src="https://img.shields.io/badge/License-Apache_2.0-blue" alt="License"></a>
</p>

An evaluation toolkit and official runner for `imagent` image agents. It has two
entrypoint families:

- `imagent-bench run`: execute an agent repository against the official suite and
  write a canonical benchmark report.
- `judge.py` / `compute_scores.py`: score already-generated images with the
  OpenRouter judge workflow.

The judge workflow evaluates generated images and aggregates scores across 5 top-level dimensions:

- Quality
- Aesthetics
- Alignment
- Real-world Fidelity
- Creative Generation

The scoring hierarchy covers 23 sub-dimensions and 56 fine-grained facets. Per-row outputs preserve the raw judge responses, and the toolkit also produces aggregated benchmark summaries in JSON and Excel.

## Quick Start

```bash
# 1. Clone the repo
git clone <your-repo-url> image-bench
cd image-bench

# 2. Create an environment
uv venv .venv --python 3.11
source .venv/bin/activate

# 3. Install Python dependencies
uv pip install -r requirements.txt
uv pip install -e ".[dev]"
```

## Official Agent Benchmark

Run the deterministic local suite against a local `imagent` checkout:

```bash
imagent-bench run \
  --repository ../imagent \
  --config configs/official.json \
  --output-dir benchmark-output \
  --fail-on-policy
```

The runner:

1. loads the candidate repository's `agent/agent.yaml`;
2. instantiates the declared `module:Class` entrypoint;
3. calls `setup(config, workdir)`;
4. executes every case in `src/imagent_bench/suites/official_v1/cases.jsonl`;
5. verifies public expected checks;
6. writes `benchmark-report.json` and `benchmark-summary.md`.

Benchmarks require OpenRouter for real image generation. If `OPENROUTER_API_KEY`
is missing or invalid, the run fails instead of falling back to a mock renderer.
Production contributor PRs use the OpenRouter vision benchmark after the PR
rules gate passes.

### OpenRouter Vision Benchmark

Use this for paid scoring and merge eligibility. It runs a small multi-case live
suite, lets the agent use its candidate/feedback loop, scores each case with an
OpenRouter vision judge, and compares the aggregate result against the current
top merged baseline score.

Generation is fixed to `google/gemini-3.1-flash-image` through OpenRouter so
rounds measure agent planning, prompt construction, context use, and iteration
against one shared underlying image model.

```bash
export OPENROUTER_API_KEY=<your-openrouter-api-key>
export IMAGENT_BASELINE_SCORE=82.0
export IMAGENT_BASELINE_COMMIT=<current-top-commit>

imagent-bench run \
  --repository ../imagent \
  --config configs/openrouter-vision-benchmark.json \
  --baseline-score "$IMAGENT_BASELINE_SCORE" \
  --baseline-commit "$IMAGENT_BASELINE_COMMIT" \
  --output-dir benchmark-output-openrouter-vision \
  --fail-on-policy
```

The report includes `ranking` metadata:

- `delta`: candidate score minus current top baseline score.
- `label`: `score-regression`, `improvement-minor`, `improvement-strong`, or
  `improvement-major`.
- `merge_eligible`: true only when the configured minimum improvement threshold
  is met.

### Z.AI Live Smoke Test

Use this when you want to verify real image generation with a Z.AI API key. It
generates one image with `glm-image` through Z.AI's image generation endpoint
and writes the normal benchmark report/artifacts.

```bash
export ZAI_API_KEY=<your-zai-api-key>

imagent-bench run \
  --repository ../imagent \
  --config configs/zai-live-smoke.json \
  --output-dir benchmark-output-zai \
  --fail-on-policy
```

This is a smoke test, not the official PR gate. It intentionally uses one case,
one candidate, no feedback rounds, and no raster-image text assertion so it does
not require a paid vision judge call after image generation.

### OpenRouter Live Smoke Test

Use this when you want to verify real image generation through OpenRouter's
dedicated Image API.

```bash
export OPENROUTER_API_KEY=<your-openrouter-api-key>

imagent-bench run \
  --repository ../imagent \
  --config configs/openrouter-live-smoke.json \
  --output-dir benchmark-output-openrouter \
  --fail-on-policy
```

This also runs one case, one candidate, no feedback rounds, and no raster-image
text assertion. It verifies the real provider path and writes the normal report,
image artifact, trace, and logs. The config uses the project-standard
`google/gemini-3.1-flash-image` model through OpenRouter with `resolution: 1K`
and `aspect_ratio: 1:1`.

### Runner API

```python
from imagent_bench import run

result = run(
    repository="../imagent",
    commit="abc123",
    config="configs/official.json",
    output_dir="benchmark-output",
)
```

The returned result is serializable through `result.to_dict()` and has the same
shape as `benchmark-output/benchmark-report.json`.

### Report Contract

The canonical report schema lives at
`schemas/benchmark-report.schema.json`. The report includes:

- overall status and score;
- benchmark and dataset versions;
- commit SHA;
- per-case scores, checks, latency, cost, and artifacts;
- optional per-case judge dimensions and judge metadata;
- optional baseline ranking and merge eligibility metadata;
- aggregate latency/cost metrics;
- policy thresholds and failure reasons;
- logs and generated image/trace artifacts.

## Judge Existing Images

```bash
# 4. Create a local .env file
cp .env.example .env

# 5. Edit .env with your OpenRouter configuration
#    OPENROUTER_API_KEY=<your-openrouter-api-key>
#    OPENROUTER_MODEL=openai/gpt-5.5

# 6. Run the judge on your images
python3 judge.py \
  --input your_data.jsonl
```

## Input Format

Your input file can be CSV, JSON, or JSONL and must include these columns:

| Column | Type | Description |
|--------|------|-------------|
| `ID` | int | Prompt identifier that matches [metadata/bench_metadata.json](metadata/bench_metadata.json) |
| `prompt` | str | The text prompt used to generate the image |
| `image_path` | str | Path to the generated image file |

Additional columns are preserved in the judged output.

## Installation

```bash
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
```

Then configure your runtime with environment variables. Both `judge.py` and
`compute_scores.py` auto-load a local `.env` file if present, so the normal flow is:

```bash
cp .env.example .env
```

And set values in `.env`:

```bash
OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_MODEL=openai/gpt-5.5
```

## Usage

### Judge New Images

```bash
python3 judge.py \
  --input your_data.jsonl
```

Optional metadata sources:

- `--local-metadata metadata/bench_metadata.json`
- `--hf-bench-repo your-dataset-repo --hf-filename image_bench_responses.jsonl`

OpenRouter model notes:

- The judge no longer hardcodes a model slug.
- Set `OPENROUTER_MODEL` in `.env`/your shell, or pass `--model`.
- Operational settings can be configured by env variables without editing code.

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | required | OpenRouter API key |
| `OPENROUTER_MODEL` | required | OpenRouter model slug |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter base URL |
| `OPENROUTER_SITE_URL` | — | Optional `HTTP-Referer` header |
| `OPENROUTER_SITE_TITLE` | `Image Bench` | Optional `X-OpenRouter-Title` header |
| `IMAGE_BENCH_HF_FILENAME` | `image_bench_responses.jsonl` | Dataset filename used with `--hf-bench-repo` or `--hf-repo` |
| `OPENROUTER_MAX_CONCURRENT_REQUESTS` | `24` | Maximum concurrent OpenRouter requests |
| `OPENROUTER_MAX_RETRIES` | `3` | Retry count for transient API failures |
| `OPENROUTER_TEMPERATURE` | `0.0` | Sampling temperature |
| `OPENROUTER_TOP_P` | `1.0` | Nucleus sampling value |
| `OPENROUTER_MAX_NEW_TOKENS` | `4096` | Max generation tokens |
| `OPENROUTER_REQUEST_TIMEOUT` | `120` | Per-request timeout in seconds |

#### CLI Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | required | Input CSV/JSON/JSONL with `ID`, `prompt`, `image_path` |
| `--model` | `OPENROUTER_MODEL` | OpenRouter model slug |
| `--openrouter-api-key` | `OPENROUTER_API_KEY` | OpenRouter API key |
| `--openrouter-base-url` | `OPENROUTER_BASE_URL` or `https://openrouter.ai/api/v1` | OpenRouter base URL |
| `--openrouter-site-url` | `OPENROUTER_SITE_URL` | Optional `HTTP-Referer` header |
| `--openrouter-site-title` | `OPENROUTER_SITE_TITLE` or `Image Bench` | Optional `X-OpenRouter-Title` header |
| `--hf-bench-repo` | — | Dataset repo used to fetch metadata |
| `--hf-filename` | `IMAGE_BENCH_HF_FILENAME` or `image_bench_responses.jsonl` | Filename inside `--hf-bench-repo` |
| `--local-metadata` | — | Local metadata file path |
| `--max-batch-size` | `OPENROUTER_MAX_CONCURRENT_REQUESTS` or `24` | Maximum number of concurrent OpenRouter requests |
| `--openrouter-max-retries` | `OPENROUTER_MAX_RETRIES` or `3` | Retry count for transient API failures |
| `--temperature` | `OPENROUTER_TEMPERATURE` or `0.0` | Sampling temperature |
| `--top-p` | `OPENROUTER_TOP_P` or `1.0` | Nucleus sampling value |
| `--max-new-tokens` | `OPENROUTER_MAX_NEW_TOKENS` or `4096` | Max generation tokens |
| `--request-timeout` | `OPENROUTER_REQUEST_TIMEOUT` or `120` | Per-request timeout in seconds |

Recommended env variables:

```bash
OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_MODEL=openai/gpt-5.5
OPENROUTER_MAX_CONCURRENT_REQUESTS=24
OPENROUTER_MAX_NEW_TOKENS=4096
OPENROUTER_REQUEST_TIMEOUT=120
```

#### Output Files

After running `judge.py`, files are written next to the input:

| File | Contents |
|------|----------|
| `<input>_judged.csv` | Per-row results for CSV input |
| `<input>_judged.json` | Per-row results as a JSON array for JSON input |
| `<input>_judged.jsonl` | Per-row results as JSON lines for JSONL input |
| `<input>_bench_scores.json` | Aggregated Level-1, Level-2, and total scores |
| `<input>_bench_scores.xlsx` | Same aggregated scores in Excel |

Per-row result rows include:

- all original input fields
- `judge_model_output`
- `quality_judge_output`
- `aesthetics_judge_output`
- `alignment_judge_output`
- `real_world_fidelity_judge_output`
- `creative_generation_judge_output`

### Compute Scores from Existing Judge Responses

```bash
# From a local JSONL file
python3 compute_scores.py --input image_bench_responses.jsonl

# Or download from a dataset repo
python3 compute_scores.py \
  --hf-repo your-dataset-repo \
  --hf-filename image_bench_responses.jsonl
```

Outputs:

- `scores_result.xlsx`
- `scores_detail.json`
- `scores_result_en.xlsx` and `scores_detail_en.json` when `_en` response columns exist

## Inference Parameters

The judge backend uses these defaults unless you override them via env vars or CLI flags:

| Parameter | Value |
|-----------|-------|
| `temperature` | `0.0` |
| `top_p` | `1.0` |
| `max_new_tokens` | `4096` |
| `max_concurrent_requests` | `24` |
| `max_retries` | `3` |
| `request_timeout` | `120s` |

## Project Structure

```text
.
├── judge.py
├── compute_scores.py
├── score_utils.py
├── checklists.py
├── backends/
│   └── openrouter_backend.py
├── metadata/
│   └── bench_metadata.json
├── requirements.txt
└── assets/
```

## Evaluation Framework

The benchmark uses a 3-level scoring hierarchy:

| Level-1 Dimension | Level-2 Sub-dimensions |
|-------------------|------------------------|
| Quality | Realism, Detail, Resolution |
| Aesthetics | Composition, Color Harmony, Lighting, Anatomical Portraiture, Emotional Expression, Style Control |
| Alignment | Attributes, Actions, Layout, Relations, Scene |
| Real-world Fidelity | Fairness, Safety & Compliance, World Knowledge |
| Creative Generation | Imagination, Feature Matching, Logical Resolution, Text Rendering, Design Applications, Visual Storytelling |

Scoring rules:

- `0` = Fail -> `0`
- `1` = Pass -> `60`
- `2` = Excel -> `100`
- `N/A` = excluded from aggregation

Scores aggregate bottom-up from Level-3 to Level-2 to Level-1 and then to the overall benchmark score.

## License

This project is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
