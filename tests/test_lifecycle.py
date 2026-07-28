from __future__ import annotations

import json
import urllib.error

import pytest

from competition.github import GitHubClient, GitHubError
from competition.lifecycle import (
    DEFEATED,
    INVALID,
    KING,
    PAST_KING,
    PENDING,
    RUNNING,
    Action,
    Submission,
    plan_outcome,
    plan_screening,
    plan_start,
)

MATCH = {
    "wins": 5,
    "losses": 2,
    "ties": 0,
    "margin": 3,
    "reasons": [],
    "king_mean_fact": 0.88,
    "challenger_mean_fact": 0.91,
}


def _kinds(actions) -> list[tuple[str, int, str]]:
    return [(action.kind, action.pull_request, action.value) for action in actions]


# --- screening --------------------------------------------------------------


def test_a_clean_submission_is_queued() -> None:
    actions = plan_screening(Submission(7, "alice"), reasons=[], open_submissions=[])

    assert ("label", 7, PENDING) in _kinds(actions)
    assert not any(action.kind == "close" for action in actions)


def test_a_rejected_submission_is_labelled_and_closed() -> None:
    actions = plan_screening(
        Submission(7, "alice"), reasons=["bundle is missing agent.yaml"], open_submissions=[]
    )

    kinds = _kinds(actions)
    assert ("label", 7, INVALID) in kinds
    assert ("close", 7, "") in kinds
    comment = next(action for action in actions if action.kind == "comment")
    assert "missing agent.yaml" in comment.value
    assert "before any credits were spent" in comment.value


def test_one_open_submission_per_contributor() -> None:
    # Without this a single author floods the queue, and since every challenge
    # costs money the flooding is expensive as well as unfair.
    actions = plan_screening(
        Submission(9, "alice"),
        reasons=[],
        open_submissions=[Submission(4, "alice"), Submission(5, "bob")],
    )

    kinds = _kinds(actions)
    assert ("label", 9, INVALID) in kinds
    comment = next(action for action in actions if action.kind == "comment")
    assert "#4" in comment.value
    assert "#5" not in comment.value


def test_stale_labels_are_cleared_on_rescreening() -> None:
    actions = plan_screening(
        Submission(7, "alice", labels=(INVALID,)), reasons=[], open_submissions=[]
    )

    kinds = _kinds(actions)
    assert ("unlabel", 7, INVALID) in kinds
    assert kinds.index(("unlabel", 7, INVALID)) < kinds.index(("label", 7, PENDING))


# --- the queue --------------------------------------------------------------


def test_the_oldest_pending_challenger_goes_first() -> None:
    actions = plan_start(
        pending=[
            Submission(9, "carol", created_at="2026-07-03T00:00:00Z"),
            Submission(4, "alice", created_at="2026-07-01T00:00:00Z"),
            Submission(6, "bob", created_at="2026-07-02T00:00:00Z"),
        ],
        running=[],
    )

    assert ("label", 4, RUNNING) in _kinds(actions)


def test_only_one_duel_runs_at_a_time() -> None:
    # Two concurrent duels could both promote, and one crown would silently
    # overwrite the other.
    actions = plan_start(
        pending=[Submission(4, "alice")], running=[Submission(2, "bob", labels=(RUNNING,))]
    )

    assert actions == ()


def test_an_empty_queue_does_nothing() -> None:
    assert plan_start(pending=[], running=[]) == ()


# --- outcomes ---------------------------------------------------------------


def test_a_promotion_crowns_and_merges() -> None:
    actions = plan_outcome(
        Submission(7, "alice", labels=(RUNNING,)),
        promoted=True,
        match=MATCH,
        challenge_id="c1",
        king_submission=Submission(3, "bob", labels=(KING,)),
    )

    kinds = _kinds(actions)
    assert ("label", 7, KING) in kinds
    assert ("merge", 7, "") in kinds
    assert ("label", 3, PAST_KING) in kinds
    assert ("unlabel", 3, KING) in kinds


def test_the_running_label_is_removed_before_the_merge() -> None:
    # A crash midway must leave a pull request in a state a human can read,
    # not one still claiming a duel is in flight.
    actions = plan_outcome(
        Submission(7, "alice", labels=(RUNNING,)), promoted=True, match=MATCH, challenge_id="c1"
    )
    kinds = _kinds(actions)

    assert kinds.index(("unlabel", 7, RUNNING)) < kinds.index(("merge", 7, ""))


def test_the_dethroned_king_is_told_it_is_requeued() -> None:
    actions = plan_outcome(
        Submission(7, "alice", labels=(RUNNING,)),
        promoted=True,
        match=MATCH,
        challenge_id="c1",
        king_submission=Submission(3, "bob", labels=(KING,)),
    )

    comment = next(
        action for action in actions if action.kind == "comment" and action.pull_request == 3
    )
    assert "rematch" in comment.value
    assert "#7" in comment.value


