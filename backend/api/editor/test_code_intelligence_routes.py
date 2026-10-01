from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.code_intelligence_routes import create_code_intelligence_router


class FakeIntelligence:
    def __init__(self):
        self.status_calls = []
        self.query_calls = []

    def status(self, project, workspace):
        self.status_calls.append((project, workspace))
        return {"providers": [], "semantic": {"status": "unavailable", "reason": "test"}, "preference": ["lsp", "semantic", "scoped-text"]}

    def query(self, query):
        self.query_calls.append(query)
        return {"status": "empty", "language": query.language, "operation": query.operation, "results": [], "detail": "test"}


def client_with(fake):
    app = FastAPI()
    app.include_router(create_code_intelligence_router(object(), intelligence=fake))
    return TestClient(app)


def test_status_uses_read_only_intelligence_without_query_spawn():
    fake = FakeIntelligence()
    with client_with(fake) as client:
        response = client.get("/api/code-intelligence/status", params={"project": "p", "workspace": "draft"})

    assert response.status_code == 200
    assert fake.status_calls == [("p", "draft")]
    assert fake.query_calls == []


def test_query_requires_exact_lsp_shape_and_constructs_typed_request():
    fake = FakeIntelligence()
    payload = {"project": "p", "workspace": "draft", "language": "python", "path": "one.py",
               "operation": "hover", "line": 0, "character": 0}
    with client_with(fake) as client:
        rejected = client.post("/api/code-intelligence/query", json={**payload, "extra": True})
        response = client.post("/api/code-intelligence/query", json=payload)

    assert rejected.status_code == 409
    assert response.status_code == 200
    assert fake.query_calls[0].path == "one.py"
    assert fake.query_calls[0].operation == "hover"
