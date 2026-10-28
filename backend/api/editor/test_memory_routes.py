"""HTTP kontrakt paměti role: přesné klíče, role ze serveru, pravdivá nedostupnost."""

import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.editor.memory_routes import create_memory_router
from backend.memory.memory_service import MemoryService
from backend.memory.test_memory_service import FakeOpenVikingClient, Toggle, hit

SELF_URI = "viking://user/role-backend/memories"


class FakeState:
    def __init__(self, nodes):
        self.nodes = nodes

    def read(self, project, workspace):
        if project != "draft" or workspace != "draft":
            raise ValueError("Neplatný rozsah.")
        return {"revision": 1, "state": {"nodes": self.nodes}, "readOnly": False}


class FakeService:
    def __init__(self, nodes):
        self.desktop_v3_state = FakeState(nodes)


def build(nodes=None, client=None, enabled=True, keys=None, actor="human"):
    fake = client or FakeOpenVikingClient(results={
        SELF_URI: [hit("viking://user/role-backend/memories/a.md", 0.9, "Router patří do api.")],
    })
    memory = MemoryService(lambda: fake, Toggle(enabled, keys))
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    @app.middleware("http")
    async def as_actor(request, call_next):
        # Původce jako po middleware aplikace (rozdání klíčů je výjimka §4: jen člověk).
        request.state.actor = actor
        return await call_next(request)

    app.include_router(create_memory_router(FakeService(nodes or {}), memory))
    return TestClient(app, raise_server_exceptions=False), memory, fake


def test_status_and_roles_are_readable():
    client, _, _ = build()
    status = client.get("/api/memory/status").json()
    assert status["status"] == "configured" and status["url"].startswith("http://127.0.0.1")
    listed = client.get("/api/memory/roles").json()["roles"]
    assert [item["id"] for item in listed][:2] == ["role-frontend", "role-backend"]
    assert all(set(item) == {"id", "label", "description"} for item in listed)


def test_status_says_which_roles_have_no_key_yet():
    client, _, _ = build(keys={"role-backend": "key-role-backend"})
    status = client.get("/api/memory/status").json()
    assert status["status"] == "needs_provisioning"
    assert "role-frontend" in status["missingRoles"] and "role-backend" not in status["missingRoles"]


def test_provision_needs_confirmation_and_returns_roles_without_secrets():
    fake = FakeOpenVikingClient(users=["admin"], results={SELF_URI: []})
    client, memory, _ = build(client=fake, keys={})
    assert client.post("/api/memory/provision", json={"confirmed": False}).status_code == 409
    assert client.post("/api/memory/provision", json={}).status_code == 409
    assert client.post("/api/memory/provision", json={"confirmed": True, "navic": 1}).status_code == 409
    done = client.post("/api/memory/provision", json={"confirmed": True}).json()
    assert done["status"] == "configured" and "role-backend" in done["provisioned"]
    assert done["errors"] == [] and done["reused"] == []
    secrets = list(memory.settings.role_keys().values())
    assert secrets and not any(secret in repr(done) for secret in secrets)
    assert client.get("/api/memory/status").json()["status"] == "configured"


def test_provision_stays_human_only_even_for_agent():
    """docs/plna-autonomie-agenta.md §4: rozdání klíčů root klíčem nikdy agent, ani s plnou autonomií."""
    from backend.canvas.activity_log import HumanRequired
    fake = FakeOpenVikingClient(users=["admin"], results={SELF_URI: []})
    client, _, _ = build(client=fake, keys={}, actor="agent")

    @client.app.exception_handler(HumanRequired)
    async def human_required(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=403)

    assert client.post("/api/memory/provision", json={"confirmed": True}).status_code == 403


def test_a_role_without_a_key_is_unavailable_over_http():
    client, _, fake = build({"n1": {"agentRole": "role-backend"}}, keys={})
    result = client.post("/api/memory/recall", json={
        "role": None, "project": "draft", "workspace": "draft", "nodeId": "n1",
        "query": "x", "maxTokens": 600}).json()
    assert result["status"] == "unavailable" and "provisioning" in result["reason"]
    assert fake.calls == []


def test_recall_uses_the_role_from_the_card_when_the_client_sends_none():
    client, _, fake = build({"n1": {"agentRole": "role-backend"}})
    body = {"role": None, "project": "draft", "workspace": "draft", "nodeId": "n1",
            "query": "kam patří router", "maxTokens": 600}
    result = client.post("/api/memory/recall", json=body).json()
    assert result["status"] == "configured" and result["role"] == "role-backend"
    assert result["items"][0]["origin"] == "self"
    searches = [call for call in fake.calls if call[0] == "search"]
    assert [call[1] for call in searches] == ["role-backend", "role-backend"]
    assert [call[4] for call in searches] == [SELF_URI, "viking://user/role-backend/peers/draft"]


