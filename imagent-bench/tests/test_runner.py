from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from imagent_bench.runner import BenchmarkRunError, _case_status, _normalize_repository_identifier, run


def _imagent_repository() -> Path:
    workspace = Path(__file__).resolve().parents[2]
    sibling_repo = workspace / "imagent"
    if (sibling_repo / "agent" / "agent.py").exists():
        return sibling_repo
    if (workspace / "agent" / "agent.py").exists():
        return workspace
    return sibling_repo


@pytest.fixture
def openrouter_http_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_urlopen(request: Any, *args: Any, **kwargs: Any) -> "_FakeResponse":
        url = str(getattr(request, "full_url", ""))
        if url.endswith("/images"):
            return _FakeResponse(
                {
                    "created": 1783296000,
                    "data": [
                        {
                            "b64_json": base64.b64encode(b"fake-png-bytes").decode("ascii"),
                            "media_type": "image/png",
                        }
                    ],
                    "usage": {"cost": 0.001},
                }
            )
        return _FakeResponse(
            {
                "model": "google/gemini-2.5-flash",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "scores": {
                                        "prompt_alignment": 100,
                                        "visual_quality": 100,
                                        "aesthetics": 100,
                                        "text_accuracy": 100,
                                        "layout_and_composition": 100,
                                        "realism": 100,
                                    },
                                    "overall_score": 100,
                                    "rationale": "offline OpenRouter fixture",
                                }
                            )
                        }
                    }
                ],
                "usage": {"cost": 0.001},
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)


def test_runner_executes_local_imagent_and_writes_report(openrouter_http_mock: None, tmp_path: Path) -> None:
    repository = _imagent_repository()
    config = Path(__file__).resolve().parents[1] / "configs" / "official.json"

    result = run(repository=repository, config=config, output_dir=tmp_path)

    report_path = tmp_path / "benchmark-report.json"
    summary_path = tmp_path / "benchmark-summary.md"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert result.status == "pass"
    assert result.overall_score == 100.0
    assert report["schema_version"] == "1.0"
    assert report["repository"] == "imagent-ai/imagent"
    assert report["metrics"]["case_count"] == 5
    assert report["policy"]["passed"] is True
    assert report["ranking"]["baseline_score"] is None
    assert summary_path.exists()


def test_runner_marks_merge_eligible_when_score_improves_baseline(
    openrouter_http_mock: None, tmp_path: Path
) -> None:
    repository = _imagent_repository()
    config = Path(__file__).resolve().parents[1] / "configs" / "official.json"

    result = run(
        repository=repository,
        config=config,
        output_dir=tmp_path,
        baseline_score=95.0,
        baseline_commit="baseline123",
    )

    report = json.loads((tmp_path / "benchmark-report.json").read_text(encoding="utf-8"))

    assert result.status == "pass"
    assert report["ranking"]["baseline_score"] == 95.0
    assert report["ranking"]["baseline_commit"] == "baseline123"
    assert report["ranking"]["delta"] == 5.0
    assert report["ranking"]["label"] == "improvement-strong"
    assert report["ranking"]["merge_eligible"] is True


def test_runner_marks_judged_case_fail_when_score_is_below_case_minimum() -> None:
    status = _case_status(
        checks=[],
        judge_result={"overall_score": 74.9},
        expected={"minimum_score": 75.0},
    )

    assert status == "fail"


def test_runner_reads_pull_request_metadata_from_github_event(
    monkeypatch, openrouter_http_mock: None, tmp_path: Path  # noqa: ANN001
) -> None:
    repository = _imagent_repository()
    config = Path(__file__).resolve().parents[1] / "configs" / "official.json"
    event_path = tmp_path / "github-event.json"
    event_path.write_text(
        json.dumps(
            {
                "number": 77,
                "pull_request": {
                    "number": 77,
                    "title": "feat: benchmark metadata",
                    "state": "open",
                    "html_url": "https://github.com/imagent-ai/imagent/pull/77",
                    "merged_at": None,
                    "closed_at": None,
                    "user": {
                        "login": "mitchelltop",
                        "avatar_url": "https://avatars.example.test/mitchelltop",
                        "html_url": "https://github.com/mitchelltop",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    result = run(repository=repository, config=config, output_dir=tmp_path / "report")
    report = json.loads((tmp_path / "report" / "benchmark-report.json").read_text(encoding="utf-8"))

    assert result.pull_request == {
        "number": 77,
        "title": "feat: benchmark metadata",
        "state": "open",
        "html_url": "https://github.com/imagent-ai/imagent/pull/77",
        "merged_at": None,
        "closed_at": None,
    }
    assert result.contributor == {
        "login": "mitchelltop",
        "name": None,
        "avatar_url": "https://avatars.example.test/mitchelltop",
        "html_url": "https://github.com/mitchelltop",
    }
    assert report["pull_request"]["number"] == 77
    assert report["contributor"]["login"] == "mitchelltop"


def test_normalize_repository_identifier_handles_common_github_urls() -> None:
    assert _normalize_repository_identifier("https://github.com/imagent-ai/imagent.git") == "imagent-ai/imagent"
    assert _normalize_repository_identifier("git@github.com:imagent-ai/imagent-bench.git") == "imagent-ai/imagent-bench"


def test_runner_rejects_local_repository_commit_mismatch(tmp_path: Path) -> None:
    repository = _imagent_repository()
    config = Path(__file__).resolve().parents[1] / "configs" / "official.json"

    with pytest.raises(BenchmarkRunError, match="local repository HEAD does not match --commit"):
        run(repository=repository, commit="deadbeef", config=config, output_dir=tmp_path)


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")
