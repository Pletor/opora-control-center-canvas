"""HTTP: only a human UI session binds a folder project to the GitHub repository of its origin."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.canvas.test_opora_folder_repository import checkout

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=builder"}
BASE = "/api/oporahub/repository"


def test_human_binds_agent_is_refused(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        created = client.post("/api/local-project", headers=HEADERS,
                              json={"path": str(checkout(tmp_path)), "name": "Ample", "confirmed": True})
        assert created.status_code == 200, created.text
        project = created.json()["id"]
        body = {"project": project, "repository": "owner/repo", "branch": "main"}
        assert client.get(BASE, params={"project": project}, headers=AGENT).json()["canConfigure"] is False
        assert client.post(BASE, headers=AGENT, json=body).status_code == 403
        shown = client.get(BASE, params={"project": project}, headers=HEADERS).json()
        assert shown["canConfigure"] and shown["detectedRepository"] == "owner/repo" and shown["binding"] is None
        mismatch = client.post(BASE, headers=HEADERS, json={**body, "repository": "other/repo"})
        assert mismatch.status_code in (400, 409) and "other/repo" in mismatch.text
        bound = client.post(BASE, headers=HEADERS, json=body)
        assert bound.status_code == 200, bound.text
        assert bound.json()["binding"]["repository"] == "owner/repo"
        listing = client.get("/api/oporahub/reconciliation", params={"project": project, "workspace": "draft"},
                             headers=HEADERS).json()
        assert "Git repozitář" not in (listing["unavailableReason"] or "")
        assert client.post(BASE + "/unbind", headers=AGENT, json={"project": project}).status_code == 403
        assert client.post(BASE + "/unbind", headers=HEADERS, json={"project": project}).json()["binding"] is None
