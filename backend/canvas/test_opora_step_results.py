"""Accepted steps are pinned in the assignment; stepResults are validated, idempotent progress."""
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
pytestmark = pytest.mark.plan_steps_claim


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


def test_assignment_snapshot_pins_accepted_steps(stepped, service):
    authority, _ = stepped
    record = claim(authority)
    assert record["assignment"]["steps"] == PLAN
    from backend.canvas.opora_execution_validation import assignment
    assert assignment(service, "draft", "draft", "b")["steps"] == []


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


def test_node_spec_plan_view_shows_working_and_accepted(stepped, service):
    result = plan_view(service, "draft", "draft", "a", service.node_spec("draft", "draft", "a"))
    assert result["plan"]["working"] == PLAN and result["plan"]["accepted"] == PLAN
    assert result["plan"]["workingDiffers"] is False


def test_claim_refuses_card_without_steps_or_with_blocked_predecessor(stepped, service, monkeypatch):
    from backend.canvas.opora_agent_state_steps import ClaimRefused
    authority, _ = stepped
    with pytest.raises(ClaimRefused) as refused:
        claim(authority, "nosteps", node="b")
    assert refused.value.code == "plan_steps_missing"
    from backend.canvas import opora_agent_state_dag
    real = opora_agent_state_dag.facts
    monkeypatch.setattr(opora_agent_state_dag, "facts",
                        lambda *args: {**real(*args), "blockedBy": {"a": ["b"]}})
    with pytest.raises(ClaimRefused) as refused:
        claim(authority, "blocked")
    assert refused.value.code == "blocked_by_predecessor"
    assert card(service)["status"] == "blocked" and card(service)["blockedBy"] == ["b"]


def test_step_events_on_claim_and_result(stepped, service):
    authority, _ = stepped
    record = claim(authority)
    submit(authority, record, "r1", done("s1"), done("s2", "failed"), done("s3", "skipped"))
    from database.repositories.opora_events import page
    rows, _, _ = page(service.db_for("draft"), "draft", "draft", 0, 500)
    events = [(item["kind"], item["stepId"]) for item in rows if item["kind"].startswith("step.")]
    assert events == [("step.started", "s1"), ("step.done", "s1"), ("step.failed", "s2")]


def test_done_step_stays_done_across_runs_and_items_list_every_step(stepped, service):
    authority, _ = stepped
    first = claim(authority)
    submit(authority, first, "r1", done("s1"))
    second = claim(authority, "second")
    submit(authority, second, "r2", done("s1", "failed"), done("s2", "failed"))
    item = card(service)
    assert item["steps"] == {"total": 3, "done": 1, "current": "s2"}
    assert item["stepItems"] == [{"id": "s1", "status": "done", "executionId": first["executionId"]},
                                 {"id": "s2", "status": "failed", "executionId": second["executionId"]},
                                 {"id": "s3", "status": "waiting", "executionId": None}]


def test_agent_state_cards_carry_dod_and_step_items(stepped, service):
    from backend.canvas.opora_agent_state import AgentState
    from backend.canvas.opora_card_done import REQUIREMENTS
    authority, _ = stepped
    submit(authority, claim(authority), "r1", done("s1"), done("s2"), done("s3"))
    entry = next(item for item in AgentState(service).read("draft", "draft")["cards"] if item["nodeId"] == "a")
    assert [step["status"] for step in entry["steps"]["items"]] == ["done", "done", "done"]
    dod = entry["dod"]
    assert {key: dod[key] for key in REQUIREMENTS} == {
        "steps": True, "card_acceptance": True, "gate_ready": False, "merged": False,
        "plan_written_back": False, "journeys": True, "human_close": False}
    assert dod["gate"] == "review" and dod["done"] is False
    assert dod["missing"] == ["gate_ready", "merged", "plan_written_back", "human_close"]
