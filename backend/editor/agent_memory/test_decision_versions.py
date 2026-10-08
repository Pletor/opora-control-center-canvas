import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.editor.agent_memory.test_memory_items import decision, write
from backend.editor.agent_memory.decision_versions import validate_versions


def test_correction_preserves_original_rejects_forks_and_warns_successor(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        view = client.get("/api/view", params=SCOPE).json()
        view["graph"]["nodes"].append({"id": "next", "parentId": "s0", "kind": "node", "name": "Next", "purpose": "", "x": 500, "y": 0})
        view["graph"]["edges"].append({"id": "edge", "source": "n0", "target": "next", "port": "block", "sourceBlockId": "b0", "sourcePortId": "p0"})
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        original = {**decision("old", "Empty database"), "nodeId": "n0"}
        assert write(client, "decision", "add", None, original).status_code == 200
        params = {**SCOPE, "nodeId": "next"}
        before = client.get("/api/desktop-v3/node-brief", params=params).json()
        corrected = {**original, "id": "new", "text": "RLS hides rows", "supersedes": "old"}
        saved = write(client, "decision", "add", None, corrected)
        assert saved.status_code == 200, saved.text
        after = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert after["contextVersion"] != before["contextVersion"]
        upstream = after["context"]["upstreamDecisions"][0]
        assert upstream["assumptionChanged"] is True
        assert upstream["decisions"] == [original, corrected]
        assert write(client, "decision", "add", None, {**corrected, "id": "fork"}).status_code == 409
        assert write(client, "decision", "update", original, {**original, "text": "Overwrite"}).status_code == 409
        assert write(client, "decision", "remove", original, None).status_code == 409
        assert write(client, "decision", "remove", corrected, None).status_code == 409
        assert write(client, "decision", "update", corrected, {k: v for k, v in corrected.items() if k != "supersedes"}).status_code == 409
        assert write(client, "decision", "add", None, {**corrected, "id": "third", "supersedes": "new"}).status_code == 200
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert len(client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["decisions"]) == 3


@pytest.mark.parametrize("items", [
    [{**decision("a"), "supersedes": "missing"}],
    [{**decision("a"), "supersedes": "b"}, {**decision("b"), "supersedes": "a"}],
    [decision("a"), {**decision("b"), "supersedes": "a", "nodeId": "other"}],
])
def test_invalid_chain(items):
    with pytest.raises(ValueError):
        validate_versions(items)
