"""Project initialization and backup restore preserve policy history across restarts."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService
from backend.canvas.migrate_architecture_backup import down
from backend.canvas.opora_review_policy_restore import TABLES
from database.repositories.opora_review_attempts import Attempts
from database.repositories.opora_review_policy import Policies
from database.repositories.test_opora_review_policy import content
from database.schema.project_schema import PROJECT_TABLES


def test_fresh_project_tables_and_factory_registration(tmp_path):
    app = create_app(tmp_path / "data")
    try:
        db = app.state.service.db_for("draft")
        for table in TABLES:
            assert PROJECT_TABLES[table] == "project_id"
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        with TestClient(app, base_url="http://127.0.0.1:8740") as client:
            response = client.get("/api/oporahub/review-policy", params={"project": "draft", "workspace": "draft"})
            assert response.status_code == 200, response.text
            assert response.json()["policyHead"] is None
    finally:
        app.state.service.close()


@pytest.mark.parametrize("kind", ["policy", "attempt"])
def test_restart_and_backup_down_cannot_erase_authority(tmp_path, monkeypatch, kind):
    root = tmp_path / "data"
    service = CanvasService(root)
    db = service.db_for("draft")
    with db:
        db.execute("BEGIN IMMEDIATE")
        if kind == "policy":
            record = Policies(db, "draft", "draft").activate(content(project="draft", workspace="draft"), None)
        else:
            record = Attempts(db, "draft", "draft").begin(1, {"repository": "owner/repo", "branch": "main"},
                                                          "a" * 40, None, "2026-10-21T00:00:00Z")
    service.close()
    fresh = CanvasService(root)
    try:
        db = fresh.db_for("draft")
        if kind == "policy":
            assert Policies(db, "draft", "draft").read(record["id"]) == record
        else:
            assert Attempts(db, "draft", "draft").read(record["sequence"]) == record
        def fail(*args):
            pytest.fail("Backup restore read an old backup before checking policy history")
        monkeypatch.setattr("backend.canvas.migrate_architecture_backup.read_manifest", fail)
        before = list(db.iterdump())
        for force in (False, True):
            with pytest.raises(ValueError, match="review policy"):
                down(fresh, "draft", "architecture-20261021T010000Z-12345678", force=force)
        assert list(db.iterdump()) == before
    finally:
        fresh.close()
