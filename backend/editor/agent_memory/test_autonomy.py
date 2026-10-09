from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.editor.agent_memory import agent_output
from backend.editor.agent_memory.test_completion_evidence import evidence


def grant(client, **overrides):
    stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
    return {**SCOPE, "sectorId": "s0", "expectedRevision": stored["revision"],
            "until": (datetime.now(UTC) + timedelta(hours=1)).isoformat(), "note": "Approved", "grantedBy": "Reviewer", **overrides}


def full_evidence():
    """Autonomie nepřijme N/A (upgrade-opora #31/#32): tests, review i merge passed."""
    value = evidence()
    value["merge"] = {"status": "passed", "url": "https://git.example/pr/1/merge", "note": "Merged"}
    return value


def prepared(client):
    """Seed + předepsaná kontrola karty n0 (zapisuje člověk; agent ji měnit nesmí)."""
    seed(client)
    view = client.get("/api/view", params=SCOPE).json()
    next(node for node in view["graph"]["nodes"] if node["id"] == "n0")["checks"] = [{"id": "unit", "command": "uv run pytest"}]
    saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]})
    assert saved.status_code == 200, saved.text


def output(client, status="met", confirmed=True, value=None):
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()
    return client.post("/api/desktop-v3/agent-output", headers={**HEADERS, "X-Opora-Actor": "agent"}, json={
        **brief["outputContract"]["request"], "agent": "worker", "output": {
            "schema": "opora.agent-output/1", "blocks": [{"blockId": "b0", "status": status, "note": "Test passed"}],
            "evidence": value or full_evidence(), "ports": [], "reports": [], "decisions": [],
            "done": {"proposed": True, "confirmed": confirmed, "note": "Verified"}}})


def complete(client, status="met"):
    """Poctivý průchod: bloky nahlásí jedním výstupem, uzavře až dalším (upgrade-opora #32)."""
    reported = output(client, status, confirmed=False)
    return reported if reported.status_code != 200 else output(client, status)


def test_grant_allows_only_met_cards_and_records_autonomy(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assert complete(client).status_code == 409
        payload = grant(client)
        assert client.post("/api/desktop-v3/autonomy", headers={**HEADERS, "X-Opora-Actor": "agent"}, json=payload).status_code == 403
        result = client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=payload)
        assert result.status_code == 200, result.text
        assert complete(client, "blocked").status_code == 409
        result = complete(client)
        assert result.status_code == 200, result.text
        assert result.json()["state"]["nodes"]["n0"]["done"]["by"] == "autonomy"
        assert result.json()["acceptedResult"]["agent"] == "worker"
        entries = client.get("/api/activity-log", params={**SCOPE, "actor": "agent", "nodeId": "n0"}).json()["entries"]
        assert any(entry["status"] == 200 and "done.confirmed=true" in entry["summary"] for entry in entries)


def test_gate_and_revoked_grant_cannot_autonomously_close(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client)).status_code == 200
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client, until="")).status_code == 200
        assert complete(client).status_code == 409

        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client)).status_code == 200
        view = client.get("/api/view", params=SCOPE).json()
        next(node for node in view["graph"]["nodes"] if node["id"] == "n0")["name"] = "[gate] Sector verification"
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        assert complete(client).status_code == 409


def test_expired_grant_rejects_completion_without_state_changes(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        payload = grant(client)
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=payload).status_code == 200
        assert output(client, confirmed=False).status_code == 200
        before = client.get("/api/desktop-v3/state", params=SCOPE).json()
        monkeypatch.setattr(agent_output, "now", lambda: (datetime.fromisoformat(payload["until"]) + timedelta(seconds=1)).isoformat())
        assert output(client).status_code == 409
        assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before


def test_parent_grant_does_not_authorize_nested_sector_or_generic_state_write(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client)).status_code == 200
        view = client.get("/api/view", params=SCOPE).json()
        view["graph"]["nodes"].append({"id": "nested", "parentId": "s0", "kind": "sector", "name": "Nested", "purpose": "", "x": 0, "y": 0})
        next(node for node in view["graph"]["nodes"] if node["id"] == "n0")["parentId"] = "nested"
        saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        assert complete(client).status_code == 409
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        stored["state"]["autonomy"]["nested"] = stored["state"]["autonomy"]["s0"]
        forged = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]})
        assert forged.status_code == 200, forged.text
        assert "nested" not in forged.json()["state"]["autonomy"]
        assert complete(client).status_code == 409
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client, sectorId="nested")).status_code == 200
        assert complete(client).status_code == 200


def test_autonomy_cannot_mark_blocks_met_and_close_in_one_output(tmp_path):
    """Kritika #32: agent si podmínky nesplní sám v témže požadavku."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client)).status_code == 200
        response = output(client)
        assert response.status_code == 409 and "předchozím výstupu" in response.json()["error"]


def test_autonomy_rejects_not_applicable_evidence_and_cards_without_checks(tmp_path):
    """Kritika #31: N/A s libovolnou poznámkou ani karta bez kontrol se autonomně neuzavře."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client)).status_code == 200
        lazy = full_evidence()
        lazy["review"] = {"status": "not_applicable", "url": "", "note": "x"}
        assert output(client, confirmed=False, value=lazy).status_code == 200
        assert output(client, value=lazy).status_code == 409
    with TestClient(create_app(tmp_path / "bez-kontrol"), base_url=ORIGIN) as client:
        seed(client)
        assert client.post("/api/desktop-v3/autonomy", headers=HEADERS, json=grant(client)).status_code == 200
        assert complete(client).status_code == 409
