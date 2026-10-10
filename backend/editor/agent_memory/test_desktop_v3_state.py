"""Desktop v3 paměť projektu a stav uzlů: revizovaný, striktní, izolovaný, atomický."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}


def _state(**overrides):
    state = copy.deepcopy(EMPTY)
    state.update(overrides)
    return state


def _seed_graph(client, project="draft", workspace="draft"):
    view = client.get("/api/view", params={"project": project, "workspace": workspace}).json()
    graph = {
        "nodes": [
            {"id": "sector", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
            {"id": "focus", "parentId": "sector", "kind": "node", "name": "Ohnisko", "purpose": "Cíl", "x": 0, "y": 0},
        ],
        "edges": [],
    }
    response = client.post(
        "/api/graph", headers=HEADERS,
        json={"project": project, "workspace": workspace, "graph": graph, "digest": view["digest"]},
    )
    assert response.status_code == 200, response.text


def _get(client, **scope):
    return client.get("/api/desktop-v3/state", params={**SCOPE, **scope})


def _post(client, state, expected=0, **scope):
    return client.post(
        "/api/desktop-v3/state", headers=HEADERS,
        json={**SCOPE, **scope, "expectedRevision": expected, "state": state},
    )


def _full_state():
    return _state(
        settings=[{"id": "s1", "key": "framework", "value": "React + TypeScript"}],
        rules=[
            {"id": "r1", "text": "Agent se nikdy nespouští sám.", "kind": "must", "scope": "project", "target": ""},
            {"id": "r2", "text": "Číst .env", "kind": "must_not", "scope": "path", "target": "src"},
            {"id": "r3", "text": "Držet digest", "kind": "must", "scope": "node", "target": "focus"},
        ],
        decisions=[{
            "id": "d1", "text": "Strom 1:1.", "pinned": True, "path": "", "nodeId": "",
            "createdAt": "2026-09-11T08:00:00+00:00", "by": "human",
        }],
        nodes={"focus": {
            "phase": "discover",
            "criteria": [{"id": "c1", "text": "Cíl popsán", "checked": False}],
            "steps": [{"id": "st1", "text": "Napsat test", "assignee": "builder", "done": False}],
        }},
        tickets=[{
            "id": "t1", "title": "Test selhává", "priority": "high", "status": "open",
            "nodeId": "focus", "sessionId": "", "createdBy": "agent",
        }],
    )


def test_default_state_is_empty_without_demo_data(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        response = _get(client)
        assert response.status_code == 200, response.text
        assert response.json() == {"revision": 0, "state": EMPTY, "readOnly": False}


def test_save_persists_and_reloads_exact_state_with_revision(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        state = _full_state()
        saved = _post(client, state)
        assert saved.status_code == 200, saved.text
        assert saved.json() == {"revision": 1, "state": state, "readOnly": False}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        reloaded = _get(client).json()
        assert reloaded == {"revision": 1, "state": state, "readOnly": False}


def test_stale_revision_is_rejected_with_409_and_keeps_stored_state(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        first = _post(client, _state(settings=[{"id": "s1", "key": "a", "value": "1"}]))
        assert first.status_code == 200
        stale = _post(client, _state(settings=[{"id": "s1", "key": "a", "value": "2"}]), expected=0)
        assert stale.status_code == 409
        assert "revi" in stale.json()["error"].lower() or "změnil" in stale.json()["error"]
        current = _get(client).json()
        assert current["revision"] == 1
        assert current["state"]["settings"][0]["value"] == "1"
        again = _post(client, _state(settings=[{"id": "s1", "key": "a", "value": "2"}]), expected=1)
        assert again.status_code == 200 and again.json()["revision"] == 2


def test_state_is_isolated_per_project_and_workspace(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Other", "confirmed": True}).json()["id"]
        assert _post(client, _state(settings=[{"id": "s1", "key": "k", "value": "DRAFT_ONLY"}])).status_code == 200
        assert _get(client, project=other).json() == {"revision": 0, "state": EMPTY, "readOnly": False}
        assert _post(client, _state(settings=[{"id": "s1", "key": "k", "value": "OTHER"}]), project=other).status_code == 200
        assert _get(client).json()["state"]["settings"][0]["value"] == "DRAFT_ONLY"
        assert _get(client, project=other).json()["state"]["settings"][0]["value"] == "OTHER"
        # Neznámé ID projektu je 404 a nic nezaloží (karta P3).
        assert _get(client, project="missing-project").status_code == 404
        assert _get(client, project="../x").status_code == 409


@pytest.mark.parametrize("mutate", [
    lambda p: p.update({"extra": 1}),
    lambda p: p.pop("expectedRevision"),
    lambda p: p.update({"expectedRevision": "0"}),
    lambda p: p["state"].pop("tickets"),
    lambda p: p["state"].update({"demo": []}),
    lambda p: p["state"].update({"rules": [{"id": "r", "text": "x", "kind": "should", "scope": "project", "target": ""}]}),
    lambda p: p["state"].update({"rules": [{"id": "r", "text": "x", "kind": "must", "scope": "project", "target": "src"}]}),
    lambda p: p["state"].update({"rules": [{"id": "r", "text": "x", "kind": "must", "scope": "path", "target": "../etc"}]}),
    lambda p: p["state"].update({"rules": [{"id": "r", "text": "x", "kind": "must", "scope": "path", "target": "src/.git/config"}]}),
    lambda p: p["state"].update({"rules": [{"id": "r", "text": "x", "kind": "must", "scope": "node", "target": "not valid!"}]}),
    lambda p: p["state"].update({"rules": [{"id": "r", "text": "", "kind": "must", "scope": "project", "target": ""}]}),
    lambda p: p["state"].update({"rules": [{"id": "r", "text": "x", "kind": "must", "scope": "project", "target": ""}] * 2}),
    lambda p: p["state"].update({"settings": [{"id": "s", "key": "k", "value": 5}]}),
    lambda p: p["state"].update({"decisions": [{"id": "d", "text": "x", "pinned": "yes", "path": "", "nodeId": "", "createdAt": "2026-09-11T08:00:00+00:00", "by": "human"}]}),
    lambda p: p["state"].update({"decisions": [{"id": "d", "text": "x", "pinned": True, "path": "", "nodeId": "", "createdAt": "včera", "by": "human"}]}),
    lambda p: p["state"].update({"decisions": [{"id": "d", "text": "x", "pinned": True, "path": "", "nodeId": "", "createdAt": "2026-09-11T08:00:00+00:00", "by": "robot"}]}),
    lambda p: p["state"].update({"nodes": {"bad id!": {"phase": "discover", "criteria": [], "steps": []}}}),
    lambda p: p["state"].update({"nodes": {"focus": {"phase": "deployed", "criteria": [], "steps": []}}}),
    lambda p: p["state"].update({"nodes": {"focus": {"phase": "discover", "criteria": [{"id": "c", "text": "x", "checked": 1}], "steps": []}}}),
    lambda p: p["state"].update({"nodes": []}),
    lambda p: p["state"].update({"tickets": [{"id": "t", "title": "x", "priority": "urgent", "status": "open", "nodeId": "", "sessionId": "", "createdBy": "human"}]}),
    lambda p: p["state"].update({"tickets": [{"id": "t", "title": "x", "priority": "high", "status": "blocked", "nodeId": "", "sessionId": "", "createdBy": "human"}]}),
    lambda p: p["state"].update({"tickets": [{"id": "t", "title": "x" * 5000, "priority": "high", "status": "open", "nodeId": "", "sessionId": "", "createdBy": "human"}]}),
])
def test_malformed_payloads_are_rejected_without_persisting(tmp_path, mutate):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        payload = {**SCOPE, "expectedRevision": 0, "state": _state()}
        mutate(payload)
        response = client.post("/api/desktop-v3/state", headers=HEADERS, json=payload)
        assert response.status_code == 409, response.text
        assert _get(client).json() == {"revision": 0, "state": EMPTY, "readOnly": False}


def test_phase_advance_requires_non_empty_checked_criteria_and_backward_is_free(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        # Uzel musí nejdřív existovat v previous, jinak je to nová karta bez brány kritérií.
        seeded = _state(nodes={"focus": {"phase": "discover", "criteria": [], "steps": []}})
        assert _post(client, seeded).status_code == 200
        unchecked = _state(nodes={"focus": {"phase": "define", "criteria": [{"id": "c1", "text": "Cíl", "checked": False}], "steps": []}})
        refused = _post(client, unchecked, expected=1)
        assert refused.status_code == 409
        assert "krit" in refused.json()["error"].lower()
        empty = _state(nodes={"focus": {"phase": "define", "criteria": [], "steps": []}})
        assert _post(client, empty, expected=1).status_code == 409
        checked = _state(nodes={"focus": {"phase": "define", "criteria": [{"id": "c1", "text": "Cíl", "checked": True}], "steps": []}})
        advanced = _post(client, checked, expected=1)
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["state"]["nodes"]["focus"]["phase"] == "define"
        skip = _state(nodes={"focus": {"phase": "live", "criteria": [{"id": "c1", "text": "Cíl", "checked": True}], "steps": []}})
        assert _post(client, skip, expected=2).status_code == 200
        back = _state(nodes={"focus": {"phase": "discover", "criteria": [], "steps": []}})
        reverted = _post(client, back, expected=3)
        assert reverted.status_code == 200, reverted.text
        assert reverted.json()["state"]["nodes"]["focus"]["phase"] == "discover"
        assert reverted.json()["revision"] == 4


def test_new_node_may_be_saved_at_any_phase_without_criteria_gate(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        state = _state(nodes={"focus": {"phase": "build", "criteria": [], "steps": []}})
        created = _post(client, state)
        assert created.status_code == 200, created.text
        assert created.json()["state"]["nodes"]["focus"]["phase"] == "build"


def test_existing_node_advance_without_criteria_is_still_rejected(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        seeded = _state(nodes={"focus": {"phase": "discover", "criteria": [], "steps": []}})
        assert _post(client, seeded).status_code == 200
        advance = _state(nodes={"focus": {"phase": "build", "criteria": [], "steps": []}})
        refused = _post(client, advance, expected=1)
        assert refused.status_code == 409
        assert "krit" in refused.json()["error"].lower()


def test_existing_node_advance_with_all_criteria_checked_is_accepted(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        seeded = _state(nodes={"focus": {"phase": "discover", "criteria": [], "steps": []}})
        assert _post(client, seeded).status_code == 200
        advance = _state(nodes={"focus": {
            "phase": "build",
            "criteria": [{"id": "c1", "text": "Hotovo", "checked": True}],
            "steps": [],
        }})
        advanced = _post(client, advance, expected=1)
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["state"]["nodes"]["focus"]["phase"] == "build"


def test_checking_criteria_does_not_touch_runs_or_other_stores(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        before_view = client.get("/api/view", params=SCOPE).json()["digest"]
        state = _state(nodes={"focus": {"phase": "discover", "criteria": [{"id": "c1", "text": "Test prošel", "checked": True}], "steps": []}})
        assert _post(client, state).status_code == 200
        assert client.get("/api/view", params=SCOPE).json()["digest"] == before_view
        assert client.get("/api/node-spec", params={**SCOPE, "node": "focus"}).json()["revision"] == 0


def test_main_workspace_is_read_only_for_state(tmp_path, monkeypatch):
    app = create_app(tmp_path / "data")
    service = app.state.service
    service.register_repository("p", "Project", str(tmp_path / "repo"), "fixture://p", "main")
    service.db.commit()

    def fake_git(_root, *args, **_kwargs):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("branch", "--show-current"):
            return "main"
        return None

    monkeypatch.setattr("backend.canvas.canvas_service.git", fake_git)
    with TestClient(app, base_url=ORIGIN) as client:
        response = _get(client, project="p", workspace="main")
        assert response.status_code == 200, response.text
        assert response.json() == {"revision": 0, "state": EMPTY, "readOnly": True}
        refused = _post(client, _state(settings=[{"id": "s", "key": "k", "value": "v"}]), project="p", workspace="main")
        assert refused.status_code == 409
        assert "main" in refused.json()["error"].lower()


def test_upload_material_accepts_both_file_name_shapes():
    from backend.editor.agent_memory.desktop_v3_state import UPLOAD_FILE

    assert UPLOAD_FILE.fullmatch("8592ffac4a0f45c3a42fd6b04f57be56.jpg")
    assert UPLOAD_FILE.fullmatch("20260915-182309-30ce481a.jpg")
    assert UPLOAD_FILE.fullmatch("20260914-184355-19019148.png")
    assert not UPLOAD_FILE.fullmatch("../20260915-182309-30ce481a.jpg")
    assert not UPLOAD_FILE.fullmatch("20260915-182309-30ce481a.exe")


def _role_state(value):
    return _state(nodes={"focus": {
        "phase": "discover", "criteria": [], "steps": [], "agentRole": value,
    }})


def test_card_role_is_optional_and_defaults_to_no_role(tmp_path):
    """Starší uložený stav `agentRole` nemá; čte se beze změny a jde uložit dál."""
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        without = _state(nodes={"focus": {"phase": "discover", "criteria": [], "steps": []}})
        assert _post(client, without).status_code == 200
        assert _get(client).json()["state"]["nodes"]["focus"] == without["nodes"]["focus"]


def test_card_role_accepts_a_registry_id_and_explicit_null(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        assert _post(client, _role_state("role-backend")).status_code == 200
        assert _get(client).json()["state"]["nodes"]["focus"]["agentRole"] == "role-backend"
        assert _post(client, _role_state(None), expected=1).status_code == 200
        assert _get(client).json()["state"]["nodes"]["focus"]["agentRole"] is None


def test_card_role_outside_the_registry_is_rejected(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        refused = _post(client, _role_state("role-nikdo"))
        assert refused.status_code == 409 and "role" in refused.json()["error"].lower()
        assert _post(client, _role_state(7)).status_code == 409
        assert _get(client).json()["revision"] == 0
