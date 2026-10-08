from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.editor.agent_memory.test_completion_evidence import evidence


def overview(client):
    result = client.get("/api/desktop-v3/work-overview", params=SCOPE)
    assert result.status_code == 200, result.text
    return result.json()


def output(client, status, proposed, touched):
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()
    return client.post("/api/desktop-v3/agent-output", headers=HEADERS, json={
        **brief["outputContract"]["request"], "agent": "worker", "output": {
            "schema": "opora.agent-output/1", "blocks": [{"blockId": "b0", "status": status, "note": "Need review"}],
            "reports": [], "decisions": [], "done": {"proposed": proposed, "note": "Ready"},
            "touched": touched, "evidence": evidence()}})


def test_lifecycle_and_touched_are_atomic_and_persisted(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert overview(client)["nodes"]["n0"]["status"] == "waiting"
        claim = client.post("/api/desktop-v3/lease", headers=HEADERS, json={**SCOPE, "nodeId": "n0", "op": "claim", "owner": "worker", "ttlSeconds": 60})
        assert claim.status_code == 200
        claimed = overview(client)["nodes"]["n0"]
        assert claimed["status"] == "claimed" and claimed["startedAt"] and claimed["touched"] is None
        heartbeat = {**SCOPE, "nodeId": "n0", "op": "heartbeat", "token": claim.json()["token"], "ttlSeconds": 60, "touched": ["src/one.py"]}
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=heartbeat).status_code == 200
        working = overview(client)["nodes"]["n0"]
        assert working["startedAt"] == claimed["startedAt"]
        assert working["lastActivity"] >= claimed["lastActivity"] and working["touched"] == ["src/one.py"]
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json={**heartbeat, "token": "0" * 64, "touched": []}).status_code == 409
        assert overview(client)["nodes"]["n0"] == working
        assert output(client, "blocked", False, ["src/one.py"]).status_code == 200
        waiting = overview(client)["nodes"]["n0"]
        assert waiting["status"] == "waiting-human" and waiting["touched"] == ["src/one.py"]
        before = overview(client)
        assert output(client, "met", True, ["../outside"]).status_code == 409
        assert overview(client) == before
        assert output(client, "met", True, ["src/one.py", "tests/test_one.py"]).status_code == 200
        assert overview(client)["nodes"]["n0"]["status"] == "proposed"
        assert overview(client)["sectors"]["s0"]["proposed"] == 1
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        stored["state"]["nodes"]["n0"]["done"].update(confirmed=True, by="human")
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]}).status_code == 200
        assert overview(client)["nodes"]["n0"]["status"] == "done"
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        restored = overview(client)["nodes"]["n0"]
        assert restored["touched"] == ["src/one.py", "tests/test_one.py"]
        assert restored["agent"] == "worker"
