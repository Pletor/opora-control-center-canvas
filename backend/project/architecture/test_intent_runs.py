"""Doklad přehrání záměru stránky (§6): tvar, verze, `stale`, append-only zápis a `intent.failed` do logu se srdcem."""

import json
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from backend.flow.workflows import approve, create_draft, create_workflow, set_candidate
from backend.project.architecture.intent_plan import IntentNotFound, page_intent_plan
from backend.project.architecture.intent_runs import IntentRunInvalid, record_intent_run
from database.schema.journey_run_schema import SCHEMA as JOURNEY_RUN_SCHEMA
from database.schema.opora_event_schema import SCHEMA as EVENT_SCHEMA
from database.schema.opora_event_schema import ensure_process_columns
from database.schema.project_schema import REGISTRY_SCHEMA, ensure_flow_owner_ref


def node(nid, kind, **params):
    return {"id": nid, "type": f"intent.{kind}", "params": params}


def edge(eid, source, target):
    return {"id": eid, "source_node": source, "source_port": "main", "target_node": target, "target_port": "main",
            "kind": "main"}


GRAPH = {"nodes": [node("in", "entry"), node("send", "action", do="submit", section="form"),
                   node("ok", "done", claim="Děkujeme", check="visible")],
         "edges": [edge("1", "in", "send"), edge("2", "send", "ok")]}


def intent_service():
    registry = sqlite3.connect(":memory:", check_same_thread=False)
    registry.row_factory = sqlite3.Row
    registry.executescript(REGISTRY_SCHEMA)
    ensure_flow_owner_ref(registry)
    registry.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    project = sqlite3.connect(":memory:", check_same_thread=False)
    project.executescript(JOURNEY_RUN_SCHEMA + EVENT_SCHEMA)
    ensure_process_columns(project)
    lock = threading.RLock()
    service = SimpleNamespace(db=registry, registry_lock=threading.RLock(), db_for=lambda pid: project,
                              lock_for=lambda pid: lock, view=lambda pid, wid: {"graph": {"nodes": []}},
                              project_hub=SimpleNamespace(settings=lambda pid: {"project": {"sourceKind": "git"}}))
    wid = create_workflow(registry, "page_intent", "Záměr", project_id="p", owner_ref="opora:page:landing")["id"]
    return service, wid


def publish(service, wid, graph=GRAPH):
    return approve(service.db, set_candidate(service.db, create_draft(service.db, wid, graph)["id"])["id"], "human")


def doklad(plan, **nodes):
    return {"schema": "opora.intent-run/1", "pageId": "landing", "workflowVersionId": plan["workflowVersionId"],
            "digest": plan["digest"], "nodes": [{"nodeId": key, **value} for key, value in nodes.items()]}


def failures(service):
    rows = service.db.execute("SELECT type, canvas, payload FROM flow_log_events WHERE type='intent.failed'")
    return [(row["canvas"], json.loads(row["payload"])) for row in rows]


def outbox(service):
    rows = service.db_for("p").execute("SELECT kind, workspace_id, data FROM opora_events").fetchall()
    return [(row[0], row[1], json.loads(row[2])) for row in rows]


def test_without_active_version_plan_and_run_are_404():
    service, _ = intent_service()
    with pytest.raises(IntentNotFound):
        page_intent_plan(service, "p", "landing")
    with pytest.raises(IntentNotFound):
        record_intent_run(service, "p", {"pageId": "landing", "workflowVersionId": "x", "digest": "d",
                                         "nodes": [{"nodeId": "ok", "ok": True}]})


def test_passing_run_is_stored_without_waking_the_heart():
    service, wid = intent_service()
    publish(service, wid)
    plan = page_intent_plan(service, "p", "landing")
    record = record_intent_run(service, "p", doklad(plan, send={"ok": True}, ok={"ok": True}))
    assert record["passed"] is True and record["stale"] is False and record["recordedAt"]
    assert failures(service) == [] and outbox(service) == []
    row = service.db_for("p").execute("SELECT page_id, stale, record FROM intent_runs").fetchone()
    assert row[:2] == ("landing", 0) and json.loads(row[2])["verification"].startswith("agent-reported")
    with pytest.raises(sqlite3.IntegrityError):
        service.db_for("p").execute("DELETE FROM intent_runs")


def test_failed_node_goes_to_the_canvas_log_and_wakes_the_heart():
    service, wid = intent_service()
    publish(service, wid)
    plan = page_intent_plan(service, "p", "landing")
    record = record_intent_run(service, "p", doklad(plan, send={"ok": True}, ok={"ok": False, "reason": "chybí text"}),
                               "agent")
    assert record["passed"] is False
    payload = {"pageId": "landing", "nodeId": "ok", "reason": "chybí text",
               "workflowVersionId": plan["workflowVersionId"]}
    assert failures(service) == [(2, {**payload, "project": "p", "author": "agent"})]
    [(kind, workspace, data)] = outbox(service)
    assert (kind, workspace) == ("canvas.failed", "main")
    assert data["canvas"] == 2 and data["kind"] == "intent.failed" and data["payload"] == payload


def test_unverified_node_needs_a_reason_and_does_not_fail_the_run():
    service, wid = intent_service()
    publish(service, wid)
    plan = page_intent_plan(service, "p", "landing")
    with pytest.raises(IntentRunInvalid):
        record_intent_run(service, "p", doklad(plan, send={"ok": True}, ok={"ok": None}))
    record = record_intent_run(service, "p", doklad(plan, send={"ok": True}, ok={"ok": None, "reason": "neověřeno"}))
    assert record["passed"] is True and failures(service) == []


def test_run_of_an_older_version_is_stale_and_silent():
    service, wid = intent_service()
    publish(service, wid)
    old = page_intent_plan(service, "p", "landing")
    publish(service, wid, {**GRAPH, "nodes": [*GRAPH["nodes"], node("v", "view", section="hero")]})
    record = record_intent_run(service, "p", doklad(old, send={"ok": False, "reason": "chybí formulář"}))
    assert record["stale"] is True and failures(service) == [] and outbox(service) == []


@pytest.mark.parametrize("change", [
    {"digest": "sha256:" + "0" * 64}, {"workflowVersionId": "neni"}, {"extra": 1}, {"schema": "jiny"},
    {"nodes": [{"nodeId": "cizi", "ok": True}]}, {"nodes": [{"nodeId": "ok", "ok": True}, {"nodeId": "ok", "ok": True}]},
    {"nodes": [{"nodeId": "ok", "ok": "ano"}]}, {"nodes": []},
])
def test_invalid_runs_are_422(change):
    service, wid = intent_service()
    publish(service, wid)
    with pytest.raises(IntentRunInvalid):
        record_intent_run(service, "p", {**doklad(page_intent_plan(service, "p", "landing"), ok={"ok": True}),
                                         **change})
