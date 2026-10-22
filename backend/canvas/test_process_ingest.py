"""Office events enter the OporaHub outbox: validation, dedupe, scope, no card refresh, health, bridge."""
import sqlite3

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_events import PROCESS_SIGNAL, emit_event
from backend.canvas.process_activity_bridge import bridge, bridged_kind
from backend.canvas.process_ingest import health, ingest
from database.repositories import opora_events as store
from database.schema.opora_event_schema import SCHEMA, ensure_process_columns


@pytest.fixture
def service(tmp_path):
    instance = CanvasService(tmp_path / "data")
    yield instance
    instance.close()


def office(seq, **overrides):
    return {"schema": "opora.process-event/1", "id": f"office:f1:{seq}", "seq": seq, "at": "2026-10-22T10:00:00Z",
            "source": "office", "kind": "tool.use", "phase": "work", "state": "progress", "title": f"krok {seq}",
            "actor": {"kind": "worker", "id": "w1", "name": "Ada"},
            "refs": {"project": "draft", "workspace": "draft", "cardId": "a", "executionId": "e1"},
            "tool": {"name": "Edit", "action": "edit", "target": "src/a.ts"}, **overrides}


def page(service):
    return store.page(service.db_for("draft"), "draft", "draft", 0, 100)[0]


def test_ingest_writes_outbox_rows_with_process_fields(service):
    generation = PROCESS_SIGNAL.generation
    result = ingest(service, {"events": [office(1), office(1), office(2, refs={"project": "draft"}),
                                         office(3, refs={"project": "nope", "workspace": "draft"}),
                                         office(4, refs={"project": "draft", "workspace": "ghost"}), office(5)]},
                    poster="office-process")
    assert result["accepted"] == 2 and result["duplicates"] == 1
    assert [item["index"] for item in result["rejected"]] == [2, 3, 4]
    assert PROCESS_SIGNAL.generation > generation
    assert ingest(service, {"events": [office(5)]}) == {"accepted": 0, "duplicates": 1, "rejected": []}
    events = page(service)
    # tool.use never refreshes the card: no stage.changed alongside office events
    assert [event["kind"] for event in events] == ["tool.use", "tool.use"]
    first = events[0]
    assert (first["source"], first["phase"], first["state"], first["title"]) == ("office", "work", "progress", "krok 1")
    assert first["eventId"] == "office:f1:1" and first["nodeId"] == "a" and first["executionId"] == "e1"
    assert first["tool"] == {"name": "Edit", "action": "edit", "target": "src/a.ts"}
    assert first["actor"] == {"kind": "agent", "name": "Ada"}
    assert first["data"] == {"actor": {"kind": "worker", "id": "w1", "name": "Ada"}, "seq": 1,
                             "sourceAt": "2026-10-22T10:00:00Z"}
    with pytest.raises(ValueError):
        ingest(service, {"events": []})


def test_opora_and_office_share_one_cursor(service):
    ingest(service, {"events": [office(1)]})
    emit_event(service, project_id="draft", workspace_id="draft", kind="merge.done", pr_number=3)
    ingest(service, {"events": [office(2)]})
    events = page(service)
    assert [(event["source"], event["kind"]) for event in events] == [
        ("office", "tool.use"), ("opora", "merge.done"), ("office", "tool.use")]
    assert [event["id"] for event in events] == sorted(event["id"] for event in events)
    assert events[1]["phase"] == "merge" and events[1]["refs"]["pr"] == 3


def test_health_reports_source_ages(service):
    result = health(service, "draft", "draft", memory_status={"status": "disabled"})
    assert result["officeConnected"] is False and result["sources"]["office"]["lastAt"] is None
    ingest(service, {"events": [office(1)]})
    emit_event(service, project_id="draft", workspace_id="draft", kind="merge.done")
    result = health(service, "draft", "draft", memory_status={"status": "disabled"})
    assert result["officeConnected"] is True and result["sources"]["office"]["ageSeconds"] < 60
    assert result["sources"]["opora"]["ageSeconds"] < 60 and result["sources"]["github"]["lastAt"] is None
    assert result["memory"] == {"status": "disabled"}


def test_bridge_only_adds_what_the_outbox_lacks(service):
    assert bridged_kind("POST", "/api/memory/remember", 200) == "memory.write"
    assert bridged_kind("POST", "/api/memory/recall", 409) is None
    assert bridged_kind("POST", "/api/desktop-v3/lease", 200) is None  # leases emit their own events
    described = {"project": "draft", "workspace": "draft", "nodeIds": ["a"], "summary": ""}
    bridge(service, method="POST", path="/api/memory/recall", status=200, actor="agent", agent="Claude",
           described=described)
    bridge(service, method="POST", path="/api/memory/recall", status=200, actor="agent", agent="Claude",
           described={**described, "project": "nope"})
    events = page(service)
    assert [(event["kind"], event["phase"], event["actor"]["name"]) for event in events] == [
        ("memory.recall", "memory", "Claude")]


def test_process_columns_migrate_an_old_outbox():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    db.execute("INSERT INTO opora_events(at,project_id,workspace_id,kind,actor_kind,data)"
               " VALUES('2026-01-01T00:00:00.000Z','p','w','merge.done','system','{}')")
    ensure_process_columns(db)
    ensure_process_columns(db)  # idempotent
    events = store.page(db, "p", "w", 0, 10)[0]
    assert events[0]["source"] == "opora" and events[0]["phase"] == "merge" and events[0]["tool"] is None
