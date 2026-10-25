"""Execution -> PR link, auto-enrollment, merge write-back and trailer discovery on real SQLite."""
import pytest

from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_execution_pr_closure import close_loop
from backend.canvas.opora_execution_pr_discovery import discover, parse_trailers
from backend.canvas.opora_execution_pr_manager import ExecutionPullRequestManager
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks, LinkMissing
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_canvas_service import managed_fixture
from backend.canvas.test_opora_review_fixtures import configure, setup
from backend.integrations.github_merge_transport import GitHubMergeError
from database.repositories.opora_execution_pull_requests import list_execution_pull_requests
from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs, stamp

SHA, NEXT_SHA, MERGE_SHA = "c" * 40, "d" * 40, "e" * 40


def pr(number=7, state="open", body="", head_repo=2):
    return {"repository": {"id": 1, "fullName": "owner/repo"}, "id": 100 + number, "number": number,
            "baseRef": "main", "headRef": "feature", "headSha": SHA, "headRepoId": head_repo,
            "state": state, "body": body}


class Reader:
    def __init__(self, items=None, error=None):
        self.calls, self.items, self.error, self.retry_after = [], items or [], error, 0

    def pull_request(self, repository, number):
        self.calls.append(("pull", repository, number))
        if self.error:
            raise self.error
        return pr(number)

    def recent(self, repository):
        self.calls.append(("recent", repository))
        if self.error:
            raise self.error
        return self.items


@pytest.fixture(name="world")
def world_fixture(tmp_path):
    service, project = managed_fixture(tmp_path)
    scope = setup(service, project["id"])
    scope = {"project": scope["project"], "workspace": scope["workspace"]}
    executions = ExecutionResults(service)
    yield service, scope, executions
    service.close()


def claim(executions, scope, request="claim"):
    context = executions.context(**scope, node="card")
    return executions.claim({**scope, "nodeId": "card", "requestId": request, "ttlSeconds": 60,
                             "expectedAcceptedHead": context["acceptedHead"],
                             "expectedContextVersion": context["contextVersion"]}, "agent:worker")


def body(record, request="link", number=7, **overrides):
    return {"project": record["project"], "workspace": record["workspace"], "token": record["token"],
            "epoch": record["epoch"], "requestId": request, "repository": "Owner/Repo", "number": number,
            "headRef": "feature", "headSha": SHA, **overrides}


def observe(service, scope, binding_id, state, number=7):
    db = service.db_for(scope["project"])
    repo = ReconciliationRepository(db, scope["project"], scope["workspace"])
    with db:
        db.execute("BEGIN IMMEDIATE")
        repo.insert("observation", {"schemaVersion": 1, **scope, "bindingId": binding_id, "createdAt": stamp(2000),
            "data": {"complete": True, "observedFrom": stamp(1999), "observedUntil": stamp(2000),
                     "repository": {"id": 1, "fullName": "owner/repo"},
                     "pr": {"id": 100 + number, "number": number, "baseRef": "main", "headSha": NEXT_SHA,
                            "headRepoId": 2, "state": state, "draft": False, "merged": state == "merged",
                            "mergedAt": stamp(1990) if state == "merged" else None,
                            "mergeCommitSha": MERGE_SHA if state == "merged" else None}}})


def close(service, links, scope):
    with links.transaction(**scope) as repo:
        return close_loop(repo.db, *repo.scope)


