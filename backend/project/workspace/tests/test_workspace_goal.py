from fastapi.testclient import TestClient
from backend.project.workspace.tests.test_workspace_sources import ORIGIN

from backend.app.factory import create_app


def test_root_document_uses_the_existing_project_goal_with_conflict_guard(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        settings = client.get("/api/project-settings?project=draft").json()
        changed = {**settings["settings"], "goal": "Jedna autorita cíle"}
        assert client.post("/api/project-settings", headers={"Origin": ORIGIN}, json={"project": "draft", "expected_revision": settings["revision"], "name": settings["project"]["name"], "settings": changed}).status_code == 200
        document = client.get("/api/workspace/document", params={"project": "draft", "workspace": "draft"}).json()
        assert document["fields"]["goal"] == "Jedna autorita cíle", "Nový Projekt nesmí mít druhý nezávislý cíl"
        payload = {"project": "draft", "workspace": "draft", "path": "", "expectedRevision": document["revision"], "expectedSettingsRevision": document["settingsRevision"], "nodeId": None, "fields": {**document["fields"], "goal": "Upraveno z v2"}}
        saved = client.post("/api/workspace/document", headers={"Origin": ORIGIN}, json=payload)
        assert saved.status_code == 200, saved.text
        assert client.get("/api/project-settings?project=draft").json()["settings"]["goal"] == "Upraveno z v2"
        assert client.post("/api/workspace/document", headers={"Origin": ORIGIN}, json={**payload, "expectedRevision": saved.json()["revision"]}).status_code == 409
