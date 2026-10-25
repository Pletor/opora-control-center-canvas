"""Trust boundaries, revision-safe votes, transaction rollback and retained projection."""
import copy
import sqlite3

import pytest

from backend.canvas import opora_event_projections
from backend.canvas.opora_card_events import closures
from backend.canvas.opora_events import emit_event
from backend.canvas.test_opora_execution_context import claimed
from backend.library.harness_learning import project_event
from backend.library.harness_learning_rates import read
from database.repositories import opora_events

HUMAN = {"kind": "human", "name": "Reviewer"}


def cohorts(world, tier="verified", **filters):
    service, _, _, _ = world
    return [row for row in read(service.db_for("draft"), "draft", "draft", **filters)["cohorts"] if row["tier"] == tier]


def merged_link(world):
    service, _, _, record = world
    db = service.db_for("draft")
    with db:
        db.execute("INSERT INTO opora_execution_pull_requests(project_id,workspace_id,execution_id,node_id,"
                   "accepted_revision,repository,number,head_ref,head_sha,state,enrollment,merge_sha,"
                   "awaiting_human_close,source,linked_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("draft", "draft", record["executionId"], record["nodeId"], record["acceptedRevision"],
                    "owner/repo", 7, "feature", "a" * 40, "merged", "enrolled", "b" * 40, 1,
                    "test-fixture", "human", "now", "now"))


def confirm(world, now=True):
    service, _, _, record = world
    db = service.db_for("draft")
    before = {"nodes": {record["nodeId"]: {"done": {"confirmed": not now, "by": "human"}}}}
    after = {"nodes": {record["nodeId"]: {"done": {"confirmed": now, "by": "human"}}}}
    with db:
        db.execute("BEGIN IMMEDIATE")
        closures(db, "draft", "draft", before, after, HUMAN)


def test_claim_enrolls_unknown_outcomes_and_report_is_not_verified(learning_run):
    _, authority, _, record = learning_run
    assert cohorts(learning_run)[0]["rate"] == {"pass": 0, "fail": 0, "unknown": 1, "executions": 1,
                                              "percent": None, "interval95": None, "coverage": 0.0}
    payload = {"project": "draft", "workspace": "draft", "token": record["token"], "epoch": record["epoch"],
               "requestId": "result", "result": {"summary": "Done", "stepResults": [{"stepId": "s1",
                   "status": "done", "evidence": {"notes": "Ran the checks"}}]}}
    receipt = authority.submit(record["executionId"], payload)
    assert authority.submit(record["executionId"], payload) == receipt
    assert cohorts(learning_run, "reported")[0]["rate"]["pass"] == 1
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1
    assert cohorts(learning_run)[0]["runner"] is None
    assert cohorts(learning_run)[0]["invocationObserved"] is False


def test_verified_close_and_reopening_revise_one_vote_then_retention_and_restart_preserve_it(learning_run):
    service, _, _, _ = learning_run
    merged_link(learning_run)
    confirm(learning_run)
    rate = cohorts(learning_run)[0]["rate"]
    assert rate["pass"] == 1 and rate["percent"] == 100 and 20 < rate["interval95"][0] < 21
    confirm(learning_run, now=False)
    assert cohorts(learning_run)[0]["rate"]["percent"] is None
    confirm(learning_run)
    assert cohorts(learning_run)[0]["rate"]["executions"] == 1
    db = service.db_for("draft")
    event = next(row for row in opora_events.page(db, "draft", None, 0, 500)[0] if row["kind"] == "decision.resolved")
    with db:
        db.execute("DELETE FROM opora_events")
        project_event(db, event["id"], event)  # Source identity survives outbox retention.
    assert cohorts(learning_run)[0]["rate"]["executions"] == 1
    file = db.execute("PRAGMA database_list").fetchone()[2]
    reopened = sqlite3.connect(file)
    try:
        assert read(reopened, "draft", "draft")["cohorts"] == read(db, "draft", "draft")["cohorts"]
    finally:
        reopened.close()


def test_external_verification_claims_and_unlinked_human_decisions_do_not_count(learning_run):
    service, _, _, record = learning_run
    db = service.db_for("draft")
    with db:
        emit_event(db, project_id="draft", workspace_id="draft", kind="decision.resolved",
                   node_id=record["nodeId"], execution_id=record["executionId"], actor=HUMAN,
                   data={"decision": "close_card"}, process={"source": "office"})
        emit_event(db, project_id="draft", workspace_id="draft", kind="decision.resolved",
                   node_id=record["nodeId"], execution_id=record["executionId"], actor=HUMAN,
                   data={"decision": "close_card"})
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1
    merged_link(learning_run)
    with db:
        emit_event(db, project_id="draft", workspace_id="draft", kind="decision.resolved",
                   node_id=record["nodeId"], execution_id=record["executionId"], actor={"kind": "agent"},
                   data={"decision": "close_card"})
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1


def test_source_and_projection_rollback_together(learning_plan, monkeypatch):
    graphs, _, _ = learning_plan
    def broken(_db, _event_id, _event):
        raise RuntimeError("Injected projection failure")
    monkeypatch.setattr(opora_event_projections, "PROJECTIONS", (*opora_event_projections.PROJECTIONS, broken))
    with pytest.raises(RuntimeError, match="Injected"):
        claimed(learning_plan)
    db = graphs.service.db_for("draft")
    for table in ("harness_learning_runs", "harness_learning_resources", "harness_learning_outcomes",
                  "harness_learning_sources", "opora_executions", "opora_execution_context_pins", "card_leases"):
        assert db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM opora_events WHERE kind='lease.claimed'").fetchone()[0] == 0


def test_scope_filters_do_not_leak_other_cards_or_workspaces(learning_run):
    assert cohorts(learning_run, node="other") == []
    assert cohorts(learning_run, resource="rule:other") == []
    service, _, _, _ = learning_run
    assert read(service.db_for("draft"), "draft", "other")["cohorts"] == []


def test_public_external_outbox_dto_cannot_be_replayed_as_native(learning_run):
    service, _, _, record = learning_run
    db = service.db_for("draft")
    merged_link(learning_run)
    fake = {"projectId": "draft", "workspaceId": "draft", "nodeId": record["nodeId"],
            "executionId": record["executionId"], "kind": "decision.resolved", "source": "office",
            "actor": HUMAN, "at": "now", "data": {"decision": "close_card"}}
    with db:
        db.execute("BEGIN IMMEDIATE")
        project_event(db, 999999, copy.deepcopy(fake))
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1
