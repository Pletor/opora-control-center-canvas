from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, prepared, send
from backend.editor.agent_memory.test_versioned_output import brief, result_request, specification


def test_latest_result_status_tracks_saved_assignment_and_survives_restart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        def status():
            response = client.get("/api/desktop-v3/assignment-status", params=SCOPE)
            assert response.status_code == 200, response.text
            return response.json()["nodes"]
        assert status() == {}
        result = send(client, result_request(brief(client)))
        assert result.status_code == 200, result.text
        assert status()["focus"]["status"] == "current"
        specification(client, "focus", "New assignment")
        assert status()["focus"] == {"status": "changed", "resultId": result.json()["acceptedResult"]["id"]}
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert client.get("/api/desktop-v3/assignment-status", params=SCOPE).json()["nodes"]["focus"]["status"] == "changed"


def test_status_reuses_unchanged_scope_capture_and_invalidates_after_specification(tmp_path, monkeypatch):
    """Polling nesmí znovu skládat plnou specifikaci, ale zápis ji ihned invaliduje."""
    import backend.editor.agent_memory.assignment_status as status_module

    original = status_module.capture_specification
    calls = 0

    def captured(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(status_module, "capture_specification", captured)
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        result = send(client, result_request(brief(client)))
        assert result.status_code == 200, result.text

        def status():
            response = client.get("/api/desktop-v3/assignment-status", params=SCOPE)
            assert response.status_code == 200, response.text
            return response.json()["nodes"]["focus"]

        assert status()["status"] == "current"
        assert status()["status"] == "current"
        assert calls == 1
        specification(client, "focus", "Changed after cached status")
        assert status()["status"] == "changed"
        assert calls == 2


def test_claim_snapshots_assignment_so_unbound_work_is_detected(tmp_path):
    """Kritika #36: snímek zadání vzniká už při převzetí, i když agent assignment-snapshot vynechá."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        claim = client.post("/api/desktop-v3/lease", headers=HEADERS, json={
            **SCOPE, "nodeId": "focus", "op": "claim", "owner": "worker", "ttlSeconds": 60})
        assert claim.status_code == 200, claim.text
        assert claim.json()["assignment"]["contextVersion"] == brief(client)["contextVersion"]
        specification(client, "focus", "Changed while agent works")
        status = client.get("/api/desktop-v3/assignment-status", params=SCOPE).json()["nodes"]["focus"]
        assert status == {"status": "changed", "resultId": claim.json()["assignment"]["id"], "source": "handoff"}


def test_handoff_detects_changes_before_first_result_and_preserves_original(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assignment = brief(client)
        payload = {**SCOPE, "nodeId": "focus", "contextVersion": assignment["contextVersion"]}
        response = client.post("/api/desktop-v3/assignment-snapshot", headers=HEADERS, json=payload)
        assert response.status_code == 200, response.text
        saved = response.json()
        specification(client, "focus", "Changed while agent works")
        status = client.get("/api/desktop-v3/assignment-status", params=SCOPE).json()["nodes"]["focus"]
        assert status == {"status": "changed", "resultId": saved["id"], "source": "handoff"}
        assert client.post("/api/desktop-v3/assignment-snapshot", headers=HEADERS, json=payload).status_code == 409
        assert send(client, result_request(assignment)).status_code == 409
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        params = {**SCOPE, "nodeId": "focus", "id": saved["id"], "source": "handoff"}
        response = client.get("/api/desktop-v3/assignment-comparison", params=params)
        assert response.status_code == 200, response.text
        comparison = response.json()
        assert comparison["status"] == "changed"
        assert comparison["before"] == assignment["specification"]
        assert comparison["after"] != comparison["before"]
        assert client.get("/api/desktop-v3/assignment-comparison", params={**params, "nodeId": "other"}).status_code == 409
