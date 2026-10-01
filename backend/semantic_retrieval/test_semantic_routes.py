from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.semantic_routes import create_semantic_router


class FakeRetrieval:
    def status(self, project, workspace):
        return {"status": "configured", "model": "fixture", "detail": f"{project}/{workspace}", "localOnly": True}

    def query(self, payload):
        return {"status": "empty", "results": [], "model": "fixture", "localOnly": True,
                "filesScanned": 0, "chunksIndexed": 0, "truncated": False, "detail": payload["path"]}


def test_semantic_router_exposes_specified_status_and_query_contract():
    app = FastAPI()
    app.include_router(create_semantic_router(object(), semantic_service=FakeRetrieval()))
    client = TestClient(app)

    status = client.get("/api/semantic-search/status", params={"project": "p", "workspace": "draft"})
    query = client.post("/api/semantic-search/query", json={"project": "p", "workspace": "draft", "path": "src", "query": "meaning", "limit": 4})

    assert status.status_code == 200 and status.json()["detail"] == "p/draft"
    assert query.status_code == 200 and query.json()["detail"] == "src"
