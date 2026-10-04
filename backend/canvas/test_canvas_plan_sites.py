"""One graph backs the Project app/page tree, Editor scope and agent specification."""
import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.graph import digest
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, send


def site_plan():
    return {"nodes": [
        {"ref": "app", "kind": "sector", "name": "Aplikace", "purpose": "Práce s účtem",
         "site": {"kind": "application", "environments": [
             {"name": "Produkce", "host": "app.example.cz"}, {"name": "Vývoj", "host": "localhost:3000"}]}},
        {"ref": "page", "kind": "node", "parent": "app", "name": "Přehled", "purpose": "Zobrazuje stav účtu",
         "site": {"kind": "page", "path": "/"}},
    ]}


def view(client):
    return client.get("/api/view", params=SCOPE).json()


def brief(client, identifier):
    response = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": identifier})
    assert response.status_code == 200, response.text
    return response.json()


def save_graph(client, graph, **extra):
    return client.post("/api/graph", headers=HEADERS,
                       json={**SCOPE, "graph": graph, "digest": view(client)["digest"], **extra})


def test_sites_roundtrip_editor_scope_and_immutable_snapshot(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        response = send(client, view(client)["digest"], site_plan())
        assert response.status_code == 200, response.text
        refs = response.json()["refs"]
        original = view(client)["graph"]
        nodes = {node["id"]: node for node in original["nodes"]}
        assert nodes[refs["page"]]["parentId"] == refs["app"]
        assert nodes[refs["app"]]["site"] == site_plan()["nodes"][0]["site"]
        before = brief(client, refs["page"])
        assert before["node"]["site"] == {"kind": "page", "path": "/"}
        assert before["node"]["purpose"] == "Zobrazuje stav účtu"
        assert before["goal"]["goal"] == ""  # Purpose is not silently copied into a work assignment.
        assert before["context"]["ancestors"][0]["site"]["kind"] == "application"
        assert digest(before["specification"]) == before["contextVersion"]
        committed = client.post("/api/opora-commit", headers=HEADERS, json={
            **SCOPE, "scope": refs["page"], "subject": "Struktura stránky",
            "by": {"kind": "human", "name": "test"},
        })
        assert committed.status_code == 200, committed.text
        frozen = committed.json()["specificationSnapshot"]
        assert frozen["contextVersion"] == before["contextVersion"]
        for kind in ("host", "path"):
            edited = copy.deepcopy(view(client)["graph"])
            if kind == "host":
                edited["nodes"][0]["site"]["environments"][0]["host"] = "new.example.cz"
            else:
                edited["nodes"][1]["site"]["path"] = "/overview"
            previous_version = brief(client, refs["page"])["contextVersion"]
            saved = save_graph(client, edited)
            assert saved.status_code == 200, saved.text
            assert brief(client, refs["page"])["contextVersion"] != previous_version
        assert frozen["specification"] == before["specification"]
        # Ordinary graph undo restores metadata and IDs without creating another page.
        restored = save_graph(client, original, undo=True)
        assert restored.status_code == 200, restored.text
        assert view(client)["graph"] == original
        assert brief(client, refs["page"])["contextVersion"] == before["contextVersion"]


def test_duplicate_route_plan_and_graph_edit_are_both_atomic(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        created = send(client, view(client)["digest"], site_plan()).json()
        before = view(client)
        failed = send(client, before["digest"], {"nodes": [{
            "ref": "duplicate", "kind": "node", "parent": "@" + created["refs"]["app"],
            "name": "Druhá stránka", "site": {"kind": "page", "path": "/"},
            "spec": {"goal": "This must not be written"},
        }]})
        assert failed.status_code == 409, failed.text
        assert view(client)["digest"] == before["digest"]
        assert app.state.service.db_for("draft").execute("SELECT COUNT(*) FROM node_spec_revisions").fetchone()[0] == 0
        broken = copy.deepcopy(before["graph"])
        broken["nodes"][0]["site"]["environments"][1]["host"] = "APP.EXAMPLE.CZ."
        assert save_graph(client, broken).status_code == 409
        assert view(client)["graph"] == before["graph"]
