"""
Image Bench Judge Model Inference Tool

Evaluate text-to-image generated images using a judge model.
Uses the OpenRouter chat-completions API for multimodal judge inference.

Per-row output preserves all original input fields plus:
  - judge_model_output: combined raw scores JSON across all L1 dimensions
  - <dim>_judge_output: raw judge model text for each L1 dimension

Bench-level scores (L1 / L2 / Total) are aggregated following the
compute_scores.py methodology and saved alongside the per-row output.
"""

import argparse
import base64
import json
import sys
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import pandas as pd
from PIL import Image
from tqdm import tqdm

from checklists import (
    DIM_TO_CHECKLIST,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    format_checklist_for_dims,
    parse_dims_by_level1,
)
from score_utils import (
    aggregate_total_score,
    compute_dimension_score,
    extract_json_from_response,
    fix_score_json,
)
from backends.openrouter_backend import OpenRouterJudge
from runtime_config import (
    DEFAULT_HF_DATASET_FILENAME,
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_OPENROUTER_MAX_CONCURRENT_REQUESTS,
    DEFAULT_OPENROUTER_MAX_NEW_TOKENS,
    DEFAULT_OPENROUTER_MAX_RETRIES,
    DEFAULT_OPENROUTER_REQUEST_TIMEOUT,
    DEFAULT_OPENROUTER_SITE_TITLE,
    DEFAULT_OPENROUTER_TEMPERATURE,
    DEFAULT_OPENROUTER_TOP_P,
    resolve_judge_runtime_config,
)


DIM_OUTPUT_MAP = {
    "Quality": "quality_judge_output",
    "Aesthetics": "aesthetics_judge_output",
    "Alignment": "alignment_judge_output",
    "Real-world Fidelity": "real_world_fidelity_judge_output",
    "Creative Generation": "creative_generation_judge_output",
}

def load_and_resize_image(path):
    """Load image and downscale large inputs while preserving aspect ratio."""
    with Image.open(path) as src:
        img = src.convert("RGB")
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024), Image.LANCZOS)
    img.load()
    return img


def image_to_data_url(image):
    """Encode a PIL image as a PNG data URL for OpenRouter image input."""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def load_input_file(file_path):
    """Load CSV or JSON/JSONL input file."""
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(file_path)
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content.startswith("["):
            return pd.DataFrame(json.loads(content))
        else:
            records = [json.loads(line) for line in content.splitlines() if line.strip()]
            return pd.DataFrame(records)
    elif ext == ".jsonl":
        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return pd.DataFrame(records)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .csv, .json, or .jsonl")