def test_agent_link_auto_enrolls_and_is_idempotent(world):
    service, scope, executions = world
    record, reader = claim(executions, scope), Reader()
    links = ExecutionPullRequestLinks(service, reader)
    linked = links.link(record["executionId"], body(record), "agent")
    assert {key: linked[key] for key in ("executionId", "cardId", "acceptedRevision", "repository", "number",
                                         "headSha", "state")} == {
        "executionId": record["executionId"], "cardId": "card", "acceptedRevision": record["acceptedRevision"],
        "repository": "owner/repo", "number": 7, "headSha": SHA, "state": "open"}
    assert linked["enrollment"] == "enrolled" and linked["bindingId"]
    db = service.db_for(scope["project"])
    repo = ReconciliationRepository(db, *scope.values())
    binding = repo.read("binding", linked["bindingId"])
    assert binding["acceptedRevision"] == record["acceptedRevision"] and binding["by"]["kind"] == "system"
    assert binding["enrolledHeadSha"] == SHA and binding["pr"] == {"id": 107, "number": 7, "headRepoId": 2}
    assert repo.latest_control(binding["id"])["action"] == "auto-enroll"
    assert ReconciliationJobs(db, *scope.values()).public(binding["id"])["state"] == "scheduled"
    # Exact replay and a re-link of the same PR are no-ops; no second binding or GitHub read.
    assert links.link(record["executionId"], body(record), "agent") == linked
    assert links.link(record["executionId"], body(record, "again"), "agent")["bindingId"] == linked["bindingId"]
    assert len(repo.bindings()) == 1 and len(reader.calls) == 1
    with pytest.raises(ValueError, match="different linked pull request"):
        links.link(record["executionId"], body(record, "other", number=8), "agent")
    with pytest.raises(ValueError, match="different PR link"):
        links.link(record["executionId"], body(record, "link", headRef="changed"), "agent")
    assert links.read(**scope, execution_id=record["executionId"])["bindingId"] == linked["bindingId"]
    assert linked["planWrittenBack"] is False and linked["mergeSha"] is None
    assert list_execution_pull_requests(db, *scope.values())[0]["executionId"] == record["executionId"]


def test_stale_epoch_and_expired_lease_are_rejected_human_may_link(world):
    service, scope, executions = world
    links = ExecutionPullRequestLinks(service, Reader())
    first = claim(executions, scope, "first")
    executions.release(first["executionId"], {**scope, "token": first["token"], "epoch": first["epoch"]})
    second = claim(executions, scope, "second")
    with pytest.raises(ValueError, match="credential or epoch"):
        links.link(second["executionId"], body(second, epoch=first["epoch"]), "agent")
    with pytest.raises(ValueError, match="authoritative"):
        links.link(first["executionId"], body(first), "agent")
    with service.db_for(scope["project"]) as db:
        db.execute("UPDATE card_leases SET expires_at=0")
    with pytest.raises(ValueError, match="authoritative"):
        links.link(second["executionId"], body(second), "agent")
    with pytest.raises(ValueError, match="Invalid execution fields"):
        links.link(second["executionId"], {k: v for k, v in body(second).items() if k not in ("token", "epoch")}, "agent")
    human = {k: v for k, v in body(second, "human").items() if k not in ("token", "epoch")}
    assert links.link(second["executionId"], human, "human")["source"] == "human"
    with pytest.raises(LinkMissing):
        links.read(**scope, execution_id=first["executionId"])


def test_merge_write_back_is_idempotent_and_keeps_spec(world):
    service, scope, executions = world
    record = claim(executions, scope)
    links = ExecutionPullRequestLinks(service, Reader())
    linked = links.link(record["executionId"], body(record), "agent")
    specs_before = OporaChangesets(service).context(*scope.values())["documents"]
    observe(service, scope, linked["bindingId"], "merged")
    assert close(service, links, scope) == ["execution.merged"]
    assert close(service, links, scope) == []
    result = links.read(**scope, execution_id=record["executionId"])
    assert result["state"] == "merged" and result["mergeSha"] == MERGE_SHA and result["headSha"] == NEXT_SHA
    assert result["awaitingHumanClose"] is True and result["planWrittenBack"] is True
    item = list_execution_pull_requests(service.db_for(scope["project"]), *scope.values())[0]
    assert {"executionId", "cardId", "state", "number", "repository", "headSha", "mergeSha", "planWrittenBack"} <= set(item)
    assert [event["kind"] for event in result["events"]] == ["execution.merged"]
    assert result["events"][0]["mergeSha"] == MERGE_SHA and result["events"][0]["prNumber"] == 7
    assert executions.history(**scope)["executions"][0]["state"] == "released"
    assert service.db_for(scope["project"]).execute("SELECT COUNT(*) FROM card_leases").fetchone()[0] == 0
    assert OporaChangesets(service).context(*scope.values())["documents"] == specs_before


