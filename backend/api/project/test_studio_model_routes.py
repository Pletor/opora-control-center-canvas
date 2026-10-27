import sqlite3
import threading
from contextlib import nullcontext
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.project.studio_model_routes import create_studio_model_router
from backend.canvas.canvas_service import ProjectNotFound
from database.schema.studio_model_schema import SCHEMA as STUDIO_MODEL_SCHEMA

URL = "/api/studio/model"


def make_client():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(STUDIO_MODEL_SCHEMA)
    graph_reads = []

    def settings(project):
        if project == "nikdo":
            raise ProjectNotFound(project)
        return {"project": {"sourceKind": "git"}}

    def reading(project):
        settings(project)
        return nullcontext()

    def view(project, wid):
        graph_reads.append((project, wid))
        return {"graph": {"nodes": [{"id": "card"}], "edges": []}}

    service = SimpleNamespace(project_hub=SimpleNamespace(settings=settings), view=view,
                              db_for=lambda project: db, reading=reading, lock_for=lambda project: threading.RLock())
    app = FastAPI()
    app.include_router(create_studio_model_router(service))
    return TestClient(app), graph_reads


def body(revision=0, binding="card"):
    return {"schema": "opora.studio-model/1", "domainId": "web", "revision": revision,
            "nodes": [{"id": "a", "type": "api-gateway", "name": "Brána", "position": {"x": 0, "y": 0}, "config": {},
                       "binding": {"nodeId": binding}},
                      {"id": "b", "type": "service", "name": "Služba", "position": {"x": 300, "y": 0}, "config": {}}],
            "edges": [{"id": "e", "from": {"nodeId": "a", "portId": "http-out"},
                       "to": {"nodeId": "b", "portId": "http-in"}, "type": "http-request", "enabled": True, "label": ""}]}


def test_get_returns_empty_model_until_saved():
    client, _ = make_client()
    response = client.get(URL, params={"project": "p1", "domain": "web"})
    assert response.status_code == 200
    assert response.json() == {"schema": "opora.studio-model/1", "domainId": "web", "revision": 0, "nodes": [],
                               "edges": [], "updatedAt": None}
    assert client.get(URL, params={"project": "p1"}).status_code == 422
    assert client.get(URL, params={"project": "nikdo", "domain": "web"}).status_code == 404


def test_put_saves_with_revision_and_conflict_is_409():
    client, graph_reads = make_client()
    params = {"project": "p1", "domain": "web"}
    saved = client.put(URL, params=params, json=body())
    assert saved.status_code == 200 and saved.json()["revision"] == 1
    assert graph_reads == [("p1", "main")]  # graf se jen čte kvůli binding
    loaded = client.get(URL, params=params).json()
    assert loaded == saved.json() and loaded["nodes"][0]["binding"] == {"nodeId": "card"}
    stale = client.put(URL, params=params, json=body(revision=0))
    assert stale.status_code == 409 and "revize 1" in stale.json()["detail"]
    assert client.put(URL, params=params, json=body(revision=1)).json()["revision"] == 2


def test_put_rejects_shape_binding_size_and_json():
    client, _ = make_client()
    params = {"project": "p1", "domain": "web"}
    ghost = client.put(URL, params=params, json=body(binding="ghost"))
    assert ghost.status_code == 422 and "ghost" in ghost.json()["detail"]
    assert client.put(URL, params={"project": "p1", "domain": "jina"}, json=body()).status_code == 422
    assert client.put(URL, params=params, content=b"{nope",
                      headers={"content-type": "application/json"}).status_code == 422
    huge = body()
    huge["nodes"][1]["config"] = {"note": "x" * (1024 * 1024)}
    assert client.put(URL, params=params, json=huge).status_code == 413
    assert client.put(URL, params={"project": "nikdo", "domain": "web"}, json=body()).status_code == 404
    assert client.get(URL, params=params).json()["revision"] == 0
