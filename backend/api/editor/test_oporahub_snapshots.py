"""Historical specifications are server-captured content, not pointers to today's cards."""

import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.graph import digest

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}


def test_commit_freezes_saved_spec_and_readback_stays_unchanged_after_edit(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view", params=SCOPE).json()
        graph = {"nodes": [{"id": "component", "parentId": None, "kind": "node",
                            "name": "Přihlášení", "purpose": "Přístup uživatele", "x": 0, "y": 0}],
                 "edges": []}
        saved = client.post("/api/graph", headers=HEADERS,
                            json={**SCOPE, "graph": graph, "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        fields = {"goal": "Původní požadavek", "non_goals": "", "acceptance": "Přihlášení funguje"}
        saved = client.post("/api/node-spec", headers=HEADERS,
                            json={**SCOPE, "node": "component", "expected_revision": 0, "fields": fields})
        assert saved.status_code == 200, saved.text
        committed = client.post("/api/opora-commit", headers=HEADERS, json={
            **SCOPE, "scope": "component", "by": {"kind": "human", "name": "Tester"},
            "specificationSnapshot": {"forged": "Tento obsah server nesmí převzít"},
        })
        assert committed.status_code == 200, committed.text
        commit = committed.json()
        snapshot = commit["specificationSnapshot"]
        assert snapshot["contextVersion"] == digest(snapshot["specification"])
        assert "Původní požadavek" in json.dumps(snapshot, ensure_ascii=False)
        assert "forged" not in snapshot
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "component"}).json()
        assert brief["contextVersion"] == snapshot["contextVersion"]

        changed = client.post("/api/node-spec", headers=HEADERS, json={
            **SCOPE, "node": "component", "expected_revision": 1,
            "fields": {**fields, "goal": "Změněný požadavek"},
        })
        assert changed.status_code == 200, changed.text
        historical = client.get("/api/opora-commit", params={**SCOPE, "scope": "component", "id": commit["id"]})
        assert historical.status_code == 200, historical.text
        assert historical.json() == commit
        latest = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "component"}).json()
        assert latest["contextVersion"] != snapshot["contextVersion"]
