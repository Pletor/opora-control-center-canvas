from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory import card_leases
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, prepared


def claim(owner="agent"):
    return {**SCOPE, "nodeId": "focus", "op": "claim", "owner": owner, "ttlSeconds": 60}


def test_atomic_claim_heartbeat_expiry_and_fenced_release(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(card_leases.time, "time", lambda: clock[0])
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        def acquire(owner):
            return client.post("/api/desktop-v3/lease", headers=HEADERS, json=claim(owner))
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(acquire, ["a", "b"]))
        assert sorted(r.status_code for r in responses) == [200, 409]
        token = next(r.json()["token"] for r in responses if r.status_code == 200)
        summary = client.get("/api/desktop-v3/leases", params=SCOPE).json()
        assert summary["nodes"]["focus"]["active"]
        assert token not in str(summary)
        renewal = {**SCOPE, "nodeId": "focus", "op": "heartbeat", "token": token, "ttlSeconds": 60}
        clock[0] = 1050
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=renewal).json()["expiresAt"] == 1110
        clock[0] = 1110
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=renewal).status_code == 409
        newer = acquire("new")
        assert newer.status_code == 200
        release = {**SCOPE, "nodeId": "focus", "op": "release", "token": token}
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=release).status_code == 409
        release["token"] = newer.json()["token"]
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=release).status_code == 200


def test_lease_survives_restart_and_frontier_unclaims_on_expiry(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(card_leases.time, "time", lambda: clock[0])
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=claim()).status_code == 200
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=claim("other")).status_code == 409
        assert client.get("/api/desktop-v3/frontier", params=SCOPE).json()["claimed"][0]["id"] == "focus"
        clock[0] = 1061
        result = client.get("/api/desktop-v3/frontier", params=SCOPE).json()
        assert result["claimed"] == []
        assert next(row for row in result["frontier"] if row["id"] == "focus")["lease"]["active"] is False
