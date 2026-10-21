"""Agent-state over the REAL execution -> PR link module: no fake seam, real SQLite, offline GitHub.

Links a PR to a reported execution the way agent-office does, simulates the merge write-back
and checks that the PR stages leave `not_connected`, the `pull_request_link` gap disappears and
the merged card surfaces as a human "close card" decision until a human confirms it."""
import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.opora_execution_pull_requests import list_execution_pull_requests as real_list
from backend.canvas.test_opora_execution_pull_requests import MERGE_SHA, SHA, Reader, claim, close, observe, world_fixture  # noqa: F401
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.test_completion_evidence import evidence


@pytest.fixture(autouse=True)
def real_seam():
    pulls.register(None)
    yield
    pulls.register(None)


def stage(document, name):
    return next(item for item in document["stages"] if item["id"] == name)


def office_body(scope, record, request="1b4e28ba-2fa1-11d2-883f-0016d3cca427"):
    return {"projectId": scope["project"], "workspaceId": scope["workspace"], "token": record["token"],
            "epoch": record["epoch"], "requestId": request, "repository": "owner/repo", "number": 7,
            "headRef": "feature", "headSha": SHA}


def test_seam_resolves_the_real_link_module_with_its_signature():
    assert pulls.source() is real_list
    assert list(__import__("inspect").signature(real_list).parameters) == ["service", "project_id", "workspace_id"]


def test_agent_state_reads_real_links_through_merge_and_human_close(world):
    service, scope, executions = world
    record = claim(executions, scope)
    executions.submit(record["executionId"], {**scope, "token": record["token"], "epoch": record["epoch"],
                                              "requestId": "result", "result": {"summary": "Done"}})
    state = AgentState(service)

    before = state.read(**scope)
    assert "pull_request_link" not in [gap["id"] for gap in before["gaps"]]
    assert stage(before, "pull_request") == {"id": "pull_request", "count": 0, "health": "blocking",
                                             "reason": "results_without_pull_request"}
    [link] = [item for item in before["actions"] if item["verb"] == "link_pull_request"]
    assert link["status"] == "ready" and link["targetId"] == record["executionId"]

    links = ExecutionPullRequestLinks(service, Reader())
    linked = links.link(record["executionId"], office_body(scope, record), "agent")
    [item] = real_list(service, scope["project"], scope["workspace"])
    assert {"executionId", "cardId", "state", "number", "repository", "headSha", "mergeSha",
            "planWrittenBack", "awaitingHumanClose"} <= set(item)
    opened = state.read(**scope)
    assert stage(opened, "pull_request") == {"id": "pull_request", "count": 1, "health": "ok", "reason": "results_linked"}
    assert stage(opened, "merge")["reason"] == "pull_requests_open"
    assert not [item for item in opened["actions"] if item["verb"] in ("link_pull_request", "close_card")]

    observe(service, scope, linked["bindingId"], "merged")
    assert close(service, links, scope) == ["execution.merged"]
    merged = state.read(**scope)
    for name in ("pull_request", "merge", "plan_writeback"):
        assert stage(merged, name)["health"] != "not_connected"
    assert stage(merged, "merge") == {"id": "merge", "count": 1, "health": "ok", "reason": "merged"}
    assert stage(merged, "plan_writeback") == {"id": "plan_writeback", "count": 1, "health": "ok",
                                               "reason": "plan_written_back"}
    assert "pull_request_link" not in [gap["id"] for gap in merged["gaps"]]
    [action] = [item for item in merged["actions"] if item["verb"] == "close_card"]
    assert action["targetId"] == "card" and action["status"] == "blocked" and action["blockReason"] == "human_only"
    assert action["preconditions"] == {"executionId": record["executionId"], "mergeSha": MERGE_SHA}
    [decision] = [item for item in merged["decisions"] if item["kind"] == "close_card"]
    assert decision["targetId"] == "card" and decision["actionId"] == action["id"]
    assert record["token"] not in str(merged)

    # A human confirms the card: the derived marker clears and the decision disappears.
    desk = DesktopV3State(service)
    current = desk.read(**scope)
    nodes = current["state"]["nodes"]
    nodes["card"] = {"phase": "discover", "criteria": [], "steps": [], "evidence": evidence(),
                     "done": {"confirmed": True, "at": "2026-10-21T09:00:00+00:00", "by": "human", "note": "Merged."}}
    desk.save({**scope, "expectedRevision": current["revision"], "state": current["state"]}, actor="human")
    closed = state.read(**scope)
    assert not [item for item in closed["decisions"] if item["kind"] == "close_card"]
    assert not [item for item in closed["actions"] if item["verb"] == "close_card"]


def test_agent_state_with_real_link_module_has_no_sql_writes(world):
    service, scope, executions = world
    record = claim(executions, scope)
    links = ExecutionPullRequestLinks(service, Reader())
    linked = links.link(record["executionId"], office_body(scope, record), "agent")
    observe(service, scope, linked["bindingId"], "merged")
    close(service, links, scope)
    db = service.db_for(scope["project"])
    sql = []
    db.set_trace_callback(sql.append)
    try:
        AgentState(service).read(**scope)
    finally:
        db.set_trace_callback(None)
    assert not [command for command in sql
                if command.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN", "CREATE"))]
