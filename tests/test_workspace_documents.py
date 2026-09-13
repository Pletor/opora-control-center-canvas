from fastapi.testclient import TestClient
from test_workspace_sources import ORIGIN, attach

from backend.app.factory import create_app

FIELDS = {"purpose": "Smysl aplikace", "goal": "Funkční projekt", "architecture": "API a UI", "technologies": "Python, React", "notes": "Teorie a tvorba", "requirements": "Požadavek není automaticky důkaz."}


def test_document_is_separate_from_code_revisioned_and_persistent(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    code = source / "hello.py"
    code.write_text("print('unchanged')", encoding="utf-8")
    root = tmp_path / "data"
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft", "path": "hello.py"}
        response = client.get("/api/workspace/document", params=scope)
        assert response.status_code == 200
        initial = response.json()
        assert initial["revision"] == 0 and initial["status"] == "missing"
        payload = {**scope, "expectedRevision": 0, "fields": FIELDS, "nodeId": None}
        saved = client.post("/api/workspace/document", headers={"origin": ORIGIN}, json=payload)
        assert saved.status_code == 200
        assert saved.json()["revision"] == 1 and saved.json()["fields"] == FIELDS
        assert saved.json()["status"] == "documented"
        assert client.post("/api/workspace/document", headers={"origin": ORIGIN}, json=payload).status_code == 409
        assert client.get("/api/workspace/document", params={**scope, "path": ""}).json()["revision"] == 0
        assert code.read_text(encoding="utf-8") == "print('unchanged')"
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        persisted = client.get("/api/workspace/document", params=scope).json()
        assert persisted["revision"] == 1 and persisted["fields"] == FIELDS
        code.write_text("print('source changed after documentation')", encoding="utf-8")
        assert client.get("/api/workspace/document", params=scope).json()["status"] == "stale"