def load_bench_metadata(
    hf_bench_repo=None,
    local_metadata=None,
    hf_filename=DEFAULT_HF_DATASET_FILENAME,
):
    """Load bench metadata containing dims_en per ID."""
    if local_metadata:
        return load_input_file(local_metadata)

    if hf_bench_repo:
        from huggingface_hub import hf_hub_download

        local_file = hf_hub_download(
            repo_id=hf_bench_repo,
            filename=hf_filename,
            repo_type="dataset",
        )
        records = []
        with open(local_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return pd.DataFrame(records)

    default_path = Path(__file__).parent / "metadata" / "bench_metadata.json"
    if default_path.exists():
        return load_input_file(str(default_path))

    print("ERROR: No metadata source found. Provide --hf-bench-repo, --local-metadata,")
    print(f"       or place metadata at {default_path}")
    sys.exit(1)


def _parse_output_to_scores(output_text, level1_dim):
    """Parse raw judge model output → fixed score_json. Returns None on failure."""
    score_json = extract_json_from_response(output_text)
    if score_json is None:
        return None
    return fix_score_json(score_json, level1_dim)


def _flush_inference_batch(
    judge,
    batch_tasks,
    batch_meta,
    row_dim_raw_scores,
    row_raw_outputs,
):
    """Execute one inference batch and merge parsed results into row-indexed stores."""
    outputs = judge.generate_batch(batch_tasks)
    if len(outputs) != len(batch_meta):
        raise RuntimeError(
            f"Judge backend returned {len(outputs)} outputs for {len(batch_meta)} requests"
        )
    parse_failures = 0

    for (row_idx, level1_dim), output_text in zip(batch_meta, outputs):
        row_dim_raw_scores.setdefault(row_idx, {})
        row_raw_outputs.setdefault(row_idx, {})
        row_raw_outputs[row_idx][level1_dim] = output_text
        score_json = _parse_output_to_scores(output_text, level1_dim)
        if score_json is None:
            parse_failures += 1
        row_dim_raw_scores[row_idx][level1_dim] = score_json

    return parse_failures


def _run_batch_inference(judge, args, input_df, metadata_df, desc):
    """Batch inference over all rows and dimensions."""
    metadata_lookup = (
        metadata_df.drop_duplicates(subset=["ID"])
        .set_index("ID")["dims_en"]
        .to_dict()
    )

    batch_tasks = []
    batch_meta = []
    skipped_rows = set()
    missing_metadata_ids = []
    image_failures = 0
    row_dim_raw_scores = {}
    row_raw_outputs = {}
    parse_failures = 0
    total_tasks = 0

    progress = tqdm(desc=desc, unit="task")
    for row_idx, (_, row) in enumerate(input_df.iterrows()):
        row_id = row["ID"]
        prompt = row["prompt"]
        image_path = row["image_path"]

        dims_en = metadata_lookup.get(row_id)
        if not dims_en:
            skipped_rows.add(row_idx)
            missing_metadata_ids.append(row_id)
            continue

        dims_by_level1 = parse_dims_by_level1(dims_en)

        try:
            img = load_and_resize_image(image_path)
            image_data_url = image_to_data_url(img)
        except Exception as e:
            image_failures += 1
            skipped_rows.add(row_idx)
            print(f"WARNING: Failed to load image for ID={row_id}, path={image_path}: {e}")
            continue

        for level1_dim, dim_pairs in dims_by_level1.items():
            if level1_dim not in DIM_TO_CHECKLIST:
                continue
            checklist = format_checklist_for_dims(level1_dim, dim_pairs)
            if not checklist:
                continue
            user_text = USER_PROMPT_TEMPLATE.format(
                prompt=prompt,
                level1_dim=level1_dim,
                format_checklist=checklist,
            )
            batch_tasks.append({
                "system_prompt": SYSTEM_PROMPT,
                "user_text": user_text,
                "image_data_url": image_data_url,
            })
            batch_meta.append((row_idx, level1_dim))
            total_tasks += 1

            if len(batch_tasks) >= args.batch_size:
                parse_failures += _flush_inference_batch(
                    judge,
                    batch_tasks,
                    batch_meta,
                    row_dim_raw_scores,
                    row_raw_outputs,
                )
                progress.update(len(batch_tasks))
                batch_tasks = []
                batch_meta = []

    if batch_tasks:
        parse_failures += _flush_inference_batch(
            judge,
            batch_tasks,
            batch_meta,
            row_dim_raw_scores,
            row_raw_outputs,
        )
        progress.update(len(batch_tasks))

    progress.close()
    print(f"Total inference tasks: {total_tasks}")
    if missing_metadata_ids:
        preview = ", ".join(str(x) for x in missing_metadata_ids[:10])
        print(
            "WARNING: Missing benchmark metadata for "
            f"{len(missing_metadata_ids)} rows (first IDs: {preview})"
        )

    results = []
    all_dim_raw_scores = []
    for row_idx, (_, row) in enumerate(input_df.iterrows()):
        if row_idx in skipped_rows:
            results.append(_empty_result(row))
            all_dim_raw_scores.append({})
            continue
        dim_raw_scores = row_dim_raw_scores.get(row_idx, {})
        dim_raw_outputs = row_raw_outputs.get(row_idx, {})
        results.append(_build_row_result(row, dim_raw_scores, dim_raw_outputs))
        all_dim_raw_scores.append(dim_raw_scores)

    return results, parse_failures, all_dim_raw_scores, image_failures


def run_openrouter_inference(args, input_df, metadata_df):
    """Run inference using the OpenRouter chat-completions API."""
    print(f"Using OpenRouter model: {args.runtime.model}")
    judge = OpenRouterJudge(
        model=args.runtime.model,
        api_key=args.runtime.api_key,
        max_batch_size=args.runtime.max_batch_size,
        max_new_tokens=args.runtime.max_new_tokens,
        base_url=args.runtime.base_url,
        request_timeout=args.runtime.request_timeout,
        site_url=args.runtime.site_url,
        site_title=args.runtime.site_title,
        max_retries=args.runtime.max_retries,
        temperature=args.runtime.temperature,
        top_p=args.runtime.top_p,
    )
    print("OpenRouter client configured successfully.")
    return _run_batch_inference(judge, args, input_df, metadata_df, desc="API inference")


def _empty_result(row):
    """Build an empty result row for skipped entries."""
    result = dict(row)
    result["judge_model_output"] = None
    for col in DIM_OUTPUT_MAP.values():
        result[col] = None
    return result


def _build_row_result(row, dim_raw_scores, dim_raw_outputs):
    """
    Build per-row JSONL record.

    Schema (in order):
      - all original row fields (transparent pass-through)
      - judge_model_output: JSON-serialized {L1_dim: fixed_score_json} for all parsed dims
      - <dim>_judge_output: raw judge text for each L1 dim
    """
    result = dict(row)

    raw_output = {
        dim_name: score_json
        for dim_name, score_json in dim_raw_scores.items()
        if score_json is not None
    }
    result["judge_model_output"] = (
        json.dumps(raw_output, ensure_ascii=False) if raw_output else None
    )

    for dim_name, col_name in DIM_OUTPUT_MAP.items():
        result[col_name] = dim_raw_outputs.get(dim_name)

    return result


def _json_safe_value(value):
    if isinstance(value, dict):
        return {k: _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe_value(v) for v in value]
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


def save_output(results, input_path):
    """Save per-row results to file in same directory as input."""
    input_p = Path(input_path)
    ext = input_p.suffix.lower()
    output_name = f"{input_p.stem}_judged{ext}"
    output_path = input_p.parent / output_name

    if ext == ".csv":
        df = pd.DataFrame(results)
        df.to_csv(output_path, index=False, encoding="utf-8")
    elif ext == ".json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                [_json_safe_value(row) for row in results],
                f,
                ensure_ascii=False,
                indent=2,
            )
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            for row in results:
                f.write(json.dumps(_json_safe_value(row), ensure_ascii=False) + "\n")

    return str(output_path)


