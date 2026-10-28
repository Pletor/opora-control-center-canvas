"""Strážce mapy: nálezy kontroly mapy jako nálezy strážce, přeskočení beze změny hlavy."""
import sqlite3
import threading
from contextlib import nullcontext
from types import SimpleNamespace

from backend.canvas.strazci import guard_mapa
from backend.canvas.strazci.registry import GuardContext
from database.schema.journey_run_schema import SCHEMA as JOURNEY_RUN_SCHEMA


def fake_service(graph, source_kind="git"):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(JOURNEY_RUN_SCHEMA)
    return SimpleNamespace(project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourceKind": source_kind}}),
                           view=lambda project, wid: {"graph": graph}, db_for=lambda project: db,
                           reading=lambda project: nullcontext(), lock_for=lambda project: threading.RLock())


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
                           "map:edge.carries-unset:e1"}
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
