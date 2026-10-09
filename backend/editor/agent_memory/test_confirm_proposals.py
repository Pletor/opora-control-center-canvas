import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.editor.agent_memory.test_completion_evidence import evidence


def test_batch_confirmation_is_scoped_atomic_human_and_revision_guarded(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        view = client.get("/api/view", params=SCOPE).json()
        sibling = {**view["graph"]["nodes"][1], "id": "n1"}
        outside = {**sibling, "id": "outside", "parentId": None}
        view["graph"]["nodes"].extend([sibling, outside])
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        for node_id in ("n0", "n1", "outside"):
            stored["state"]["nodes"].setdefault(node_id, {"phase": "discover", "criteria": [], "steps": []})["done"] = {
                "by": "agent", "confirmed": False, "note": "Ready for review", "at": "2026-10-07T12:00:00Z"}
            stored["state"]["nodes"][node_id]["evidence"] = evidence()
        saved = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]}).json()
        payload = {**SCOPE, "sectorId": "s0", "nodeIds": ["n0", "n1"], "expectedRevision": saved["revision"]}
        def post(value, headers=HEADERS):
            return client.post("/api/desktop-v3/confirm-proposals", headers=headers, json=value)
        assert post(payload, {**HEADERS, "X-Opora-Actor": "agent; name=test"}).status_code == 403
        invalid = copy.deepcopy(payload)
        invalid["nodeIds"][1] = "outside"
        assert post(invalid).status_code == 409
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"] == saved["revision"]
        result = post(payload)
        assert result.status_code == 200, result.text
        state = result.json()["state"]
        assert all(state["nodes"][n]["done"]["confirmed"] for n in ("n0", "n1"))
        assert not state["nodes"]["outside"]["done"]["confirmed"]
        assert post(payload).status_code == 409
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        nodes = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]
        assert all(nodes[n]["done"]["by"] == "human" for n in ("n0", "n1"))