def _safe_mean(xs):
    return sum(xs) / len(xs) if xs else None


def compute_bench_scores(all_dim_raw_scores):
    """
    Bench-level aggregation following compute_scores.py methodology:
      per-row L3→L2→L1→Total nested averaging,
      then arithmetic mean across rows (None values skipped).
    """
    l1_accum = defaultdict(list)
    l2_accum = defaultdict(lambda: defaultdict(list))
    total_accum = []

    for row_scores in all_dim_raw_scores:
        dim_results = {}
        for l1_dim, score_json in row_scores.items():
            if score_json is None:
                continue
            dim_results[l1_dim] = compute_dimension_score(score_json)

        row_total = aggregate_total_score(dim_results)
        if row_total is not None:
            total_accum.append(row_total)

        for l1_dim, dim_data in dim_results.items():
            if dim_data["level1_score"] is not None:
                l1_accum[l1_dim].append(dim_data["level1_score"])
            for l2_name, l2_score in dim_data["level2_scores"].items():
                if l2_score is not None:
                    l2_accum[l1_dim][l2_name].append(l2_score)

    return {
        "level1": {d: _safe_mean(v) for d, v in l1_accum.items()},
        "level2": {
            d: {l2: _safe_mean(v) for l2, v in l2d.items()}
            for d, l2d in l2_accum.items()
        },
        "total": _safe_mean(total_accum),
    }


def save_bench_scores(bench, input_path):
    """Save bench-level scores as JSON + Excel beside the input file."""
    input_p = Path(input_path)
    base = input_p.parent / f"{input_p.stem}_bench_scores"
    json_path = f"{base}.json"
    xlsx_path = f"{base}.xlsx"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(bench, f, ensure_ascii=False, indent=2)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        l1_rows = [{"Dimension": d, "Score": s} for d, s in bench["level1"].items()]
        l1_rows.append({"Dimension": "Total", "Score": bench["total"]})
        pd.DataFrame(l1_rows).to_excel(writer, sheet_name="Level-1 Summary", index=False)

        for dim, l2_dict in bench["level2"].items():
            if not l2_dict:
                continue
            df = pd.DataFrame(
                [{"Sub-dimension": l2, "Score": s} for l2, s in l2_dict.items()]
            )
            df.to_excel(writer, sheet_name=dim[:31], index=False)

    return json_path, xlsx_path


