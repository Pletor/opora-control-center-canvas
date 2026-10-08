from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_graph_source_ref import node, sector, view, post_graph
from backend.project.workspace.test_workspace_sources import attach, ORIGIN
from backend.editor.agent_memory.test_completion_evidence import evidence


def test_planned_empty_path_is_unspecified_not_the_existing_root(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        graph = {"nodes": [sector(purpose="Plánovaný adresář výstupů projektu", source_ref={"origin": "planned", "path": "", "kind": "directory"})], "edges": []}
        saved = post_graph(client, pid, graph, view(client, pid)["digest"])
        assert saved.status_code == 200, saved.text
        result = client.get("/api/desktop-v3/source-status", params={"project": pid, "workspace": "draft"})
        assert result.status_code == 200
        assert result.json()["nodes"][graph["nodes"][0]["id"]]["status"] == "unspecified"


def test_realization_requires_merge_and_disk_then_tracks_disappearance(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft"}
        graph = {"nodes": [sector(), node(source_ref={"origin": "planned", "path": "result.py", "kind": "file"})], "edges": []}
        assert post_graph(client, pid, graph, view(client, pid)["digest"]).status_code == 200
        payload = {**scope, "nodeId": "node-1", "digest": view(client, pid)["digest"], "commit": "abc1234", "prUrl": "https://git.example/pr/1"}
        def realize():
            return client.post("/api/desktop-v3/realize-source", headers={"origin": ORIGIN}, json=payload)
        assert realize().status_code == 409
        stored = client.get("/api/desktop-v3/state", params=scope).json()
        proof = evidence()
        proof["merge"] = {"status": "passed", "url": payload["prUrl"], "note": "Merged"}
        stored["state"]["nodes"]["node-1"] = {"phase": "discover", "criteria": [], "steps": [], "evidence": proof}
        assert client.post("/api/desktop-v3/state", headers={"origin": ORIGIN}, json={**scope, "expectedRevision": stored["revision"], "state": stored["state"]}).status_code == 200
        assert realize().status_code == 409
        assert view(client, pid)["digest"] == payload["digest"]
        (source / "result.py").write_text("pass", encoding="utf-8")
        result = realize()
        assert result.status_code == 200, result.text
        changed = next(n for n in view(client, pid)["graph"]["nodes"] if n["id"] == "node-1")
        assert changed["sourceRef"]["origin"] == "existing"
        assert changed["realization"]["commit"] == "abc1234"
        assert realize().status_code == 409
        assert client.get("/api/desktop-v3/source-status", params=scope).json()["nodes"]["node-1"]["status"] == "present"
        (source / "result.py").unlink()
        assert client.get("/api/desktop-v3/source-status", params=scope).json()["nodes"]["node-1"]["status"] == "missing"
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        brief = client.get("/api/desktop-v3/node-brief", params={**scope, "nodeId": "node-1"}).json()
        assert brief["node"]["realization"]["prUrl"] == payload["prUrl"]
