import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed, send
from backend.canvas.test_canvas_plan_catalog import component
from backend.editor.agent_memory.test_completion_evidence import evidence


def test_downloader_plan_adds_required_block_and_cannot_close_without_it(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        plan = component()
        plan["nodes"][0]["downloadsUrl"] = True
        result = send(client, digest, plan)
        assert result.status_code == 200, result.text
        node_id = result.json()["refs"]["component"]
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        original = stored["state"]
        secure = next(b for b in original["nodes"][node_id]["blocks"] if "input-security" in b["tags"])
        assert secure["title"] == "Bezpečnost vstupu" and "SSRF" in secure["state"]["condition"]
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": node_id}).json()
        assert brief["node"]["downloadsUrl"] is True
        def save(state):
            return client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": state, "expectedRevision": stored["revision"]})
        removed = copy.deepcopy(original)
        removed["nodes"][node_id]["blocks"] = [b for b in removed["nodes"][node_id]["blocks"] if b["id"] != secure["id"]]
        assert save(removed).status_code == 409
        finished = copy.deepcopy(original)
        finished["nodes"][node_id].update(evidence=evidence(), done={"confirmed": True, "by": "human", "at": "2026-10-07T12:00:00Z", "note": "Verified"})
        assert save(finished).status_code == 409
        next(b for b in finished["nodes"][node_id]["blocks"] if b["id"] == secure["id"])["state"]["status"] = "met"
        saved = save(finished)
        assert saved.status_code == 200, saved.text