def print_bench_scores(bench):
    """Pretty-print bench-level scores to terminal."""
    print("\n" + "=" * 70)
    print("BENCH-LEVEL SCORES")
    print("=" * 70)
    for dim, score in bench["level1"].items():
        s = f"{score:.2f}" if score is not None else "N/A"
        print(f"  L1 {dim:30s}: {s}")
    total = bench["total"]
    total_str = f"{total:.2f}" if total is not None else "N/A"
    print(f"  {'TOTAL':33s}: {total_str}")
    print("-" * 70)
    for dim, l2_dict in bench["level2"].items():
        if not l2_dict:
            continue
        print(f"  [{dim}]")
        for l2, s in l2_dict.items():
            v = f"{s:.2f}" if s is not None else "N/A"
            print(f"    L2 {l2:28s}: {v}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Image Bench Judge Model Inference Tool"
    )
    parser.add_argument("--input", required=True, help="Input CSV/JSON/JSONL with ID, prompt, image_path")
    parser.add_argument(
        "--model",
        default=None,
        help="OpenRouter model slug (default: OPENROUTER_MODEL env var)",
    )
    parser.add_argument(
        "--openrouter-api-key",
        default=None,
        help="OpenRouter API key (default: OPENROUTER_API_KEY env var)",
    )
    parser.add_argument(
        "--openrouter-base-url",
        default=None,
        help=(
            "OpenRouter API base URL "
            f"(default: OPENROUTER_BASE_URL env var or {DEFAULT_OPENROUTER_BASE_URL})"
        ),
    )
    parser.add_argument(
        "--openrouter-site-url",
        default=None,
        help="Optional HTTP-Referer header for OpenRouter ranking attribution (default: OPENROUTER_SITE_URL env var)",
    )
    parser.add_argument(
        "--openrouter-site-title",
        default=None,
        help=(
            "Optional X-OpenRouter-Title header "
            f"(default: OPENROUTER_SITE_TITLE env var or {DEFAULT_OPENROUTER_SITE_TITLE})"
        ),
    )
    parser.add_argument("--hf-bench-repo", default=None, help="HF dataset repo for bench metadata")
    parser.add_argument(
        "--hf-filename",
        default=None,
        help=(
            "Dataset filename inside --hf-bench-repo "
            f"(default: IMAGE_BENCH_HF_FILENAME env var or {DEFAULT_HF_DATASET_FILENAME})"
        ),
    )
    parser.add_argument("--local-metadata", default=None, help="Local metadata file path (skip HF download)")
    parser.add_argument(
        "--max-batch-size",
        type=int,
        default=None,
        help=(
            "Maximum number of concurrent OpenRouter requests "
            f"(default: OPENROUTER_MAX_CONCURRENT_REQUESTS env var or {DEFAULT_OPENROUTER_MAX_CONCURRENT_REQUESTS})"
        ),
    )
    parser.add_argument(
        "--openrouter-max-retries",
        type=int,
        default=None,
        help=(
            "Retry count for transient OpenRouter failures "
            f"(default: OPENROUTER_MAX_RETRIES env var or {DEFAULT_OPENROUTER_MAX_RETRIES})"
        ),
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help=(
            "Sampling temperature "
            f"(default: OPENROUTER_TEMPERATURE env var or {DEFAULT_OPENROUTER_TEMPERATURE})"
        ),
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=None,
        help=f"Nucleus sampling value (default: OPENROUTER_TOP_P env var or {DEFAULT_OPENROUTER_TOP_P})",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=None,
        help=(
            "Maximum completion tokens "
            f"(default: OPENROUTER_MAX_NEW_TOKENS env var or {DEFAULT_OPENROUTER_MAX_NEW_TOKENS})"
        ),
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=None,
        help=(
            "Per-request timeout in seconds for OpenRouter calls "
            f"(default: OPENROUTER_REQUEST_TIMEOUT env var or {DEFAULT_OPENROUTER_REQUEST_TIMEOUT})"
        ),
    )

    args = parser.parse_args()
    try:
        args.runtime = resolve_judge_runtime_config(args)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    args.batch_size = args.runtime.max_batch_size

    # Load input
    print(f"Loading input: {args.input}")
    input_df = load_input_file(args.input)
    required_cols = {"ID", "prompt", "image_path"}
    missing = required_cols - set(input_df.columns)
    if missing:
        print(f"ERROR: Input file missing required columns: {missing}")
        sys.exit(1)
    print(f"Input: {len(input_df)} rows")

    # Load metadata
    print("Loading bench metadata...")
    metadata_df = load_bench_metadata(
        hf_bench_repo=args.hf_bench_repo,
        local_metadata=args.local_metadata,
        hf_filename=args.runtime.hf_filename,
    )
    print(f"Metadata: {len(metadata_df)} rows")

    # Run inference
    results, parse_failures, all_dim_raw_scores, image_failures = run_openrouter_inference(
        args,
        input_df,
        metadata_df,
    )

    # Save per-row JSONL
    saved_path = save_output(results, args.input)
    print(f"\nPer-row results saved to: {saved_path}")
    if image_failures:
        print(f"Skipped (broken images): {image_failures}")
    print(f"Parse failures: {parse_failures}")

    # Compute & save bench-level scores
    bench = compute_bench_scores(all_dim_raw_scores)
    json_path, xlsx_path = save_bench_scores(bench, args.input)
    print(f"Bench scores saved to: {json_path}")
    print(f"Bench scores saved to: {xlsx_path}")
    print_bench_scores(bench)


if __name__ == "__main__":
    main()
