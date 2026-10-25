"""Real accepted assignments keep historical origin claims and native outcome tiers distinct."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_learning_routes import create_harness_learning_router
from backend.canvas.test_opora_changesets import SCOPE, accept
from backend.canvas.test_opora_execution_context import claimed
from backend.library.harness_origin_history import read
from backend.library.test_harness_kit import propose_kit
from backend.library.test_harness_learning import confirm, merged_link
from backend.library.test_harness_selection import selected


def enroll(sparse, value):
    graphs, authority, refs = sparse
    proposal, head = propose_kit(sparse, value, {"steps": [{"id": "s1", "order": 1,
        "title": "Check", "acceptance": ["Pass"], "dependsOn": []}]})
    accept(graphs.service, proposal, head)
    return graphs.service, authority, refs, claimed(sparse)


def origins():
    return [{"slot": "slot." + scope, "scope": scope,
             "node": None if scope in {"global", "repository"} else "opora:draft:draft:" + scope}
            for scope in ["global", "repository", "page", "layer", "area", "sector", "task"]]


def test_seven_origins_deduplicate_slots_and_keep_outcome_tiers(sparse):
    kit = selected()
    kit["selection"]["entries"][0]["assignments"] = origins() + [
        {**origins()[-1], "slot": "duplicate.origin.different.slot"}]
    world = enroll(sparse, kit)
    canvas, authority, refs, run = world
    db = canvas.db_for("draft")
    before = read(db, "draft", "draft")
    assert len(before["cohorts"]) == 14
    assert all(c["rate"]["executions"] == 1 and c["rate"]["unknown"] == 1 for c in before["cohorts"])
    payload = {**SCOPE, "token": run["token"], "epoch": run["epoch"], "requestId": "origin-result",
        "result": {"summary": "Checked", "stepResults": [{"stepId": "s1", "status": "done",
                    "evidence": {"notes": "Isolated fixture"}}]}}
    receipt = authority.submit(run["executionId"], payload)
    assert authority.submit(run["executionId"], payload) == receipt
    reported = read(db, "draft", "draft")
    assert all(c["rate"]["pass"] == (c["tier"] == "reported") for c in reported["cohorts"])
    merged_link(world)
    confirm(world)
    assert all(c["rate"]["pass"] == 1 for c in read(db, "draft", "draft")["cohorts"])
    confirm(world, now=False)
    reopened = read(db, "draft", "draft", origin_scope="area", origin_node="opora:draft:draft:area")
    assert len(reopened["cohorts"]) == 2
    assert all(c["rate"]["executions"] == 1 for c in reopened["cohorts"])
    assert next(c for c in reopened["cohorts"] if c["tier"] == "verified")["rate"]["percent"] is None
    assert reopened["promotionAllowed"] is False and reopened["causalContribution"] is False
    assert "not verified ancestry" in reopened["originEvidence"]
    # No raw assignment, resource contents, private token, or live graph is returned.
    text = json.dumps(reopened)
    assert run["token"] not in text and kit["resources"][0]["content"] not in text
    assert read(db, "draft", "foreign")["cohorts"] == []
    assert read(db, "draft", "draft", node="foreign")["cohorts"] == []
    assert read(db, "draft", "draft", resource="foreign")["cohorts"] == []


def test_legacy_unknown_and_bounded_execution_window(learning_run, learning_plan):
    canvas, authority, refs, first = learning_run
    db = canvas.db_for("draft")
    before = read(db, "draft", "draft")
    assert all(c["origin"] == {"scope": "unknown", "node": None} for c in before["cohorts"])
    authority.release(first["executionId"], {**SCOPE, "token": first["token"], "epoch": first["epoch"]})
    # Existing native preparation/claim, not synthetic learning rows.
    claimed(learning_plan, request="origin-second")
    bounded = read(db, "draft", "draft", limit=1)
    assert bounded["limited"] and bounded["window"]["examined"] == 1
    assert all(c["rate"]["executions"] == 1 for c in bounded["cohorts"])


@pytest.mark.parametrize("field,value", [("assignment_digest", "bad"), ("kit_digest", "bad"),
                                        ("accepted_revision", "foreign"), ("node_id", "foreign")])
def test_mismatched_enrollment_excluded_not_reassigned(learning_run, field, value):
    canvas, _, _, _ = learning_run
    db = canvas.db_for("draft")
    with db:
        db.execute("UPDATE harness_learning_runs SET " + field + "=?", (value,))
    result = read(db, "draft", "draft")
    assert result["cohorts"] == [] and result["window"]["excluded"] == 1


def test_many_origin_cohorts_are_bounded_and_explicitly_truncated(sparse):
    kit = selected()
    kit["problems"] = ["problem." + str(i) for i in range(8)]
    kit["selection"]["problem"] = kit["problems"][0]
    kit["selection"]["entries"][0]["assignments"] = [
        {"slot": "slot." + str(i), "scope": "task", "node": "opora:draft:draft:" + str(i)}
        for i in range(32)]
    canvas, _, _, _ = enroll(sparse, kit)
    result = read(canvas.db_for("draft"), "draft", "draft")
    assert len(result["cohorts"]) == 100 and result["limited"]
    assert result["omittedCohortContributions"] == 412


@pytest.mark.parametrize("damage", ["missing", "assignment"])
def test_missing_or_corrupt_native_record_is_excluded(learning_run, damage):
    canvas, _, _, run = learning_run
    db = canvas.db_for("draft")
    with db:
        if damage == "missing":
            db.execute("DELETE FROM opora_executions WHERE id=?", (run["executionId"],))
        else:
            stored = json.loads(db.execute("SELECT record FROM opora_executions WHERE id=?",
                                           (run["executionId"],)).fetchone()[0])
            stored["assignment"]["documents"] = []
            db.execute("UPDATE opora_executions SET record=? WHERE id=?",
                       (json.dumps(stored), run["executionId"]))
    result = read(db, "draft", "draft")
    assert result["cohorts"] == [] and result["window"] == {
        "kind": "newest-enrolled-executions", "limit": 100, "examined": 1, "excluded": 1}


def test_registered_route_validates_scope_and_never_writes(learning_run):
    canvas, _, _, _ = learning_run
    app = FastAPI()
    app.include_router(create_harness_learning_router(canvas))
    with TestClient(app) as client:
        url = "/api/oporahub/harness-origin-history"
        result = client.get(url, params=SCOPE)
        assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
        assert len(result.json()["cohorts"]) == 2
        for extra in [{"limit": 101}, {"originScope": "wrong"}, {"originNode": "foreign"},
                      {"originScope": "global", "originNode": "foreign"}, {"resource": ""}]:
            assert client.get(url, params={**SCOPE, **extra}).status_code == 422
        assert client.get(url, params={**SCOPE, "project": "missing"}).status_code == 404
        assert client.post(url, json={"outcome": "pass"}).status_code == 405
