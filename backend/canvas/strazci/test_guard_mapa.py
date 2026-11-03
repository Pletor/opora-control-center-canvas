"""Strážce mapy: nálezy kontroly mapy jako nálezy strážce, přeskočení beze změny hlavy."""
import sqlite3
import threading
from contextlib import nullcontext
from types import SimpleNamespace

from backend.canvas.strazci import guard_mapa
from backend.canvas.strazci.registry import GuardContext
from backend.flow.page_intents import page_digest
from backend.flow.workflows import approve, create_draft, create_workflow, set_candidate
from database.schema.journey_run_schema import SCHEMA as JOURNEY_RUN_SCHEMA
from database.schema.project_schema import REGISTRY_SCHEMA, ensure_flow_owner_ref

INTENT = {"nodes": [{"id": "in", "type": "intent.entry"}, {"id": "ok", "type": "intent.done"}],
          "edges": [{"id": "1", "source_node": "in", "source_port": "main", "target_node": "ok", "target_port": "main"}]}


def fake_service(graph, source_kind="git"):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(JOURNEY_RUN_SCHEMA)
    registry = sqlite3.connect(":memory:", check_same_thread=False)
    registry.row_factory = sqlite3.Row
    registry.executescript(REGISTRY_SCHEMA)
    ensure_flow_owner_ref(registry)
    registry.execute("INSERT INTO projects(id,name) VALUES('p1','P')")
    return SimpleNamespace(project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourceKind": source_kind}}),
                           view=lambda project, wid: {"graph": graph}, db_for=lambda project: db,
                           reading=lambda project: nullcontext(), lock_for=lambda project: threading.RLock(),
                           db=registry, registry_lock=threading.RLock())


def graph():
    sections = [{"id": "hero"}, {"id": "cena"}]
    return {"nodes": [{"id": "app", "parentId": None, "kind": "sector", "site": {"kind": "application"}},
                      {"id": "p", "parentId": "app", "kind": "node", "site": {"kind": "page", "path": "/", "sections": sections}},
                      {"id": "a", "parentId": "p", "kind": "node"}, {"id": "b", "parentId": "p", "kind": "node"}],
            "edges": [{"id": "e1", "source": "a", "target": "b"}]}


def test_findings_get_stable_keys_severity_and_solver_card():
    service = fake_service(graph())
    found = guard_mapa.run(GuardContext(service, "p1", 0.0))
    by_key = {item["key"]: item for item in found}
    assert set(by_key) == {"map:page.no-goal:p", "map:section.unrealized:p:hero", "map:section.unrealized:p:cena",
                           "map:edge.carries-unset:e1", "map:page.no-intent:p"}
    assert by_key["map:page.no-intent:p"]["severity"] == "warn"
    assert by_key["map:page.no-goal:p"]["severity"] == "block"
    assert by_key["map:section.unrealized:p:hero"]["severity"] == "warn"
    edge = by_key["map:edge.carries-unset:e1"]
    assert edge["nodeId"] == "a" and edge["data"] == {"edgeId": "e1"} and edge["workspaceId"] == "main"


def test_unchanged_head_skips_and_a_change_runs_again():
    current = graph()
    service = fake_service(current)
    memo = {}
    assert guard_mapa.run(GuardContext(service, "p1", 0.0, memo)) is not None
    assert guard_mapa.run(GuardContext(service, "p1", 60.0, memo)) is None
    current["nodes"][1]["site"]["goal"] = "Prodat"
    again = guard_mapa.run(GuardContext(service, "p1", 120.0, memo))
    assert again is not None and "map:page.no-goal:p" not in {item["key"] for item in again}


def test_new_journey_run_changes_the_head():
    service = fake_service(graph(), source_kind="folder")
    memo = {}
    guard_mapa.run(GuardContext(service, "p1", 0.0, memo))
    service.db_for("p1").execute(
        "INSERT INTO journey_runs(project_id,application_id,journey_id,at_utc,plan_digest,passed,record,recorded_at)"
        " VALUES('p1','app','j1','2026-01-01T00:00:00Z','d',1,'{\"applicationId\":\"app\",\"journeyId\":\"j1\"}','x')")
    found = guard_mapa.run(GuardContext(service, "p1", 60.0, memo))
    assert found is not None and all(item["workspaceId"] == "draft" for item in found)


def test_journey_findings_block_on_broken_and_differ_per_message():
    found = guard_mapa.to_findings({"findings": [
        {"rule": "journey.broken", "journeyId": "j1", "message": "Cesta: chybí stránka.", "solverId": "app"},
        {"rule": "journey.unrealized", "journeyId": "j1", "message": "z / na /a", "solverId": "p"},
        {"rule": "journey.unrealized", "journeyId": "j1", "message": "z /a na /b", "solverId": "p"}]}, "main")
    assert found[0]["severity"] == "block" and found[0]["nodeId"] == "app" and found[0]["journeyId"] == "j1"
    assert found[1]["key"] != found[2]["key"] and found[1]["key"].startswith("map:journey.unrealized:j1:")


def test_approved_intent_changes_the_head_and_a_changed_page_blocks_as_stale():
    current = graph()
    service = fake_service(current)
    memo = {}
    guard_mapa.run(GuardContext(service, "p1", 0.0, memo))
    wid = create_workflow(service.db, "page_intent", "Záměr", project_id="p1", owner_ref="opora:page:p")["id"]
    version = set_candidate(service.db, create_draft(service.db, wid, INTENT)["id"])
    approve(service.db, version["id"], "human", page_digest(current["nodes"][1]["site"]))
    found = {item["key"] for item in guard_mapa.run(GuardContext(service, "p1", 60.0, memo))}
    assert "map:page.no-intent:p" not in found and "map:page.intent-stale:p" not in found
    current["nodes"][1]["site"]["path"] = "/jinam"
    stale = {item["key"]: item for item in guard_mapa.run(GuardContext(service, "p1", 120.0, memo))}
    assert stale["map:page.intent-stale:p"]["severity"] == "block"
