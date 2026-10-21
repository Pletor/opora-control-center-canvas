"""Actual factory/middleware/schema enforce human controls and durable migration guards."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.opora_review_evidence import OporaReviewEvidence
from backend.canvas.test_opora_review_fixtures import AGENT, Reader, setup
from database.schema.opora_reconciliation_jobs import JOB_TABLES
from database.schema.opora_reconciliation_schema import RECONCILIATION_TABLES
from database.schema.project_schema import PROJECT_TABLES

ORIGIN = "http://127.0.0.1:8740"
PREFIX = "/api/oporahub/reconciliation"
HEADERS = {"origin": ORIGIN}


def test_factory_human_authority_candidate_enroll_replay_and_history(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    from backend.canvas.test_canvas_service import managed_fixture
    fixture, project = managed_fixture(tmp_path)
    fixture.close()
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        service = app.state.service
        # Native draft deliberately has no repository, but identity rejection precedes domain access.
        bad = {"project": "draft", "workspace": "draft", "requestId": "test"}
        client.cookies.clear()
        assert client.post(PREFIX + "/bindings", headers=HEADERS, json=bad).status_code == 428
        assert client.post(PREFIX + "/bindings", headers={**HEADERS, "X-Opora-Actor": "agent; name=test"}, json=bad).status_code == 403
        assert client.get("/api/access/ui-session", headers={"sec-fetch-site": "same-origin", "sec-fetch-mode": "cors"}).status_code == 200
        # Real managed git project, matching normal repository fixture setup.
        assert client.post(PREFIX + "/bindings", headers=HEADERS, json={**bad, "by": {"kind": "human"}}).status_code == 409
        response = client.get(PREFIX, params={"project": "draft", "workspace": "draft"})
        assert response.status_code == 200 and response.json()["items"] == []
        db = service.db_for("draft")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {*RECONCILIATION_TABLES, *JOB_TABLES} <= tables
        assert {*RECONCILIATION_TABLES, *JOB_TABLES} <= PROJECT_TABLES.keys()
        payload = setup(service, project["id"])
        reader = Reader(payload)
        reader.result["pr"].update(baseSha="f" * 40, state="open", draft=False)
        reader.result["repository"]["fullName"] = "owner/repo"
        snapshot = OporaReviewEvidence(service, reader).observe(payload, AGENT)["snapshot"]
        scope = {k: payload[k] for k in ("project", "workspace")}
        summary = client.get(PREFIX + "/candidate", params={**scope, "evidenceId": snapshot["id"]})
        assert summary.status_code == 200 and summary.json()["canConfigure"]
        enrollment = {**scope, "expectedAcceptedHead": payload["expectedAcceptedHead"],
                      "identityEvidenceId": snapshot["id"], "requestId": "human-enroll"}
        created = client.post(PREFIX + "/bindings", headers=HEADERS, json=enrollment)
        assert created.status_code == 200, created.text
        assert client.post(PREFIX + "/bindings", headers=HEADERS, json=enrollment).json() == created.json()
        binding_id = created.json()["binding"]["id"]
        malformed_action = client.post(PREFIX + f"/{binding_id}/control", headers=HEADERS,
            json={**scope, "expectedGeneration": 1, "action": [], "requestId": "invalid-action"})
        assert malformed_action.status_code == 409
        huge_cursor = client.get(PREFIX + f"/{binding_id}/history", params={**scope, "cursor": str(10 ** 100)})
        assert huge_cursor.status_code == 409
        history = client.get(PREFIX + f"/{binding_id}/history", params=scope)
        assert history.status_code == 200 and len(history.json()["items"]) == 2
        foreign = client.get(PREFIX + f"/{binding_id}/history", params={**scope, "workspace": "main"})
        assert foreign.status_code == 409
        archived = client.post(f"/api/workspaces/{scope['workspace']}/archive", headers=HEADERS,
                               json={"project": scope["project"], "reason": "Archived after enrollment", "confirmed": True})
        assert archived.status_code == 200, archived.text
        archived_history = client.get(PREFIX + f"/{binding_id}/history", params=scope)
        assert archived_history.status_code == 200 and len(archived_history.json()["items"]) == 2
        archived_status = client.get(PREFIX, params=scope).json()
        assert not archived_status["canConfigure"] and archived_status["canPause"]
        assert archived_status["items"][0]["binding"] == created.json()["binding"]
        paused = client.post(PREFIX + f"/{binding_id}/control", headers=HEADERS,
                             json={**scope, "expectedGeneration": 1, "action": "pause", "requestId": "pause-archived"})
        assert paused.status_code == 200 and paused.json()["job"]["state"] == "paused"
        resume = client.post(PREFIX + f"/{binding_id}/control", headers=HEADERS,
                             json={**scope, "expectedGeneration": 2, "action": "resume", "requestId": "resume-archived"})
        assert resume.status_code == 409


def test_old_backup_guard_checks_every_new_table(tmp_path):
    import sqlite3

    import pytest

    from backend.canvas.opora_reconciliation_restore import refuse_reconciliation_restore
    from database.schema.opora_reconciliation_jobs import JOB_SCHEMA
    from database.schema.opora_reconciliation_schema import RECONCILIATION_SCHEMA
    db = sqlite3.connect(tmp_path / "old.sqlite")
    db.executescript(RECONCILIATION_SCHEMA + JOB_SCHEMA)
    refuse_reconciliation_restore(db)
    for table in (*RECONCILIATION_TABLES, *JOB_TABLES):
        columns = list(db.execute(f"PRAGMA table_info({table})"))
        names = [row[1] for row in columns]
        values = [row[4] if row[4] is not None else "1" for row in columns]
        with db:
            db.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", values)
        with pytest.raises(ValueError, match="restore"):
            refuse_reconciliation_restore(db)
        db.execute(f"DELETE FROM {table}")
        db.commit()
    db.close()
