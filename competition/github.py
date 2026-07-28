from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .lifecycle import Action, Submission

# The only part of the bot that touches GitHub.
#
# `dry_run` is not a testing convenience. This client merges and closes pull
# requests, so being able to print exactly what it would do — in CI, on a real
# queue, without doing it — is how a maintainer stays able to audit an automated
# competition.

API_ROOT = "https://api.github.com"


class GitHubError(RuntimeError):
    """Raised when the GitHub API refuses a request."""


class GitHubClient:
    def __init__(
        self,
        repository: str,
        token: str,
        *,
        dry_run: bool = False,
        api_root: str = API_ROOT,
        opener=urllib.request.urlopen,
        timeout_seconds: int = 30,
    ) -> None:
        if "/" not in repository:
            raise ValueError("repository must be 'owner/name'")
        if not token and not dry_run:
            raise ValueError("a GitHub token is required unless running dry")
        self.repository = repository
        self._token = token
        self.dry_run = dry_run
        self.api_root = api_root.rstrip("/")
        self._opener = opener
        self.timeout_seconds = timeout_seconds
        self.performed: list[Action] = []
        # Stand-in queue for an offline dry run, so a plan can be previewed
        # against a hypothetical state.
        self.fixtures: list[Submission] = []

    # --- reads ------------------------------------------------------------

    def list_submissions(self, *, label: str = "") -> list[Submission]:
        # A dry run with no token must be fully offline. Reads are harmless, but
        # needing credentials and a network to preview a plan defeats the point
        # of being able to preview it.
        if self.dry_run and not self._token:
            return list(self.fixtures)

        query = {"state": "open", "per_page": "100"}
        if label:
            query["labels"] = label
        payload = self._request("GET", f"/repos/{self.repository}/issues?{urllib.parse.urlencode(query)}")

        submissions: list[Submission] = []
        for item in payload if isinstance(payload, list) else []:
            # /issues returns issues and pull requests; only the latter carry a
            # `pull_request` key, and only they can be merged.
            if not isinstance(item, dict) or "pull_request" not in item:
                continue
            submissions.append(
                Submission(
                    number=int(item["number"]),
                    author=str((item.get("user") or {}).get("login", "")),
                    labels=tuple(
                        str(entry.get("name", "")) for entry in item.get("labels", []) if isinstance(entry, dict)
                    ),
                    created_at=str(item.get("created_at", "")),
                )
            )
        return submissions

    # --- writes -----------------------------------------------------------

    def apply(self, actions: tuple[Action, ...] | list[Action]) -> list[str]:
        """Perform a plan in order, returning a human-readable log.

        Ordering is load-bearing: a plan removes `challenger:running` before it
        merges, so a crash midway leaves a pull request in a state a human can
        read rather than one that claims a duel is still in flight.
        """
        performed: list[str] = []
        for action in actions:
            self.performed.append(action)
            performed.append(("DRY " if self.dry_run else "") + action.describe())
            if self.dry_run:
                continue
            self._perform(action)
        return performed

    def _perform(self, action: Action) -> None:
        number = action.pull_request
        if action.kind == "label":
            self._request(
                "POST", f"/repos/{self.repository}/issues/{number}/labels", {"labels": [action.value]}
            )
        elif action.kind == "unlabel":
            try:
                self._request(
                    "DELETE",
                    f"/repos/{self.repository}/issues/{number}/labels/{urllib.parse.quote(action.value)}",
                )
            except GitHubError as error:
                # Removing a label that is not there is the desired end state, so
                # it must not abort the rest of the plan.
                if "404" not in str(error):
                    raise
        elif action.kind == "comment":
            self._request(
                "POST", f"/repos/{self.repository}/issues/{number}/comments", {"body": action.value}
            )
        elif action.kind == "close":
            self._request("PATCH", f"/repos/{self.repository}/issues/{number}", {"state": "closed"})
        elif action.kind == "merge":
            self._request(
                "PUT",
                f"/repos/{self.repository}/pulls/{number}/merge",
                {"merge_method": "squash"},
            )
        else:  # pragma: no cover - the dataclass constrains this
            raise GitHubError(f"unknown action: {action.kind}")

    # --- transport --------------------------------------------------------

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        request = urllib.request.Request(
            f"{self.api_root}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:300]
            raise GitHubError(f"{method} {path} -> HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise GitHubError(f"{method} {path} failed: {error}") from error
        except json.JSONDecodeError as error:
            raise GitHubError(f"{method} {path} returned malformed JSON") from error
