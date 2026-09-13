from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.editor.claude_code_routes import create_claude_code_router


def client_for(tmp_path):
    skills = tmp_path / "skills"
    (skills / "graphify").mkdir(parents=True)
    (skills / "graphify/SKILL.md").write_text("---\nname: graphify\ndescription: Graph.\n---\n", encoding="utf-8")
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    app.include_router(create_claude_code_router(SimpleNamespace(root=tmp_path / "data"), roots={"user": skills}))
    return TestClient(app)


def test_lists_skills_and_persists_disabled_set(tmp_path):
    client = client_for(tmp_path)
    first = client.get("/api/claude-code/skills").json()
    assert [item["id"] for item in first["skills"]] == ["user:graphify"]
    assert first["disabled"] == []

    saved = client.post("/api/claude-code/skills/disabled", json={"disabled": ["user:graphify"]})
    assert saved.status_code == 200
    assert saved.json() == {"disabled": ["user:graphify"]}
    assert client.get("/api/claude-code/skills").json()["disabled"] == ["user:graphify"]
    assert (tmp_path / "data/claude-code-skills.json").exists()


def test_rejects_unexpected_payload(tmp_path):
    client = client_for(tmp_path)
    assert client.post("/api/claude-code/skills/disabled", json={"disabled": ["x"], "extra": 1}).status_code == 409
    assert client.post("/api/claude-code/skills/disabled", json={"disabled": ["no-scope"]}).status_code == 409
