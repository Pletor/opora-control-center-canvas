"""Kdo je člověk (upgrade-opora #29, #30): exploity z kritiky musí narazit.

Testovací klient nese doklad UI z backend/conftest.py; „neznámý“ volající ho smaže.
"""
import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.editor.agent_memory.test_completion_evidence import evidence

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=lazy"}
BROWSER = {"sec-fetch-site": "same-origin", "sec-fetch-mode": "cors"}


def stored(client):
    return client.get("/api/desktop-v3/state", params=SCOPE).json()


def close_as(client, headers, by="human"):
    current = stored(client)
    state = copy.deepcopy(current["state"])
    state["nodes"]["n0"]["done"] = {"confirmed": True, "by": by, "at": "2026-10-07T12:00:00Z", "note": "x"}
    state["nodes"]["n0"]["evidence"] = evidence()
    return client.post("/api/desktop-v3/state", headers=headers,
                       json={**SCOPE, "expectedRevision": current["revision"], "state": state})


def test_ui_session_is_issued_only_to_browser_fetch(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        client.cookies.clear()
        assert client.get("/api/access/ui-session").status_code == 403
        issued = client.get("/api/access/ui-session", headers=BROWSER)
        assert issued.status_code == 200
        cookie = issued.headers["set-cookie"].lower()
        assert "opora_ui=" in cookie and "httponly" in cookie and "samesite=strict" in cookie


def test_missing_actor_header_is_unknown_not_human(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        client.cookies.clear()
        payload = {**SCOPE, "sectorId": "s0", "nodeIds": ["n0"], "expectedRevision": stored(client)["revision"]}
        response = client.post("/api/desktop-v3/confirm-proposals", headers=HEADERS, json=payload)
        assert response.status_code == 428 and response.json()["humanRequired"] is True
        assert close_as(client, HEADERS).status_code == 428
        log = client.get("/api/activity-log", params={**SCOPE, "actor": "unknown"}).json()["entries"]
        assert {entry["path"] for entry in log} >= {"/api/desktop-v3/confirm-proposals", "/api/desktop-v3/state"}


def test_agent_cannot_close_card_as_human_through_generic_state(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        for by in ("human", "autonomy"):
            assert close_as(client, AGENT, by).status_code == 403
        assert not stored(client)["state"]["nodes"]["n0"].get("done", {}).get("confirmed")
        # Člověk se stejným zápisem projde; agent pak kartu ani neotevře, ani nevypustí.
        assert close_as(client, HEADERS).status_code == 200
        current = stored(client)
        reopened = copy.deepcopy(current["state"])
        reopened["nodes"]["n0"]["done"]["confirmed"] = False
        assert client.post("/api/desktop-v3/state", headers=AGENT,
                           json={**SCOPE, "expectedRevision": current["revision"], "state": reopened}).status_code == 403
        dropped = copy.deepcopy(current["state"])
        del dropped["nodes"]["n0"]
        assert client.post("/api/desktop-v3/state", headers=AGENT,
                           json={**SCOPE, "expectedRevision": current["revision"], "state": dropped}).status_code == 403


def test_agent_cannot_rewrite_gate_or_checks_of_existing_cards(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        view = client.get("/api/view", params=SCOPE).json()
        graph = copy.deepcopy(view["graph"])
        graph["nodes"][1]["checks"] = [{"id": "unit", "command": "uv run pytest"}]
        human = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]})
        assert human.status_code == 200, human.text
        view = human.json()
        weakened = copy.deepcopy(view["graph"])
        weakened["nodes"][1]["checks"] = [{"id": "unit", "command": "true"}]
        response = client.post("/api/graph", headers=AGENT, json={**SCOPE, "graph": weakened, "digest": view["digest"]})
        assert response.status_code == 403 and "n0.checks" in response.json()["error"]
        gated = copy.deepcopy(view["graph"])
        gated["nodes"][0]["gateNodeId"] = "n0"
        assert client.post("/api/graph", headers=AGENT, json={**SCOPE, "graph": gated, "digest": view["digest"]}).status_code == 403
        # Běžná úprava karty (název) agentovi dál projde.
        renamed = copy.deepcopy(view["graph"])
        renamed["nodes"][1]["name"] = "Přejmenovaná karta"
        assert client.post("/api/graph", headers=AGENT, json={**SCOPE, "graph": renamed, "digest": view["digest"]}).status_code == 200


def test_restore_of_canvas_version_is_human_only(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        response = client.post("/api/canvas-versions/restore", headers=AGENT,
                               json={**SCOPE, "versionId": "v1", "digest": "x", "expectedToken": "x", "author": "lazy"})
        assert response.status_code == 403
