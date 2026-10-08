import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.card_checks import validate_checks
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed, send
from backend.canvas.test_canvas_plan_catalog import component
from backend.editor.agent_memory.test_completion_evidence import evidence


@pytest.mark.parametrize("extra", [
    {"checks": [{"id": "unit", "command": ""}]},
    {"checks": [{"id": "unit", "command": "test"}] * 2},
    {"checks": "test"}, {"goal_mode": "forever"}, {"goal_mode": "until_checks_pass"},
])
def test_invalid_checks(extra):
    with pytest.raises(ValueError):
        validate_checks({"kind": "node", **extra})


def test_plan_brief_version_and_restart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        plan = component()
        checks = [{"id": "unit", "command": "uv run pytest"}]
        plan["nodes"][0].update(checks=checks, goal_mode="until_checks_pass")
        response = send(client, digest, plan)
        assert response.status_code == 200, response.text
        node_id = response.json()["refs"]["component"]
        params = {**SCOPE, "nodeId": node_id}
        before = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert before["node"]["checks"] == checks
        assert before["node"]["goal_mode"] == "until_checks_pass"
        view = client.get("/api/view", params=SCOPE).json()
        next(n for n in view["graph"]["nodes"] if n["id"] == node_id)["checks"][0]["command"] = "uv run pytest backend"
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        after = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert before["contextVersion"] != after["contextVersion"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert client.get("/api/desktop-v3/node-brief", params=params).json()["node"]["checks"][0]["command"] == "uv run pytest backend"


def test_closure_rejects_wrong_command_or_missing_required_check(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        view = client.get("/api/view", params=SCOPE).json()
        next(n for n in view["graph"]["nodes"] if n["id"] == "n0")["checks"] = [{"id": "unit", "command": "uv run pytest backend"}]
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        node = stored["state"]["nodes"]["n0"]
        node["done"] = {"confirmed": True, "by": "human", "at": "2026-10-07T12:00:00Z", "note": "Verified"}
        node["evidence"] = evidence()
        # Karta s kontrolami nesmí mít merge jako N/A (upgrade-opora #31).
        node["evidence"]["merge"] = {"status": "passed", "url": "https://git.example/pr/1/merge", "note": "Merged"}
        payload = {**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]}
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json=payload).status_code == 409
        node["evidence"]["checksRun"][0].update(command="uv run pytest backend", checkId="other")
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json=payload).status_code == 409
        node["evidence"]["checksRun"][0]["checkId"] = "unit"
        response = client.post("/api/desktop-v3/state", headers=HEADERS, json=payload)
        assert response.status_code == 200, response.text
