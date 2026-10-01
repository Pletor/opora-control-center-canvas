"""Zápis do paměti role je vedlejší účinek: nikdy nepoloží uložení v Opoře."""

import copy
import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.editor.canvas_routes import create_canvas_router
from backend.api.editor.desktop_v3_routes import create_desktop_v3_router
from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_handoff.message_store import MessageStore
from backend.editor.agent_memory.agent_output import AgentOutput
from backend.editor.agent_memory.agent_workspace import AgentWorkspace
from backend.editor.agent_memory.block_access import BlockAccess
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import DesktopV3Packets
from backend.editor.agent_packet.node_brief import NodeBrief

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}
GRAPH = {
    "nodes": [{"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko",
               "purpose": "Cíl", "x": 0, "y": 0}],
    "edges": [],
}


class RecordingMemory:
    """Dvojník služby paměti; `explode` dokazuje, že chyba nikdy neunikne do odpovědi."""

    def __init__(self, explode=False):
        self.mirrored, self.committed = [], []
        self.explode = explode

    def status(self):
        return {"status": "configured", "reason": "", "url": "http://127.0.0.1:1933"}

    def bootstrap_status(self):
        return {"enabled": True, "status": "unknown"}

    def recall(self, role, project, node_id, query, max_tokens=600):
        return {"status": "configured", "role": role, "items": [], "rendered": "", "truncated": False}

    def mirror_workspace(self, role, project, node_id, sections):
        if self.explode:
            raise OSError("OpenViking spadl")
        self.mirrored.append((role, project, node_id, dict(sections)))
        return {"status": "configured", "mirrored": [], "errors": []}

    def commit_card(self, role, project, node_id, sections):
        if self.explode:
            raise OSError("OpenViking spadl")
        self.committed.append((role, project, node_id, dict(sections)))
        return {"status": "configured", "taskId": "t-1"}


def build(tmp_path, explode=False):
    """Stejné složení jako v `factory.py`, jen s dvojníkem paměti místo OpenVikingu."""
    service = CanvasService(tmp_path / "data")
    state = DesktopV3State(service)
    service.desktop_v3_state = state
    memory = RecordingMemory(explode)
    service.memory_service = memory
    workspace = AgentWorkspace(service, state)
    service.agent_workspace = workspace
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    @app.exception_handler(sqlite3.Error)
    async def storage(request, exc):
        return JSONResponse({"error": "Úložiště není dostupné."}, status_code=503)

    app.include_router(create_canvas_router(service))
    app.include_router(create_desktop_v3_router(
        state, DesktopV3Packets(service, state), NodeBrief(service, state, MessageStore(service, state)),
        AgentOutput(service, state), BlockAccess(service, state), workspace, memory_service=memory,
    ))
    return app, memory


def seed(client, role="role-backend"):
    view = client.get("/api/view", params=SCOPE).json()
    saved = client.post("/api/graph", headers=HEADERS,
                        json={**SCOPE, "graph": GRAPH, "digest": view["digest"]})
    assert saved.status_code == 200, saved.text
    state = copy.deepcopy(EMPTY)
    state["nodes"] = {"focus": {"phase": "discover", "criteria": [], "steps": [], "agentRole": role}}
    stored = client.post("/api/desktop-v3/state", headers=HEADERS,
                         json={**SCOPE, "expectedRevision": 0, "state": state})
    assert stored.status_code == 200, stored.text
    return state, stored.json()["revision"]


def write_space(client, expected=0, **sections):
    return client.post("/api/desktop-v3/agent-workspace", headers=HEADERS, json={
        **SCOPE, "nodeId": "focus", "expectedRevision": expected, "by": "agent",
        "sections": sections or {"log": "Napsal jsem router."},
    })


def test_saving_the_workspace_mirrors_it_into_the_role_memory(tmp_path):
    app, memory = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        seed(client)
        saved = write_space(client)
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        assert len(memory.mirrored) == 1
        role, project, node_id, sections = memory.mirrored[0]
        assert (role, project, node_id) == ("role-backend", "draft", "focus")
        assert sections["log"] == "Napsal jsem router."
        assert "updatedAt" not in sections and "by" not in sections


def test_a_card_without_a_role_is_never_mirrored(tmp_path):
    app, memory = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        seed(client, role=None)
        assert write_space(client).status_code == 200
        assert memory.mirrored == []


def test_a_broken_memory_never_fails_the_save(tmp_path):
    app, _memory = build(tmp_path, explode=True)
    with TestClient(app, base_url=ORIGIN) as client:
        seed(client)
        saved = write_space(client)
        assert saved.status_code == 200 and saved.json()["workspace"]["log"] == "Napsal jsem router."
        read = client.get("/api/desktop-v3/agent-workspace", params={**SCOPE, "nodeId": "focus"})
        assert read.json()["workspace"]["log"] == "Napsal jsem router."


def test_confirming_a_card_commits_it_once(tmp_path):
    app, memory = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        state, revision = seed(client)
        assert write_space(client).status_code == 200
        state["nodes"]["focus"]["done"] = {"confirmed": True, "at": "", "by": "human", "note": ""}
        done = client.post("/api/desktop-v3/state", headers=HEADERS,
                           json={**SCOPE, "expectedRevision": revision, "state": state})
        assert done.status_code == 200, done.text
        assert len(memory.committed) == 1
        role, project, node_id, sections = memory.committed[0]
        assert (role, project, node_id) == ("role-backend", "draft", "focus")
        assert sections["log"] == "Napsal jsem router."
        # Druhé uložení už kartu znovu neuzavírá, takže se nic neposílá podruhé.
        again = client.post("/api/desktop-v3/state", headers=HEADERS,
                            json={**SCOPE, "expectedRevision": done.json()["revision"], "state": state})
        assert again.status_code == 200 and len(memory.committed) == 1


def test_a_broken_memory_never_fails_confirming_a_card(tmp_path):
    app, _memory = build(tmp_path, explode=True)
    with TestClient(app, base_url=ORIGIN) as client:
        state, revision = seed(client)
        state["nodes"]["focus"]["done"] = {"confirmed": True, "at": "", "by": "human", "note": ""}
        done = client.post("/api/desktop-v3/state", headers=HEADERS,
                           json={**SCOPE, "expectedRevision": revision, "state": state})
        assert done.status_code == 200, done.text
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()[
            "state"]["nodes"]["focus"]["done"]["confirmed"] is True


def test_an_invalid_state_payload_still_fails_without_touching_memory(tmp_path):
    app, memory = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        seed(client)
        refused = client.post("/api/desktop-v3/state", headers=HEADERS, json={"state": {}})
        assert refused.status_code == 409
        assert memory.committed == [] and memory.mirrored == []


def test_bootstrap_reports_the_memory_toggle_without_a_network_call(tmp_path):
    app = create_app(tmp_path / "real")
    app.state.service.memory_service = RecordingMemory()
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/bootstrap").json()["memory"] == {"enabled": True, "status": "unknown"}


def test_bootstrap_says_disabled_when_the_toggle_is_off(tmp_path):
    app = create_app(tmp_path / "off")
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/bootstrap").json()["memory"] == {"enabled": False, "status": "disabled"}
