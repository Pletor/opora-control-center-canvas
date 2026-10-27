"""Úložiště technického modelu Studia: tabulka vznikne s projektem (i ve starší project.sqlite), drží jednu verzi na doménu."""

import sqlite3

from backend.canvas.canvas_service import CanvasService
from database.repositories.studio_models import StudioModelStore
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_TABLES


def test_project_database_keeps_one_current_model_per_domain(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        db = service.db_for("draft")
        store = StudioModelStore(db, "draft")
        assert store.get("web") is None
        with db:
            store.put("web", 1, {"nodes": [], "name": "Žluťoučký"}, "t1")
            store.put("web", 2, {"nodes": [{"id": "a"}]}, "t2")
            store.put("admin", 1, {"nodes": []}, "t3")
        assert store.get("web") == (2, {"nodes": [{"id": "a"}]}, "t2")
        assert store.get("admin") == (1, {"nodes": []}, "t3")
        assert StudioModelStore(db, "jiny").get("web") is None
    finally:
        service.close()


def test_older_project_database_gets_the_table_on_open(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    db.execute("CREATE TABLE drafts(id TEXT PRIMARY KEY, graph TEXT)")
    initialize_project_schema(db)
    assert db.execute("SELECT name FROM sqlite_master WHERE name='studio_models'").fetchone() is not None
    assert PROJECT_TABLES["studio_models"] == "project_id"
    initialize_project_schema(db)  # opakované otevření nic nemění
    db.close()
