"""Merge gate per-step evidence: status and evidence per pinned step, verdict flags gaps."""
import pytest

from backend.canvas.opora_execution_steps import checkpoint
from backend.canvas.opora_review_step_evidence import for_link
from backend.canvas.test_opora_auto_rebase import propose
from backend.canvas.test_opora_changesets import accept, service
from backend.canvas.test_opora_executions import claim, credentials
from backend.canvas.test_opora_plan_steps import PLAN
from backend.canvas.test_opora_step_results import done, stepped, submit

__all__ = ["service", "stepped"]
pytestmark = pytest.mark.plan_steps_claim


def read(service, record):
    return for_link(service.db_for("draft"), "draft", "draft", {"execution_id": record["executionId"]})


def test_each_pinned_step_shows_status_and_newest_evidence(stepped, service):
    authority, _ = stepped
    first = claim(authority)
    checkpoint(authority, first["executionId"], {**credentials(first), "requestId": "c1", **done("s1")})
    blank = {"stepId": "s3", "status": "done", "evidence": {"notes": "  "}}
    authority.submit(first["executionId"], {**credentials(first), "requestId": "r1", "result": {
        "summary": "Work", "stepResults": [done("s2", "failed"), blank], "decisions": ["Keep the API small"]}})
    steps = read(service, first)
    assert [(item["id"], item["status"], item["reported"], item["source"], item["evidenced"]) for item in steps["items"]] == [
        ("s1", "done", "done", "checkpoint", True), ("s2", "blocked", "failed", "result", True),
        ("s3", "done", "done", "result", False)]
    assert steps["items"][0]["evidence"] == {"checks": ["pytest"], "commits": ["abc1234"], "notes": "ok"}
    assert steps["items"][0]["title"] == "Step s1" and steps["items"][0]["executionId"] == first["executionId"]
    assert steps["verdict"] == {"status": "incomplete", "total": 3, "done": 2, "blocked": ["s2"], "missing": [],
                                "withoutEvidence": ["s3"]}
    assert steps["decisions"] == 1


def test_missing_steps_and_done_sticking_across_runs(stepped, service):
    authority, head = stepped
    first = claim(authority)
    submit(authority, first, "r1", done("s1"))
    second = claim(authority, "second")
    assert read(service, second)["verdict"]["missing"] == ["s2", "s3"]
    submit(authority, second, "r2", done("s1", "failed"), done("s2"), done("s3"))
    steps = read(service, second)
    assert [(item["status"], item["executionId"]) for item in steps["items"]] == [
        ("done", first["executionId"]), ("done", second["executionId"]), ("done", second["executionId"])]
    assert steps["verdict"]["status"] == "evidenced" and steps["verdict"]["withoutEvidence"] == []
    # A changed step definition: earlier runs' reports of the old s3 no longer evidence the new one.
    accept(service, propose(service, "a", steps=[PLAN[0], PLAN[1], {**PLAN[2], "title": "Changed"}]), head["id"])
    third = claim(authority, "third")
    steps = read(service, third)
    assert [item["status"] for item in steps["items"]] == ["done", "done", "missing"]
    assert steps["verdict"] == {"status": "incomplete", "total": 3, "done": 2, "blocked": [], "missing": ["s3"],
                                "withoutEvidence": ["s3"]}


def test_unknown_execution_adds_nothing(stepped, service):
    assert for_link(service.db_for("draft"), "draft", "draft", {"execution_id": "missing"}) is None
