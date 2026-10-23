"""Per-step checkpoints survive a crashed run; result decisions become card decisions (A/B protokol M4)."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_steps import checkpoint
from backend.canvas.opora_step_results import progress
from backend.canvas.test_opora_changesets import SCOPE, service
from backend.canvas.test_opora_executions import claim, credentials
from backend.canvas.test_opora_step_results import accepted_a, card, done, stepped
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, validate_state
from database.schema.project_schema import PROJECT_TABLES

__all__ = ["service", "stepped"]
pytestmark = pytest.mark.plan_steps_claim


def step(authority, record, request, item):
    return checkpoint(authority, record["executionId"], {**credentials(record), "requestId": request, **item})


def step_events(service):
    from database.repositories.opora_events import page
    rows, _, _ = page(service.db_for("draft"), "draft", "draft", 0, 500)
    return [(item["kind"], item["stepId"], item["executionId"]) for item in rows if item["kind"].startswith("step.")]


def expire(service):
    with service.db_for("draft") as db:
        db.execute("UPDATE card_leases SET expires_at=0")


def test_crash_after_two_steps_keeps_them_and_next_run_continues(stepped, service):
    authority, _ = stepped
    first = claim(authority)
    stored = step(authority, first, "c1", done("s1"))
    assert stored["stepId"] == "s1" and "token" not in str(stored)
    step(authority, first, "c2", done("s2"))
    expire(service)  # the agent crashed; its lease ran out
    summary, _ = progress(service.db_for("draft"), "draft", "draft", "a", accepted_a(service))
    assert summary == {"total": 3, "done": 2, "current": "s3"}
    assert card(service)["steps"] == {"total": 3, "done": 2, "current": "s3"}
    second = claim(authority, "second")
    read = authority.read_assignment(second["executionId"], **SCOPE, token=second["token"])
    assert read["progress"]["current"] == "s3"
    assert [(item["id"], item["status"], item["executionId"]) for item in read["progress"]["steps"]] == [
        ("s1", "done", first["executionId"]), ("s2", "done", first["executionId"]), ("s3", "current", None)]
    assert "progress" not in read["assignment"]
    assert step_events(service) == [
        ("step.started", "s1", first["executionId"]), ("step.done", "s1", first["executionId"]),
        ("step.started", "s2", first["executionId"]), ("step.done", "s2", first["executionId"]),
        ("step.started", "s3", first["executionId"]), ("step.started", "s3", second["executionId"])]


def test_checkpoint_is_idempotent_and_needs_live_authority(stepped, service):
    authority, _ = stepped
    record = claim(authority)
    first = step(authority, record, "c1", done("s1"))
    assert step(authority, record, "c1", done("s1")) == first
    with pytest.raises(ValueError, match="different content"):
        step(authority, record, "c1", done("s1", "failed"))
    for bad in ({**done("s9")}, {**done("s1"), "status": "maybe"}, {"stepId": "s1", "status": "done", "evidence": {}}):
        with pytest.raises(ValueError):
            step(authority, record, "bad", bad)
    with pytest.raises(ValueError, match="credential"):
        checkpoint(authority, record["executionId"], {**credentials(record), "token": "0" * 64,
                                                      "requestId": "c2", **done("s2")})
    with pytest.raises(ValueError, match="Invalid execution fields"):
        checkpoint(authority, record["executionId"], {**credentials(record), "requestId": "c3", **done("s2"), "extra": 1})
    expire(service)
    assert step(authority, record, "c1", done("s1")) == first  # replay after expiry: same receipt
    with pytest.raises(ValueError, match="authoritative"):
        step(authority, record, "c2", done("s2"))


def test_final_result_completes_without_repeating_checkpoint_events(stepped, service):
    authority, _ = stepped
    record = claim(authority)
    step(authority, record, "c1", done("s1"))
    receipt = authority.submit(record["executionId"], {**credentials(record), "requestId": "r1", "result": {
        "summary": "Work", "stepResults": [done("s1"), done("s2"), done("s3")]}})
    assert receipt["state"] == "reported"
    kinds = [(kind, item) for kind, item, _ in step_events(service)]
    assert kinds.count(("step.done", "s1")) == 1 and ("step.done", "s3") in kinds
    assert card(service)["steps"] == {"total": 3, "done": 3, "current": None}
    with pytest.raises(ValueError, match="authoritative"):
        step(authority, record, "c2", done("s2"))  # reported runs take no more checkpoints


def test_result_decisions_are_card_decisions_with_execution(stepped, service):
    authority, _ = stepped
    record = claim(authority)
    with pytest.raises(ValueError, match="decisions"):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "bad",
                                                 "result": {"summary": "Work", "decisions": ["ok", ""]}})
    before = DesktopV3State(service).read(**SCOPE)
    assert before["state"]["decisions"] == []
    with pytest.raises(ValueError, match="decisions"):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "bad2",
                                                 "result": {"summary": "Work", "decisions": [{"why": "bez textu"}]}})
    payload = {**credentials(record), "requestId": "r1", "result": {"summary": "Work", "decisions": [
        "Webhook, ne polling", {"text": "Klíč sha256", "why": "audit"}]}}  # the handoff keeps the object
    receipt = authority.submit(record["executionId"], payload)
    assert authority.submit(record["executionId"], payload) == receipt  # replay adds nothing
    after = DesktopV3State(service).read(**SCOPE)
    assert after["revision"] == before["revision"] + 1
    decisions = after["state"]["decisions"]
    assert [item["text"] for item in decisions] == ["Webhook, ne polling", "Klíč sha256"]
    assert {(item["nodeId"], item["by"], item["executionId"]) for item in decisions} == {("a", "agent", record["executionId"])}
    assert receipt["decisionIds"] == [item["id"] for item in decisions]
    # A plain legacy decision (no executionId) and a correction of an execution decision stay valid.
    legacy = {key: value for key, value in decisions[0].items() if key != "executionId"} | {"id": "legacy1"}
    fix = {**decisions[1], "id": "fix1", "supersedes": decisions[1]["id"], "text": "Klíč sha512"}
    validate_state({**after["state"], "decisions": [*decisions, legacy, fix]})
    with pytest.raises(ValueError):
        validate_state({**after["state"], "decisions": [{**decisions[0], "executionId": "bad id!"}]})


def test_existing_project_database_gains_the_checkpoint_table(tmp_path):
    assert PROJECT_TABLES["opora_execution_steps"] == "project_id"
    root = tmp_path / "data"
    first = CanvasService(root)
    db = first.db_for("draft")
    with db:
        db.execute("DROP TABLE opora_execution_steps")  # a project database from before M4
        db.execute("INSERT INTO opora_execution_results VALUES('draft','draft','e1','r1','d','{}')")
    first.close()
    second = CanvasService(root)
    try:
        db = second.db_for("draft")
        assert db.execute("SELECT COUNT(*) FROM opora_execution_steps").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 1
    finally:
        second.close()