def test_recall_on_a_card_without_a_role_is_skipped_not_empty():
    client, _, fake = build({"n1": {}})
    body = {"role": None, "project": "draft", "workspace": "draft", "nodeId": "n1",
            "query": "cokoli", "maxTokens": 600}
    result = client.post("/api/memory/recall", json=body).json()
    assert result == {"status": "skipped", "reason": result["reason"], "role": None,
                      "items": [], "rendered": "", "truncated": False}
    assert fake.calls == []


def test_missing_or_extra_keys_are_refused_with_409():
    client, _, _ = build({"n1": {"agentRole": "role-backend"}})
    assert client.post("/api/memory/recall", json={"query": "x"}).status_code == 409
    full = {"role": None, "project": "draft", "workspace": "draft", "nodeId": "n1",
            "query": "x", "maxTokens": 600}
    assert client.post("/api/memory/recall", json={**full, "navic": 1}).status_code == 409
    assert client.post("/api/memory/recall", json={**full, "role": "role-nikdo"}).status_code == 409
    assert client.post("/api/memory/recall", json={**full, "maxTokens": 99999}).status_code == 409
    assert client.post("/api/memory/recall", json={**full, "query": " "}).status_code == 409


def test_remember_requires_confirmation_and_writes_the_card_resource():
    client, _, fake = build({"n1": {"agentRole": "role-backend"}})
    body = {"role": None, "project": "draft", "workspace": "draft", "nodeId": "n1",
            "kind": "lesson", "text": "CAS konflikt řeš revizí.", "confirmed": False}
    assert client.post("/api/memory/remember", json=body).status_code == 409
    saved = client.post("/api/memory/remember", json={**body, "confirmed": True}).json()
    assert saved["status"] == "configured"
    assert saved["uri"].startswith("viking://user/role-backend/peers/draft/resources/cards/n1/lesson-")
    assert any(call[0] == "write" for call in fake.calls)


def test_lend_labels_the_origin_and_refuses_an_unknown_role():
    fake = FakeOpenVikingClient(results={
        "viking://user/role-db/memories": [hit("viking://user/role-db/memories/index.md", 0.7)],
    })
    client, _, _ = build(client=fake)
    body = {"fromRole": "role-db", "toRole": "role-backend", "query": "index", "maxTokens": 600}
    result = client.post("/api/memory/lend", json=body).json()
    assert result["items"][0]["origin"] == "lent:role-db" and result["fromRole"] == "role-db"
    assert client.post("/api/memory/lend", json={**body, "toRole": "role-nikdo"}).status_code == 409


def test_settings_toggle_is_application_wide_and_reports_the_new_status():
    client, memory, _ = build()
    off = client.post("/api/memory/settings", json={"enabled": False}).json()
    assert off["status"] == "disabled" and memory.enabled() is False
    assert client.post("/api/memory/recall", json={
        "role": "role-backend", "project": "draft", "workspace": "draft", "nodeId": "n1",
        "query": "x", "maxTokens": 600}).json()["status"] == "disabled"
    assert client.post("/api/memory/settings", json={"enabled": True}).json()["status"] == "configured"
    assert client.post("/api/memory/settings", json={"enabled": "ano"}).status_code == 409


def test_a_down_server_is_unavailable_never_a_fabricated_answer():
    client, _, _ = build({"n1": {"agentRole": "role-backend"}}, client=FakeOpenVikingClient(fail={"search"}))
    result = client.post("/api/memory/recall", json={
        "role": None, "project": "draft", "workspace": "draft", "nodeId": "n1",
        "query": "x", "maxTokens": 600}).json()
    assert result["status"] == "unavailable" and result["items"] == [] and result["reason"]


def test_an_invalid_scope_is_refused_by_the_state_store():
    client, _, _ = build({"n1": {"agentRole": "role-backend"}})
    refused = client.post("/api/memory/recall", json={
        "role": None, "project": "jiny", "workspace": "draft", "nodeId": "n1",
        "query": "x", "maxTokens": 600})
    assert refused.status_code == 409


def test_the_registry_table_exists_in_the_registry_schema(tmp_path):
    from database.schema.project_schema import REGISTRY_SCHEMA

    db = sqlite3.connect(tmp_path / "registry.sqlite")
    db.executescript(REGISTRY_SCHEMA)
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "app_settings" in tables
