from __future__ import annotations

from pathlib import Path

from imagent_bench.config import validate_result_schema
from imagent_bench.runner import run


def test_runner_writes_valid_results(tmp_path: Path) -> None:
    result = run(
        Path("configs/local-smoke.yaml").resolve(),
        "tests/fixtures/echo_agent",
        tmp_path,
    )

    assert validate_result_schema(result) == []
    assert result["metrics"]["failed_generations"] == 0
    assert result["metrics"]["total_cases"] == 6
    assert result["metrics"]["pass_rate"] == 1.0
    assert "cost_usd" in result["metrics"]
    assert result["metrics"]["judge_cost_usd"] == 0.0
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "summary.md").exists()


def test_runner_raises_for_missing_public_input_file(tmp_path: Path) -> None:
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "suite.yaml").write_text(
        """
id: broken_suite
version: 1
tasks:
  broken: cases/broken.jsonl
""",
        encoding="utf-8",
    )
    cases_dir = suite_dir / "cases"
    cases_dir.mkdir()
    (cases_dir / "broken.jsonl").write_text(
        """
{"id":"broken-asset-001","capability":"plan","prompt":"Create a card.","assets":["missing.txt"],"allowed_tools":[],"expected":{"checks":[{"type":"always"}]}}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
suite:
  path: suite/suite.yaml
runtime:
  seeds: [1001]
metrics:
  primary: ia_score
""",
        encoding="utf-8",
    )

    try:
        run(config_path, "tests/fixtures/echo_agent", tmp_path / "out")
    except FileNotFoundError as exc:
        assert "missing.txt" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError for missing public input file")


def _write_agent_with_output_paths(tmp_path: Path, image_path: str, trace_path: str) -> Path:
    agent_dir = tmp_path / "path_agent"
    package_dir = agent_dir / "path_agent"
    package_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "id: path-agent\nentrypoint: path_agent.agent:Agent\n",
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "agent.py").write_text(
        f"""
from pathlib import Path


class Agent:
    def setup(self, config, workdir):
        pass

    def generate(self, case, output_dir):
        output_dir = Path(output_dir)
        trace = output_dir / "safe-trace.json"
        image = output_dir / "safe-image.svg"
        trace.write_text('{{"planning": {{"missing_context": []}}, "grounding": {{}}, "final_generation_context": {{"prompt": "ok"}}, "feedback": []}}', encoding="utf-8")
        image.write_text("<svg/>", encoding="utf-8")
        return {{
            "image_path": {image_path!r},
            "trace_path": {trace_path!r},
            "metadata": {{}},
        }}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return agent_dir


def test_runner_rejects_output_paths_outside_output_dir(tmp_path: Path) -> None:
    outside_image = tmp_path / "outside.svg"
    outside_trace = tmp_path / "outside.json"
    outside_image.write_text("<svg/>", encoding="utf-8")
    outside_trace.write_text("{}", encoding="utf-8")
    agent_dir = _write_agent_with_output_paths(tmp_path, str(outside_image), str(outside_trace))

    result = run(Path("configs/local-smoke.yaml").resolve(), str(agent_dir), tmp_path / "out")

    assert result["metrics"]["failed_generations"] == 6
    assert result["cases"][0]["output"]["image_path"] == ""
    assert "must stay within output dir" in result["cases"][0]["output"]["metadata"]["error"]


def test_runner_rejects_relative_output_path_escape(tmp_path: Path) -> None:
    agent_dir = _write_agent_with_output_paths(tmp_path, "../outside.svg", "../outside.json")

    result = run(Path("configs/local-smoke.yaml").resolve(), str(agent_dir), tmp_path / "out")

    assert result["metrics"]["failed_generations"] == 6
    assert result["cases"][0]["output"]["trace_path"] == ""
    assert "must stay within output dir" in result["cases"][0]["output"]["metadata"]["error"]
