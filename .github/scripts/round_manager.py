from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LABELS = {
    "pr-rules-pass": "2da44e",
    "invalid-pr": "d73a4a",
    "duplicate-pr": "d73a4a",
    "round-benchmark-running": "fbca04",
    "round-eligible": "2da44e",
    "round-winner": "8250df",
    "below-threshold": "d73a4a",
    "benchmark-fail": "d73a4a",
    "needs-rebase": "fbca04",
}

CANDIDATE_AGENT_PATH = "agent/agent.py"
BOT_MANAGED_WINNER_PATH = Path("agent/last_winner.py")
WINNERS_DIR = Path("winners")
TRUSTED_AUTHOR_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


@dataclass
class CandidateResult:
    pr: dict[str, Any]
    report: dict[str, Any]
    score: float
    delta: float
    head_sha: str


class GitHub:
    def __init__(self, token: str, repository: str) -> None:
        self.token = token
        self.repository = repository
        self.api_root = "https://api.github.com"

    def request(self, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
        body = None if data is None else json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            self.api_root + path,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {payload}") from exc
        return json.loads(payload) if payload else None

    def paginate(self, path: str) -> list[Any]:
        items: list[Any] = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            batch = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not batch:
                return items
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def ensure_labels(self) -> None:
        for name, color in LABELS.items():
            try:
                self.request("GET", f"/repos/{self.repository}/labels/{name}")
            except RuntimeError as exc:
                if " 404 " not in str(exc):
                    raise
                self.request("POST", f"/repos/{self.repository}/labels", {"name": name, "color": color})

    def add_labels(self, number: int, labels: list[str]) -> None:
        if labels:
            self.request("POST", f"/repos/{self.repository}/issues/{number}/labels", {"labels": labels})

    def remove_label(self, number: int, label: str) -> None:
        try:
            self.request("DELETE", f"/repos/{self.repository}/issues/{number}/labels/{label}")
        except RuntimeError as exc:
            if " 404 " not in str(exc):
                raise

    def comment(self, number: int, body: str) -> None:
        self.request("POST", f"/repos/{self.repository}/issues/{number}/comments", {"body": body})

    def issue_labels(self, number: int) -> set[str]:
        labels = self.paginate(f"/repos/{self.repository}/issues/{number}/labels")
        return {str(label["name"]) for label in labels if isinstance(label, dict) and label.get("name")}

    def close_pr(self, number: int) -> None:
        self.request("PATCH", f"/repos/{self.repository}/pulls/{number}", {"state": "closed"})

    def pr_files(self, number: int) -> list[str]:
        files = self.paginate(f"/repos/{self.repository}/pulls/{number}/files")
        return [str(item["filename"]) for item in files if isinstance(item, dict) and item.get("filename")]

    def merge_pr(self, number: int, commit_title: str) -> dict[str, Any]:
        result = self.request(
            "PUT",
            f"/repos/{self.repository}/pulls/{number}/merge",
            {"merge_method": "squash", "commit_title": commit_title},
        )
        return result if isinstance(result, dict) else {}

    def set_variable(self, name: str, value: str) -> None:
        payload = {"name": name, "value": value}
        try:
            self.request("PATCH", f"/repos/{self.repository}/actions/variables/{name}", {"value": value})
        except RuntimeError as exc:
            if " 404 " not in str(exc):
                raise
            self.request("POST", f"/repos/{self.repository}/actions/variables", payload)


def main() -> int:
    repository = required_env("GITHUB_REPOSITORY")
    token = required_env("GITHUB_TOKEN")
    github = GitHub(token, repository)
    github.ensure_labels()

    round_id = os.environ.get("IMAGENT_ROUND_ID") or current_round_id()
    baseline_score = env_float("IMAGENT_BASELINE_SCORE", 0.0)
    threshold = env_float("IMAGENT_ROUND_THRESHOLD", 0.0)
    benchmark_config = os.environ.get(
        "IMAGENT_BENCH_CONFIG",
        "_imagent-bench/configs/openrouter-vision-benchmark.json",
    )
    base_ref = git_output("rev-parse", "HEAD")

    print(f"round_id={round_id}")
    print(f"baseline_score={baseline_score}")
    print(f"threshold={threshold}")

    prs = open_same_repo_prs(github, repository)
    prs = enforce_one_open_pr_per_contributor(github, prs, round_id)
    if not prs:
        print("No valid PRs to evaluate.")
        return 0

    results: list[CandidateResult] = []
    for pr in prs:
        number = int(pr["number"])
        file_failures = candidate_file_failures(github.pr_files(number))
        if file_failures:
            close_with_reason(
                github,
                pr,
                round_id,
                "PR file scope is not a valid candidate submission",
                extra="\n".join(f"- {failure}" for failure in file_failures),
                labels=["invalid-pr"],
            )
            continue
        github.add_labels(number, ["round-benchmark-running"])
        clear_round_labels(github, number)
        try:
            result = evaluate_pr(pr, baseline_score, benchmark_config)
        except Exception as exc:  # noqa: BLE001
            close_with_reason(
                github,
                pr,
                round_id,
                "benchmark failed before producing a valid report",
                extra=f"Error: `{exc}`",
                labels=["benchmark-fail"],
            )
            continue
        finally:
            checkout_ref(base_ref)

        if not report_passes_quality_policy(result.report):
            close_with_reason(
                github,
                pr,
                round_id,
                "benchmark policy did not pass",
                extra=policy_failure_summary(result),
                labels=["benchmark-fail"],
            )
            continue
        if result.delta <= threshold:
            close_with_reason(
                github,
                pr,
                round_id,
                "score improvement did not exceed the round threshold",
                extra=summary_line(result, threshold),
                labels=["below-threshold"],
            )
            continue
        github.remove_label(number, "round-benchmark-running")
        github.add_labels(number, ["round-eligible"])
        github.comment(
            number,
            "\n".join(
                [
                    f"Round `{round_id}` benchmark passed the threshold.",
                    "",
                    summary_line(result, threshold),
                    "",
                    "This PR remains eligible until the round winner is selected.",
                ]
            ),
        )
        results.append(result)

    if not results:
        print("No PR exceeded the round threshold.")
        return 0

    winner = max(results, key=lambda item: (item.score, item.delta, -int(item.pr["number"])))
    promote_winner(github, winner, round_id, base_ref)

    for result in results:
        number = int(result.pr["number"])
        github.remove_label(number, "round-benchmark-running")
        if number == int(winner.pr["number"]):
            github.remove_label(number, "round-eligible")
            github.add_labels(number, ["round-winner"])
            continue
        github.remove_label(number, "round-eligible")
        github.add_labels(number, ["needs-rebase"])
        github.comment(
            number,
            "\n".join(
                [
                    f"Round `{round_id}` completed. This PR passed the threshold but was not the highest score.",
                    "",
                    summary_line(result, threshold),
                    "",
                    "It remains open, but it is labeled `needs-rebase` because the winning agent was merged.",
                    "Rebase onto `main` and push an update to enter a future round.",
                ]
            ),
        )
    return 0


def current_round_id(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    slot = 0 if value.hour < 12 else 1
    return f"{value:%Y%m%d}-{slot}"


def open_same_repo_prs(github: GitHub, repository: str) -> list[dict[str, Any]]:
    prs = github.paginate(f"/repos/{repository}/pulls?state=open&sort=created&direction=asc")
    result: list[dict[str, Any]] = []
    for pr in prs:
        labels = {label["name"] for label in pr.get("labels", []) if isinstance(label, dict) and label.get("name")}
        if not labels:
            labels = github.issue_labels(int(pr["number"]))
        if pr.get("draft"):
            continue
        if pr.get("head", {}).get("repo", {}).get("full_name") != repository:
            continue
        if "pr-rules-pass" not in labels:
            continue
        if "needs-rebase" in labels:
            continue
        if is_maintainer_pr(pr, repository):
            continue
        result.append(pr)
    return result


def enforce_one_open_pr_per_contributor(
    github: GitHub,
    prs: list[dict[str, Any]],
    round_id: str,
) -> list[dict[str, Any]]:
    by_author: dict[str, list[dict[str, Any]]] = {}
    for pr in prs:
        by_author.setdefault(str(pr["user"]["login"]), []).append(pr)

    kept: list[dict[str, Any]] = []
    for author, author_prs in by_author.items():
        ordered = sorted(author_prs, key=lambda item: (item["created_at"], int(item["number"])))
        kept.append(ordered[0])
        for duplicate in ordered[1:]:
            close_with_reason(
                github,
                duplicate,
                round_id,
                f"only one open PR per contributor is allowed per round; keeping #{ordered[0]['number']} for `{author}`",
                labels=["duplicate-pr"],
            )
    return sorted(kept, key=lambda item: int(item["number"]))


def evaluate_pr(pr: dict[str, Any], baseline_score: float, benchmark_config: str) -> CandidateResult:
    number = int(pr["number"])
    head_sha = str(pr["head"]["sha"])
    output_dir = (Path("round-output") / f"pr-{number}").resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    benchmark_config_path = Path(benchmark_config).resolve()
    benchmark_project = Path(os.environ.get("IMAGENT_BENCH_PROJECT", "_imagent-bench")).resolve()

    with tempfile.TemporaryDirectory(prefix=f"imagent-pr-{number}-") as tempdir:
        candidate_dir = Path(tempdir) / "candidate"
        venv_dir = Path(tempdir) / ".venv"
        run(["git", "worktree", "add", "--detach", str(candidate_dir), head_sha])
        try:
            run([sys.executable, "-m", "venv", str(venv_dir)])
            venv_python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            run([venv_python, "-m", "pip", "install", "-U", "pip"])
            run([venv_python, "-m", "pip", "install", "-e", str(benchmark_project)])
            run([venv_python, "-m", "pip", "install", "-e", ".[dev]"], cwd=candidate_dir)
            run([venv_python, "-m", "pytest"], cwd=candidate_dir)
            run([venv_python, "-m", "compileall", "agent", "tests"], cwd=candidate_dir)
            if (candidate_dir / WINNERS_DIR).exists():
                run([venv_python, "-m", "compileall", str(WINNERS_DIR)], cwd=candidate_dir)
            command = [
                venv_python,
                "-m",
                "imagent_bench",
                "run",
                "--repository",
                str(candidate_dir),
                "--config",
                str(benchmark_config_path),
                "--output-dir",
                str(output_dir),
                "--baseline-score",
                str(baseline_score),
            ]
            baseline_commit = os.environ.get("IMAGENT_BASELINE_COMMIT", "").strip()
            if baseline_commit:
                command.extend(["--baseline-commit", baseline_commit])
            completed = subprocess.run(
                [str(part) for part in command],
                text=True,
                cwd=candidate_dir,
                env=_candidate_subprocess_env(os.environ),
            )
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(candidate_dir)], check=False)

    report_path = output_dir / "benchmark-report.json"
    if not report_path.exists():
        raise RuntimeError(f"benchmark command exited {completed.returncode} and did not write {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    score = float(report.get("overall_score") or 0.0)
    ranking = report.get("ranking") if isinstance(report.get("ranking"), dict) else {}
    raw_delta = ranking.get("delta")
    delta = float(raw_delta) if raw_delta is not None else score - baseline_score
    return CandidateResult(pr=pr, report=report, score=score, delta=delta, head_sha=head_sha)


def _candidate_subprocess_env(base_env: dict) -> dict:
    """Return a copy of base_env safe to expose to untrusted candidate code.

    The candidate benchmark subprocess executes contributor-supplied
    ``agent/agent.py``, so secrets that only the orchestrator needs must not be
    inherited. Strip the GitHub tokens to avoid exfiltration, but keep
    ``OPENROUTER_API_KEY`` because the candidate needs it to generate images.
    """
    env = dict(base_env)
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        env.pop(name, None)
    return env


def candidate_file_failures(filenames: list[str]) -> list[str]:
    failures: list[str] = []
    if CANDIDATE_AGENT_PATH not in filenames:
        failures.append(f"candidate PR must change `{CANDIDATE_AGENT_PATH}`")
    extra_files = [name for name in filenames if name != CANDIDATE_AGENT_PATH]
    if extra_files:
        failures.append(
            "contributor candidate PRs may only change `agent/agent.py`; remove: "
            + ", ".join(f"`{name}`" for name in extra_files)
        )
    return failures


def report_passes_quality_policy(report: dict[str, Any]) -> bool:
    if report.get("status") == "pass":
        return True
    reasons = policy_reasons(report)
    return bool(reasons) and all(is_merge_improvement_reason(reason) for reason in reasons)


def policy_failure_summary(result: CandidateResult) -> str:
    reasons = policy_reasons(result.report)
    if not reasons:
        return summary_line(result)
    lines = [summary_line(result), "", "Policy failures:"]
    lines.extend(f"- {reason}" for reason in reasons)
    return "\n".join(lines)


def policy_reasons(report: dict[str, Any]) -> list[str]:
    policy = report.get("policy") if isinstance(report.get("policy"), dict) else {}
    reasons = policy.get("reasons") if isinstance(policy, dict) else []
    return [str(reason) for reason in reasons if str(reason).strip()] if isinstance(reasons, list) else []


def is_merge_improvement_reason(reason: str) -> bool:
    # NOTE: This is intentionally coupled to imagent-bench's human-readable policy
    # reason strings (e.g. "score improvement 0.50 is below required 1.00"). A
    # structured status field emitted by the benchmark would be more robust than
    # matching English text; until that exists, guard against non-string input.
    if not isinstance(reason, str):
        return False
    return reason.startswith("score improvement ") and " is below required " in reason


def promote_winner(github: GitHub, winner: CandidateResult, round_id: str, base_ref: str) -> None:
    pr = winner.pr
    number = int(pr["number"])
    head_ref = str(pr["head"]["ref"])
    head_sha = str(pr["head"]["sha"])
    base_branch = str(pr.get("base", {}).get("ref") or "main")
    archive_name = archive_filename(round_id, number, head_sha)

    run(["git", "config", "user.name", "imagent-round-bot"])
    run(["git", "config", "user.email", "actions@github.com"])
    checkout_ref(head_sha)
    winner_code = Path(CANDIDATE_AGENT_PATH).read_text(encoding="utf-8")
    candidate_paths = changed_paths_between(base_ref, head_sha)
    merge_base_into_candidate(base_ref)
    restore_changed_paths_from_ref(base_ref, candidate_paths)
    BOT_MANAGED_WINNER_PATH.write_text(winner_code, encoding="utf-8")
    WINNERS_DIR.mkdir(exist_ok=True)
    archive_path = WINNERS_DIR / archive_name
    archive_path.write_text(winner_code, encoding="utf-8")

    stage_paths([*candidate_paths, str(BOT_MANAGED_WINNER_PATH), str(archive_path)])
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        run(["git", "commit", "-m", f"chore: promote round {round_id} winner"])
        run(["git", "push", "origin", f"HEAD:refs/heads/{head_ref}"])

    github.comment(
        number,
        "\n".join(
            [
                f"Round `{round_id}` winner selected.",
                "",
                summary_line(winner),
                "",
                f"Promoted into `agent/last_winner.py` and `winners/{archive_name}`.",
            ]
        ),
    )
    merge_result = github.merge_pr(number, f"chore: promote round {round_id} winner")
    merged_sha = str(merge_result.get("sha") or "").strip()
    if not merged_sha:
        run(["git", "fetch", "origin", base_branch])
        merged_sha = git_output("rev-parse", f"origin/{base_branch}")
    github.set_variable("IMAGENT_BASELINE_SCORE", str(winner.score))
    github.set_variable("IMAGENT_BASELINE_COMMIT", merged_sha)
    github.set_variable("IMAGENT_LAST_ROUND_ID", round_id)
    github.set_variable("IMAGENT_LAST_WINNER_PR", str(number))


def close_with_reason(
    github: GitHub,
    pr: dict[str, Any],
    round_id: str,
    reason: str,
    *,
    extra: str = "",
    labels: list[str] | None = None,
) -> None:
    number = int(pr["number"])
    for label in ["round-benchmark-running", "round-eligible", "round-winner"]:
        github.remove_label(number, label)
    github.add_labels(number, labels or [])
    body = [f"Round `{round_id}` closed this PR: {reason}."]
    if extra:
        body.extend(["", extra])
    github.comment(number, "\n".join(body))
    github.close_pr(number)


def clear_round_labels(github: GitHub, number: int) -> None:
    for label in ["round-eligible", "round-winner", "below-threshold", "benchmark-fail", "duplicate-pr"]:
        github.remove_label(number, label)


def summary_line(result: CandidateResult, threshold: float | None = None) -> str:
    baseline = result.report.get("ranking", {}).get("baseline_score")
    parts = [
        f"Score: `{result.score:.6f}`",
        f"baseline: `{baseline}`",
        f"delta: `{result.delta:.6f}`",
    ]
    if threshold is not None:
        parts.append(f"threshold: `{threshold:.6f}`")
    return ", ".join(parts) + "."


def archive_filename(round_id: str, pr_number: int, sha: str) -> str:
    safe_round = re.sub(r"[^A-Za-z0-9_]+", "_", round_id).strip("_")
    return f"{safe_round}_pr_{pr_number}_{sha[:12]}.py"


def changed_paths_between(base_ref: str, head_sha: str) -> list[str]:
    output = git_output("diff", "--name-only", f"{base_ref}...{head_sha}")
    return [line for line in output.splitlines() if line.strip()]


def merge_base_into_candidate(base_ref: str) -> None:
    run(["git", "merge", "--no-edit", "-X", "theirs", base_ref])


def restore_changed_paths_from_ref(ref: str, paths: list[str]) -> None:
    for path in sorted(set(paths)):
        restore_path_from_ref(ref, path)


def stage_paths(paths: list[str]) -> None:
    unique_paths = sorted(set(paths))
    if unique_paths:
        run(["git", "add", "--all", "--", *unique_paths])


def restore_path_from_ref(ref: str, path: str) -> None:
    target = Path(path)
    if path_exists_in_ref(ref, path):
        target.parent.mkdir(parents=True, exist_ok=True)
        content = subprocess.check_output(["git", "show", f"{ref}:{path}"])
        target.write_bytes(content)
        return
    remove_worktree_path(target)


def path_exists_in_ref(ref: str, path: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{ref}:{path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def remove_worktree_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def checkout_ref(ref: str) -> None:
    run(["git", "checkout", "--force", ref])


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def is_maintainer_pr(pr: dict[str, Any], repository: str) -> bool:
    owner = repository.split("/", 1)[0]
    author = str(pr.get("user", {}).get("login", ""))
    association = str(pr.get("author_association", ""))
    return author == owner or association in TRUSTED_AUTHOR_ASSOCIATIONS


def run(command: list[Any], *, cwd: Path | None = None) -> None:
    printable = [str(part) for part in command]
    cwd_text = f" (cwd={cwd})" if cwd else ""
    print("+ " + " ".join(printable) + cwd_text, flush=True)
    subprocess.run(printable, cwd=cwd, check=True)


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
