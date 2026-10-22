"""Accepted steps are pinned in the assignment; stepResults are validated, idempotent progress."""
import sys
import types

import pytest

from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_process_sync import ProcessSync
from backend.canvas.opora_step_results import plan_view, progress
from backend.canvas.test_opora_auto_rebase import propose
from backend.canvas.test_opora_changesets import SCOPE, accept, baseline, service
from backend.canvas.test_opora_executions import claim, credentials
from backend.canvas.test_opora_plan_steps import PLAN
from database.schema.opora_execution_schema import SCHEMA

__all__ = ["service"]


@pytest.fixture
def stepped(service):
    service.db_for("draft").executescript(SCHEMA)
    initial = baseline(service)
    head = accept(service, propose(service, "a", goal="Build it", steps=PLAN), initial["id"])
    return ExecutionResults(service), head


def done(step, status="done"):
    return {"stepId": step, "status": status, "evidence": {"notes": "ok", "commits": ["abc1234"], "checks": ["pytest"]}}


def submit(authority, record, request, *items):
    return authority.submit(record["executionId"], {**credentials(record), "requestId": request,
                                                    "result": {"summary": "Work", "stepResults": list(items)}})


def card(service):
    return ProcessSync(service).read(**SCOPE, node="a")["items"][0]


def accepted_a(service):
    from backend.canvas.opora_changesets import OporaChangesets
    documents = OporaChangesets(service).context("draft", "draft")["acceptedDocuments"]
    return next(item for item in documents if item["nodeId"] == "a")


def test_assignment_snapshot_pins_accepted_steps(stepped):
    authority, _ = stepped
    record = claim(authority)
    assert record["assignment"]["steps"] == PLAN
    other = claim(authority, "other", node="b")
    assert other["assignment"]["steps"] == []


def test_step_results_validated_and_idempotent(stepped, service):
    authority, _ = stepped
    record = claim(authority)
    for bad in ([done("s9")], [done("s1"), done("s1")], [{**done("s1"), "status": "maybe"}],
                [{**done("s1"), "evidence": {"commits": ["zz"], "notes": ""}}], [{"stepId": "s1"}]):
        with pytest.raises(ValueError):
            submit(authority, record, "bad", *bad)
    first = submit(authority, record, "r1", done("s1"), done("s2", "failed"))
    assert submit(authority, record, "r1", done("s1"), done("s2", "failed")) == first
    with pytest.raises(ValueError, match="different content"):
        submit(authority, record, "r1", done("s1"))
    summary, _ = progress(service.db_for("draft"), "draft", "draft", "a", accepted_a(service))
    assert summary == {"total": 3, "done": 1, "current": "s2"}


def test_progress_newest_report_wins_and_changed_step_resets(stepped, service):
    authority, head = stepped
    submit(authority, claim(authority), "r1", done("s1"), done("s2", "failed"))
    submit(authority, claim(authority, "second"), "r2", done("s2"), done("s3"))
    item = card(service)
    assert item["steps"] == {"total": 3, "done": 3, "current": None}
    assert item["acceptanceEvidence"] is True
    accept(service, propose(service, "a", steps=[PLAN[0], PLAN[1], {**PLAN[2], "title": "Changed"}]), head["id"])
    item = card(service)
    assert item["steps"] == {"total": 3, "done": 2, "current": "s3"}
    assert item["acceptanceEvidence"] is False


def test_readiness_from_accepted_steps_not_stages(service):
    service.db_for("draft").executescript(SCHEMA)
    initial = baseline(service)
    head = accept(service, propose(service, "a", goal="Build it"), initial["id"])
    assert card(service)["status"] == "needs-steps"
    accept(service, propose(service, "a", steps=PLAN), head["id"])
    item = card(service)
    assert item["status"] == "ready" and item["pipeline"]["stageCount"] == 0
    assert item["blockedBy"] == []


def test_blocked_by_from_card_dag_module(stepped, service, monkeypatch):
    module = types.ModuleType("backend.canvas.opora_card_dag")
    module.blocked_by = lambda canvas, project, workspace: {"a": ["b"]}
    monkeypatch.setitem(sys.modules, "backend.canvas.opora_card_dag", module)
    item = card(service)
    assert item["status"] == "blocked" and item["blockedBy"] == ["b"]


def test_node_spec_plan_view_shows_working_and_accepted(stepped, service):
    result = plan_view(service, "draft", "draft", "a", service.node_spec("draft", "draft", "a"))
    assert result["plan"]["working"] == PLAN and result["plan"]["accepted"] == PLAN
    assert result["plan"]["workingDiffers"] is False