def test_a_defeat_closes_the_pull_request() -> None:
    losing = {**MATCH, "wins": 2, "losses": 3, "margin": -1, "reasons": ["net wins -1 is below the required margin of 2"]}

    actions = plan_outcome(
        Submission(7, "alice", labels=(RUNNING,)), promoted=False, match=losing, challenge_id="c1"
    )

    kinds = _kinds(actions)
    assert ("label", 7, DEFEATED) in kinds
    assert ("close", 7, "") in kinds
    assert ("merge", 7, "") not in kinds
    comment = next(action for action in actions if action.kind == "comment")
    assert "below the required margin" in comment.value


def test_an_aborted_challenge_is_not_a_defeat() -> None:
    # Infrastructure failing must never be recorded as an agent losing.
    actions = plan_outcome(
        Submission(7, "alice", labels=(RUNNING,)),
        promoted=False,
        match=MATCH,
        challenge_id="c1",
        aborted="room unreachable for chal-1",
    )

    kinds = _kinds(actions)
    assert ("label", 7, PENDING) in kinds
    assert ("close", 7, "") not in kinds
    assert (DEFEATED not in [value for _, _, value in kinds])
    comment = next(action for action in actions if action.kind == "comment")
    assert "not a defeat" in comment.value


def test_the_result_comment_shows_the_tally_and_the_rules() -> None:
    actions = plan_outcome(
        Submission(7, "alice"), promoted=True, match=MATCH, challenge_id="c1"
    )
    comment = next(action for action in actions if action.kind == "comment").value

    assert "new king" in comment
    assert "| Won | 5 |" in comment
    assert "+3" in comment
    assert "Ties count for the king" in comment


# --- the client -------------------------------------------------------------


class _Response:
    def __init__(self, payload) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def _client(payload=None, *, capture=None, dry_run=False, raiser=None):
    def opener(request, timeout):
        if capture is not None:
            capture.append((request.get_method(), request.full_url, request.data))
        if raiser is not None:
            raise raiser
        return _Response(payload if payload is not None else {})

    return GitHubClient("owner/repo", "token", dry_run=dry_run, opener=opener)


def test_a_dry_run_performs_nothing_but_reports_everything() -> None:
    captured: list = []
    client = _client(capture=captured, dry_run=True)

    log = client.apply(
        [Action("label", 7, KING), Action("merge", 7), Action("close", 3)]
    )

    assert captured == []  # nothing left the process
    assert all(entry.startswith("DRY ") for entry in log)
    assert client.performed[1].kind == "merge"


def test_actions_become_the_right_api_calls() -> None:
    captured: list = []
    _client(capture=captured).apply(
        [Action("label", 7, PENDING), Action("comment", 7, "hi"), Action("merge", 7)]
    )

    methods = [(method, url.rsplit("/repos/owner/repo", 1)[-1]) for method, url, _ in captured]
    assert methods == [
        ("POST", "/issues/7/labels"),
        ("POST", "/issues/7/comments"),
        ("PUT", "/pulls/7/merge"),
    ]


def test_removing_an_absent_label_is_not_an_error() -> None:
    # The desired end state is "label not present", which is already true.
    error = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    error.read = lambda: b"{}"  # type: ignore[method-assign]

    _client(raiser=error).apply([Action("unlabel", 7, PENDING)])


def test_a_real_api_failure_still_raises() -> None:
    error = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    error.read = lambda: b"insufficient permissions"  # type: ignore[method-assign]

    with pytest.raises(GitHubError, match="403"):
        _client(raiser=error).apply([Action("label", 7, KING)])


def test_only_pull_requests_are_listed_as_submissions() -> None:
    payload = [
        {"number": 1, "user": {"login": "alice"}, "labels": [{"name": PENDING}], "pull_request": {}},
        {"number": 2, "user": {"login": "bob"}, "labels": []},  # a plain issue
    ]

    submissions = _client(payload).list_submissions(label=PENDING)

    assert [item.number for item in submissions] == [1]
    assert submissions[0].labels == (PENDING,)


def test_a_token_is_required_unless_running_dry() -> None:
    with pytest.raises(ValueError, match="token is required"):
        GitHubClient("owner/repo", "")

    GitHubClient("owner/repo", "", dry_run=True)


def test_the_repository_must_be_owner_slash_name() -> None:
    with pytest.raises(ValueError, match="owner/name"):
        GitHubClient("just-a-name", "token")


def test_an_offline_dry_run_never_reaches_the_network() -> None:
    # A dry run that needs a token and a network to preview a plan is not a dry
    # run. Reads are harmless, but they must not be required.
    def explode(request, timeout):
        raise AssertionError("a dry run with no token must not call GitHub")

    client = GitHubClient("owner/repo", "", dry_run=True, opener=explode)
    client.fixtures = [Submission(4, "alice", labels=(PENDING,))]

    assert [item.number for item in client.list_submissions()] == [4]
    client.apply([Action("merge", 4)])


def test_a_dry_run_with_a_token_still_reads_the_real_queue() -> None:
    # Previewing a plan against the live queue is the useful case.
    payload = [{"number": 3, "user": {"login": "bob"}, "labels": [], "pull_request": {}}]
    client = _client(payload, dry_run=True)

    assert [item.number for item in client.list_submissions()] == [3]
