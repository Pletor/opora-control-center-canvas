"""Actual SQLite projection reads do not become a second writable process machine."""
import copy
import json

import pytest

from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_process_sync import ProcessSync
from backend.canvas.test_opora_changesets import SCOPE, accept, baseline, legacy_save, propose
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_execution_budgets import configure, v2
from backend.canvas.test_opora_executions import claim, credentials
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.pipeline_routing import PipelineRouting


@pytest.fixture
def planned(service):
    legacy_save(service, goal="Read accepted task")
    baseline(service)
    return ExecutionResults(service)


def row(service, node="a"):
    return ProcessSync(service).read(**SCOPE, node=node)["items"][0]


def route(service):
    """Legacy pipeline (reported only) plus accepted plan steps, which are what makes a card ready."""
    pipeline(service)
    add_steps(service)


def pipeline(service):
    current = DesktopV3State(service).read(**SCOPE)
    PipelineRouting(service).apply({**SCOPE, "nodeId": "a", "expectedRevision": current["revision"],
                                    "op": "route", "profile": "code", "reason": "Native process"}, actor="human")


def add_steps(service, node="a"):
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.test_opora_auto_rebase import propose as propose_fields
    from backend.canvas.test_opora_plan_steps import PLAN
    head = OporaChangesets(service).context("draft", "draft")["acceptedHead"]
    accept(service, propose_fields(service, node, steps=PLAN), head)


def save_node(service, change):
    store = DesktopV3State(service)
    current = store.read(**SCOPE)
    state = copy.deepcopy(current["state"])
    change(state["nodes"]["a"])
    return store.save({**SCOPE, "expectedRevision": current["revision"], "state": state}, actor="human")


def test_missing_plan_acceptance_and_pipeline_are_distinct(service):
    assert row(service)["status"] == "needs-plan"
    legacy_save(service)
    assert row(service)["status"] == "needs-acceptance"
    baseline(service)
    assert row(service)["status"] == "needs-steps"
    route(service)
    item = row(service)
    assert item["status"] == "ready"
    assert item["pipeline"]["stageCount"] > 1
    assert item["currentExecution"] is None


def test_reads_have_no_sql_writes_or_private_capabilities(planned, service):
    route(service)
    record = claim(planned)
    db = service.db_for("draft")
    before = (list(db.iterdump()), list(service.db.iterdump()), db.total_changes, service.db.total_changes)
    sql = []
    db.set_trace_callback(sql.append)
    try:
        output = ProcessSync(service).read(**SCOPE)
        ProcessSync(service).read(**SCOPE)
    finally:
        db.set_trace_callback(None)
    assert before == (list(db.iterdump()), list(service.db.iterdump()), db.total_changes, service.db.total_changes)
    assert not any(command.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN", "CREATE")) for command in sql)
    assert record["token"] not in json.dumps(output)
    assert "assignment" not in json.dumps(output)
    assert row(service)["status"] == "running"
    assert not row(service)["executionAvailability"]["available"]


def test_report_is_separate_from_card_completion_and_revision(planned, service):
    record = claim(planned)
    planned.submit(record["executionId"], {**credentials(record), "requestId": "report", "result": {"summary": "Reported only"}})
    item = row(service)
    assert item["status"] == "reported" and item["currentExecution"]["results"] == 1
    assert not item["doneConfirmed"]
    proposal = propose(service)
    accept(service, proposal, record["acceptedRevision"])
    item = row(service)
    assert item["status"] == "stale"
    assert item["currentExecution"]["results"] == 1
    assert not item["currentExecution"]["matchesCurrentRevision"]


def test_active_run_is_observed_despite_exhausted_admission(planned, service):
    configure(planned, limits={"maxRunSeconds": 60, "maxAttempts": 1, "maxRepairRounds": 0})
    v2(planned)
    item = row(service)
    assert item["status"] == "running"
    assert not item["executionAvailability"]["available"]
    assert "exhausted" in item["executionAvailability"]["unavailableReason"]


def test_expired_lease_is_never_presented_as_active(planned, service):
    claim(planned)
    with service.db_for("draft") as db:
        db.execute("UPDATE card_leases SET expires_at=0")
    item = row(service)
    assert item["currentExecution"]["state"] == "revoked"
    assert item["status"] != "running"


def test_legacy_pipeline_is_reported_but_never_gates_readiness(planned, service):
    from backend.editor.agent_memory.test_completion_evidence import evidence
    route(service)
    save_node(service, lambda node: node["stages"]["items"][-1].update(status="failed", note="Blocker"))
    item = row(service)
    assert item["status"] == "ready" and item["pipeline"]["failedCount"] == 1
    save_node(service, lambda node: [item.update(status="passed") for item in node["stages"]["items"]])
    assert row(service)["status"] == "ready"
    # A stepped card closes by the single definition of done, not by legacy evidence and pipeline.
    with pytest.raises(ValueError, match="definice hotovo"):
        save_node(service, lambda node: node.update(evidence=evidence(), done={"confirmed": True, "by": "human", "at": "", "note": "Human confirmation"}))


def test_card_without_steps_keeps_legacy_closure(planned, service):
    from backend.editor.agent_memory.test_completion_evidence import evidence
    pipeline(service)
    save_node(service, lambda node: [item.update(status="passed") for item in node["stages"]["items"]])
    save_node(service, lambda node: node.update(evidence=evidence(), done={"confirmed": True, "by": "human", "at": "", "note": "Human confirmation"}))
    item = row(service)
    assert item["status"] == "closed" and item["doneConfirmed"]
    assert "merge" in item["nextAction"]["reason"]


@pytest.mark.parametrize("project,workspace,node", [("../draft", "draft", None), ("draft", "missing", None),
                                                   ("draft", "draft", "missing"), ("draft", "draft", "a" * 81)])
def test_scope_and_card_selection_fail_closed(service, project, workspace, node):
    with pytest.raises(ValueError):
        ProcessSync(service).read(project, workspace, node)


def test_explicit_card_limit_does_not_claim_full_coverage(service):
    from backend.canvas.test_graph_card import node
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [*view["graph"]["nodes"], *[node(f"card-{index}") for index in range(2, 101)]], "edges": []}, view["digest"])
    output = ProcessSync(service).read(**SCOPE)
    assert len(output["items"]) == output["cardLimit"] == 100
    assert output["truncated"] and output["totalCards"] == 103
    single = ProcessSync(service).read(**SCOPE, node="card-100")
    assert single["items"][0]["nodeId"] == "card-100" and not single["truncated"]


def test_full_read_builds_the_canvas_view_once(planned, service, monkeypatch):
    # Under the project lock `view` does not memoize, and each card's availability rebuilt it for every node:
    # on a Git project that was thousands of git subprocesses while the lock stalled every save.
    built = []
    original = service._view
    monkeypatch.setattr(service, "_view", lambda pid, wid: built.append(wid) or original(pid, wid))
    ProcessSync(service).read(**SCOPE)
    assert built == [SCOPE["workspace"]]
    built.clear()
    service.view(SCOPE["project"], SCOPE["workspace"])
    with service.lock_for(SCOPE["project"]):
        service.view(SCOPE["project"], SCOPE["workspace"])
    assert len(built) == 2  # outside a steady block nothing is held over
