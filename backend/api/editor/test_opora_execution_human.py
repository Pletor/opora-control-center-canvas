"""Explicit human operations survive enrollment; system is not a human shortcut."""
from backend.api.editor.test_opora_execution_enrollment import enroll
from backend.api.editor.test_opora_execution_routes import AGENT, SCOPE, client  # noqa: F401
from backend.canvas.test_canvas_plan import HEADERS
from backend.editor.agent_memory.test_completion_evidence import evidence


def test_human_confirmation_of_enrolled_card_is_not_blocked(client):
    enroll(client)
    stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
    node = stored["state"]["nodes"]["n0"]
    node["done"] = {"by": "agent", "confirmed": False, "note": "Ready", "at": "2026-10-07T12:00:00Z"}
    node["evidence"] = evidence()
    response = client.post("/api/desktop-v3/state", headers=HEADERS,
                           json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]})
    assert response.status_code == 200, response.text
    body = {**SCOPE, "sectorId": "s0", "nodeIds": ["n0"], "expectedRevision": response.json()["revision"]}
    assert client.post("/api/desktop-v3/confirm-proposals", headers=AGENT, json=body).status_code == 403
    response = client.post("/api/desktop-v3/confirm-proposals", headers=HEADERS, json=body)
    assert response.status_code == 200, response.text