def test_closed_unmerged_flags_attention_and_reopen_clears_it(world):
    service, scope, executions = world
    record = claim(executions, scope)
    links = ExecutionPullRequestLinks(service, Reader())
    linked = links.link(record["executionId"], body(record), "agent")
    observe(service, scope, linked["bindingId"], "closed-unmerged")
    assert close(service, links, scope) == ["execution.pr_closed"]
    assert close(service, links, scope) == []
    closed = links.read(**scope, execution_id=record["executionId"])
    assert closed["state"] == "closed" and closed["attention"] == "pr-closed-unmerged"
    observe(service, scope, linked["bindingId"], "open")
    close(service, links, scope)
    assert links.read(**scope, execution_id=record["executionId"])["attention"] is None


def test_trailer_parsing_is_strict():
    revision = "a" * 40
    assert parse_trailers(f"Fix\n\nOpora-Execution: abc123\r\nOpora-Revision: {revision}\n") == ("abc123", revision)
    assert parse_trailers(f"opora-execution: abc\nOPORA-REVISION: {revision}") == ("abc", revision)
    assert parse_trailers(f"Opora-Execution: abc\nOpora-Execution: def\nOpora-Revision: {revision}") is None
    assert parse_trailers("Opora-Execution: abc\nOpora-Revision: notasha") is None
    assert parse_trailers(f"text Opora-Execution: abc\nOpora-Revision: {revision}") is None
    assert parse_trailers(None) is None and parse_trailers("") is None


def test_discovery_links_by_trailers_and_enrolls_without_extra_reads(world):
    service, scope, executions = world
    record = claim(executions, scope)
    trailer = f"Opora-Execution: {record['executionId']}\nOpora-Revision: {record['acceptedRevision']}"
    wrong = f"Opora-Execution: {record['executionId']}\nOpora-Revision: {'f' * 40}"
    reader = Reader([pr(9, body=wrong), pr(7, body=trailer), pr(8, body="no trailers")])
    links = ExecutionPullRequestLinks(service, reader)
    assert discover(service, links, scope["project"]) == [record["executionId"]]
    linked = links.read(**scope, execution_id=record["executionId"])
    assert linked["number"] == 7 and linked["source"] == "discovery" and linked["enrollment"] == "enrolled"
    assert reader.calls == [("recent", "owner/repo")]
    # Already linked: no candidate remains, so no further GitHub request.
    assert discover(service, links, scope["project"]) == [] and len(reader.calls) == 1


def test_github_not_configured_is_safe(world):
    service, scope, executions = world
    record = claim(executions, scope)
    configure(service, scope["project"], url="https://example.invalid/owner/repo.git")
    reader = Reader()
    links = ExecutionPullRequestLinks(service, reader)
    linked = links.link(record["executionId"], body(record), "agent")
    assert linked["enrollment"] == "unavailable" and linked["enrollmentError"] == "github-not-configured"
    assert linked["bindingId"] is None
    assert discover(service, links, scope["project"]) == []
    manager = ExecutionPullRequestManager(service, links)
    manager.run_once()
    assert reader.calls == []


def test_unavailable_github_retries_enrollment_from_the_loop(world, monkeypatch):
    service, scope, executions = world
    monkeypatch.setenv("OPORA_EXECUTION_PR_DISCOVERY_SECONDS", "0")
    record = claim(executions, scope)
    reader = Reader(error=GitHubMergeError("github-unavailable"))
    now = [1000.0]
    links = ExecutionPullRequestLinks(service, reader, clock=lambda: now[0])
    linked = links.link(record["executionId"], body(record), "agent")
    assert linked["enrollment"] == "pending" and linked["enrollmentError"] == "github-unavailable"
    manager = ExecutionPullRequestManager(service, links, clock=lambda: now[0])
    manager.run_once()
    assert len(reader.calls) == 1  # backoff not yet elapsed
    reader.error, now[0] = None, 2000.0
    manager.run_once()
    assert links.read(**scope, execution_id=record["executionId"])["enrollment"] == "enrolled"
    manager.close()


