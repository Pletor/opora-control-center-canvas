import sqlite3
import time
from datetime import UTC, datetime
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.project.project_work_status_routes import create_project_work_status_router


def make_client():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE card_leases(project_id, workspace_id, node_id, owner, token, expires_at REAL);
        CREATE TABLE card_work_activity(project_id, workspace_id, node_id, agent, started_at, updated_at, touched);
    """)
    db.execute("INSERT INTO card_leases VALUES('p','w1','c1','agent','t',?)", (time.time() + 600,))
    db.execute("INSERT INTO card_work_activity VALUES('p','w1','c1','agent',NULL,?,NULL)",
               (datetime.now(UTC).isoformat(),))
    db.execute("INSERT INTO card_leases VALUES('p','w2','c2','agent','t',?)", (time.time() + 600,))
    db.commit()
    site = {"kind": "application", "environments": [{"name": "Vývoj", "host": "a.dev"}]}
    graph = {"nodes": [{"id": "dom", "name": "Aplikace", "site": site}, {"id": "c1", "name": "Karta"}]}

    @contextmanager
    def reading(project):
        yield

    service = SimpleNamespace(
        reading=reading, db_for=lambda project: db,
        project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourceKind": "git"}}),
        view=lambda project, wid: {"graph": graph},
        workspaces=lambda project: [{"id": "w1", "node_id": "dom", "branch": "work/w1", "actor": "a"},
                                    {"id": "w2", "node_id": "project", "branch": "work/w2", "actor": "b"}],
    )
    app = FastAPI()
    app.include_router(create_project_work_status_router(service))
    return TestClient(app)


def test_work_status_endpoint_shape():
    body = make_client().get("/api/project-architecture/work-status", params={"project": "p"}).json()
    assert set(body) == {"domains", "unassigned"}
    domain = body["domains"][0]
    assert domain["id"] == "dom" and domain["environment"] == {"name": "Vývoj", "host": "a.dev"}
    assert domain["counts"]["running"] == 1 and domain["counts"]["total"] == 1
    assert domain["worktrees"][0]["cards"] == [{"nodeId": "c1", "name": "Karta"}]
    assert body["unassigned"][0]["id"] == "w2" and body["unassigned"][0]["state"] == "waiting"