"""Centralized runtime configuration for judge and scoring entrypoints."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv

DEFAULT_HF_DATASET_FILENAME = "image_bench_responses.jsonl"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_SITE_TITLE = "Image Bench"
DEFAULT_OPENROUTER_MAX_CONCURRENT_REQUESTS = 24
DEFAULT_OPENROUTER_MAX_NEW_TOKENS = 4096
DEFAULT_OPENROUTER_REQUEST_TIMEOUT = 120
DEFAULT_OPENROUTER_MAX_RETRIES = 3
DEFAULT_OPENROUTER_TEMPERATURE = 0.0
DEFAULT_OPENROUTER_TOP_P = 1.0


@dataclass(frozen=True)
class JudgeRuntimeConfig:
    model: str
    api_key: str
    base_url: str
    site_url: str | None
    site_title: str
    hf_filename: str
    max_batch_size: int
    max_new_tokens: int
    request_timeout: int
    max_retries: int
    temperature: float
    top_p: float


def _read_env(name):
    # Re-load .env during resolution so config works even if callers import this
    # module before creating or updating a local .env file.
    load_dotenv(override=False)
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _resolve_str(value, env_name, default=None):
    return value if value not in (None, "") else _read_env(env_name) or default


def _resolve_required_str(value, env_name, label):
    resolved = _resolve_str(value, env_name)
    if resolved is None:
        raise ValueError(f"{label} not provided. Set {env_name} or pass the matching CLI flag.")
    return resolved


def _parse_int(raw_value, label, minimum=None):
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer, got: {raw_value!r}") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{label} must be >= {minimum}, got: {parsed}")
    return parsed


def _parse_float(raw_value, label, minimum=None, maximum=None):
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number, got: {raw_value!r}") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{label} must be >= {minimum}, got: {parsed}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{label} must be <= {maximum}, got: {parsed}")
    return parsed


def _resolve_int(value, env_name, default, label, minimum=None):
    if value is not None:
        return _parse_int(value, label, minimum=minimum)
    env_value = _read_env(env_name)
    if env_value is not None:
        return _parse_int(env_value, env_name, minimum=minimum)
    return default


def _resolve_float(value, env_name, default, label, minimum=None, maximum=None):
    if value is not None:
        return _parse_float(value, label, minimum=minimum, maximum=maximum)
    env_value = _read_env(env_name)
    if env_value is not None:
        return _parse_float(env_value, env_name, minimum=minimum, maximum=maximum)
    return default


def resolve_hf_dataset_filename(cli_value):
    return _resolve_str(cli_value, "IMAGE_BENCH_HF_FILENAME", DEFAULT_HF_DATASET_FILENAME)


def resolve_judge_runtime_config(args):
    return JudgeRuntimeConfig(
        model=_resolve_required_str(args.model, "OPENROUTER_MODEL", "OpenRouter model"),
        api_key=_resolve_required_str(args.openrouter_api_key, "OPENROUTER_API_KEY", "OpenRouter API key"),
        base_url=_resolve_str(
            args.openrouter_base_url,
            "OPENROUTER_BASE_URL",
            DEFAULT_OPENROUTER_BASE_URL,
        ),
        site_url=_resolve_str(args.openrouter_site_url, "OPENROUTER_SITE_URL"),
        site_title=_resolve_str(
            args.openrouter_site_title,
            "OPENROUTER_SITE_TITLE",
            DEFAULT_OPENROUTER_SITE_TITLE,
        ),
        hf_filename=resolve_hf_dataset_filename(args.hf_filename),
        max_batch_size=_resolve_int(
            args.max_batch_size,
            "OPENROUTER_MAX_CONCURRENT_REQUESTS",
            DEFAULT_OPENROUTER_MAX_CONCURRENT_REQUESTS,
            "--max-batch-size",
            minimum=1,
        ),
        max_new_tokens=_resolve_int(
            args.max_new_tokens,
            "OPENROUTER_MAX_NEW_TOKENS",
            DEFAULT_OPENROUTER_MAX_NEW_TOKENS,
            "--max-new-tokens",
            minimum=1,
        ),
        request_timeout=_resolve_int(
            args.request_timeout,
            "OPENROUTER_REQUEST_TIMEOUT",
            DEFAULT_OPENROUTER_REQUEST_TIMEOUT,
            "--request-timeout",
            minimum=1,
        ),
        max_retries=_resolve_int(
            args.openrouter_max_retries,
            "OPENROUTER_MAX_RETRIES",
            DEFAULT_OPENROUTER_MAX_RETRIES,
            "--openrouter-max-retries",
            minimum=0,
        ),
        temperature=_resolve_float(
            args.temperature,
            "OPENROUTER_TEMPERATURE",
            DEFAULT_OPENROUTER_TEMPERATURE,
            "--temperature",
            minimum=0.0,
        ),
        top_p=_resolve_float(
            args.top_p,
            "OPENROUTER_TOP_P",
            DEFAULT_OPENROUTER_TOP_P,
            "--top-p",
            minimum=0.0,
            maximum=1.0,
        ),
    )
