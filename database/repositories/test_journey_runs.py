"""Úložiště dokladů cest: tabulka vznikne s projektem (i ve starší project.sqlite) a čte se poslední doklad."""

import sqlite3

import pytest

from backend.canvas.canvas_service import CanvasService
from database.repositories.journey_runs import JourneyRunStore
from database.schema.project_initialization import initialize_project_schema


def record(journey, passed, at="2026-10-27T21:40:00Z"):
    return {"schema": "opora.journey-run/1", "applicationId": "web", "journeyId": journey,
            "planDigest": "sha256:" + "a" * 64, "command": "runner", "at": at,
            "segments": [{"from": "s1", "to": "s2", "ok": passed}], "passed": passed}


def test_project_database_has_the_table_and_latest_run_per_journey(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        db = service.db_for("draft")
        store = JourneyRunStore(db, "draft")
        with db:
            store.insert(record("kampan", False), "2026-10-27T21:40:00.000000+00:00", "r1")
            store.insert(record("kampan", True), "2026-10-27T21:40:00.000000+00:00", "r2")
            store.insert(record("kampan", False), "2026-10-27T20:00:00.000000+00:00", "r3")
            store.insert(record("poptavka", True), "2026-10-27T20:00:00.000000+00:00", "r4")
        latest = store.latest()
        assert {key: run["passed"] for key, run in latest.items()} == {("web", "kampan"): True, ("web", "poptavka"): True}
        assert JourneyRunStore(db, "jiny").latest() == {}
    finally:
        service.close()


def test_older_project_database_gets_the_table_on_open(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    db.execute("CREATE TABLE drafts(id TEXT PRIMARY KEY, graph TEXT)")
    initialize_project_schema(db)
    assert db.execute("SELECT name FROM sqlite_master WHERE name='journey_runs'").fetchone() is not None
    initialize_project_schema(db)  # opakované otevření nic nemění
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("INSERT INTO journey_runs(project_id) VALUES('x')")
    db.close()
