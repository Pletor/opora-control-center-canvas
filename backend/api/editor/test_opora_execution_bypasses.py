"""Direct SQL writer integrations cannot mutate enrolled cards through alternate APIs."""
from backend.api.editor.test_opora_execution_enrollment import enroll
from backend.api.editor.test_opora_execution_routes import AGENT, SCOPE, client  # noqa: F401
from backend.canvas.test_canvas_plan import HEADERS
from backend.canvas.test_canvas_plan_extend import extension


def test_canvas_plan_extension_cannot_bypass_enrollment(client):
    enroll(client)
    view = client.get("/api/view", params=SCOPE).json()
    before = client.get("/api/desktop-v3/state", params=SCOPE).json()
    response = client.post("/api/canvas-plan", headers=AGENT,
                           json={**SCOPE, "digest": view["digest"], "dryRun": False, "plan": {"extend": [extension(client)]}})
    assert response.status_code == 409 and "receipts" in response.text, response.text
    assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before
    assert client.get("/api/node-spec", params={**SCOPE, "node": "n0"}).json()["revision"] == 0


def test_vault_idea_extraction_cannot_bypass_enrollment(client):
    stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
    stored["state"]["nodes"]["n0"]["ideas"] = [{"id": "idea1", "text": "Explore", "by": "human",
        "source": "review", "at": "2026-10-07T12:00:00Z", "status": "open"}]
    response = client.post("/api/desktop-v3/state", headers=HEADERS,
                           json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]})
    assert response.status_code == 200, response.text
    enroll(client)
    before = client.get("/api/desktop-v3/state", params=SCOPE).json()
    response = client.post("/api/brief-vault", headers=AGENT,
                           json={**SCOPE, "op": "from-idea", "nodeId": "n0", "ideaId": "idea1", "discipline": "be"})
    assert response.status_code == 409 and "receipts" in response.text, response.text
    assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before