def test_missing_token_is_told_as_auth_missing_and_heals_once_set(world, monkeypatch):
    service, scope, executions = world
    monkeypatch.setenv("OPORA_EXECUTION_PR_DISCOVERY_SECONDS", "0")
    record = claim(executions, scope)
    reader = Reader(error=GitHubMergeError("github-auth-missing", action_required=True))
    now = [1000.0]
    links = ExecutionPullRequestLinks(service, reader, clock=lambda: now[0])
    linked = links.link(record["executionId"], body(record), "agent")
    assert (linked["enrollment"], linked["enrollmentError"], linked["attention"]) == (
        "pending", "github-auth-missing", "github-auth-missing")
    assert "OPORA_GITHUB_TOKEN" in linked["enrollmentMessage"] and "token" in linked["enrollmentMessage"]
    manager = ExecutionPullRequestManager(service, links, clock=lambda: now[0])
    reader.error, now[0] = None, 2000.0  # The token was set: the retry enrolls and the attention clears.
    manager.run_once()
    healed = links.read(**scope, execution_id=record["executionId"])
    assert (healed["enrollment"], healed["enrollmentError"], healed["attention"], healed["enrollmentMessage"]) == (
        "enrolled", None, None, None)
    manager.close()


def test_office_links_after_reported_result_with_own_credentials(world):
    """agent-office links the PR after the worker submitted its result and the lease is gone."""
    service, scope, executions = world
    first = claim(executions, scope, "first")
    credentials = {**scope, "token": first["token"], "epoch": first["epoch"]}
    executions.submit(first["executionId"], {**credentials, "requestId": "result", "result": {"summary": "Done"}})
    assert service.db_for(scope["project"]).execute("SELECT COUNT(*) FROM card_leases").fetchone()[0] == 0
    second = claim(executions, scope, "second")
    links = ExecutionPullRequestLinks(service, Reader())
    office = {"projectId": scope["project"], "workspaceId": scope["workspace"], "token": first["token"],
              "epoch": first["epoch"], "requestId": "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
              "repository": "owner/repo", "number": 7, "headRef": "feature", "headSha": SHA}
    with pytest.raises(ValueError, match="credential or epoch"):
        links.link(first["executionId"], {**office, "epoch": first["epoch"] + 1}, "agent")
    with pytest.raises(ValueError, match="credential or epoch"):
        links.link(first["executionId"], {**office, "token": second["token"], "epoch": second["epoch"]}, "agent")
    with pytest.raises(ValueError, match="either project"):
        links.link(first["executionId"], {**office, "project": scope["project"]}, "agent")
    linked = links.link(first["executionId"], office, "agent")
    assert linked["enrollment"] == "enrolled" and linked["headSha"] == SHA
    assert links.link(first["executionId"], office, "agent") == linked
    # A new pushed head on the same PR re-links with a new requestId: updated, not a conflict.
    moved = links.link(first["executionId"], {**office, "requestId": "2c4e28ba-2fa1-11d2-883f-0016d3cca427",
                                              "headSha": NEXT_SHA}, "agent")
    assert moved["headSha"] == NEXT_SHA and moved["bindingId"] == linked["bindingId"]
    with pytest.raises(ValueError, match="different PR link"):
        links.link(first["executionId"], {**office, "headSha": NEXT_SHA}, "agent")
    with pytest.raises(ValueError, match="different linked pull request"):
        links.link(first["executionId"], {**office, "requestId": "other", "number": 8}, "agent")
    with pytest.raises(ValueError, match="differs from the project repository"):
        links.link(second["executionId"], {**office, "token": second["token"], "epoch": second["epoch"],
                                           "requestId": "foreign", "repository": "other/repo"}, "agent")
