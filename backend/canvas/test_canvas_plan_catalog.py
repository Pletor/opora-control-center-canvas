"""Catalog insertion persists one real component and its complete initial assignment."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_completion_evidence import evidence
from backend.canvas.areas import area_of
from backend.canvas.canvas_plan_layout import overlapping
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed, send, snapshot


def component(parent="@n0", position=None):
    return {"nodes": [{
        "ref": "component", "kind": "node", "name": "Přihlášení", "parent": parent,
        "purpose": "Uživatel se přihlásí k účtu.", "card": {"layer": "frontend"},
        "position": position or {"x": 40, "y": 60},
        "spec": {"goal": "Uživatel se přihlásí k účtu.", "non_goals": "Registrace",
                 "acceptance": "Platný účet se přihlásí; neplatné heslo zobrazí chybu."},
        "criteria": ["Platný účet se přihlásí", "Neplatné heslo zobrazí chybu"],
        "blocks": [{"ref": "login", "title": "Odeslání formuláře", "text": "Předat přihlašovací údaje API",
                    "ports": [{"ref": "success", "label": "Přihlášen"}]}],
        "rules": [{"kind": "must_not", "text": "Neukládat heslo do logu."}],
    }]}


def test_plan_preserves_all_card_fields_in_graph_and_brief(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        plan = component()
        card = {'layer': 'backend', 'status': 'ready', 'model': 'sonnet', 'effort': 'high', 'due': '2026-10-10'}
        plan['nodes'][0]['card'] = card
        result = send(client, digest, plan)
        assert result.status_code == 200, result.text
        node_id = result.json()['refs']['component']
        view = client.get('/api/view', params=SCOPE).json()
        assert next(n for n in view['graph']['nodes'] if n['id'] == node_id)['card'] == card
        brief = client.get('/api/desktop-v3/node-brief', params={**SCOPE, 'nodeId': node_id}).json()
        assert all(brief['node'][key] == value for key, value in card.items())


@pytest.mark.parametrize("parent,expected_parent", [("@n0", "n0"), ("@s0", "s0"), ("@a0", None), (None, None)])
def test_catalog_creates_actual_child_with_spec_criteria_and_rules(tmp_path, parent, expected_parent):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        response = send(client, digest, component(parent))
        assert response.status_code == 200, response.text
        saved = response.json()
        node_id = saved["refs"]["component"]
        view = client.get("/api/view", params=SCOPE).json()
        nodes = view["graph"]["nodes"]
        node = next(item for item in nodes if item["id"] == node_id)
        assert node["parentId"] == expected_parent
        assert node["card"]["layer"] == "frontend"
        assert view["digest"] == saved["digest"] and saved["revision"] == 2
        assert overlapping(nodes) == []
        if parent == "@a0":
            assert area_of(node, nodes)["id"] == "a0"
        if parent == "@n0":
            assert (node["x"], node["y"]) == (40, 60)
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": node_id}).json()
        assert brief["goal"] == {"goal": "Uživatel se přihlásí k účtu.", "nonGoals": "Registrace",
                                  "acceptance": component()["nodes"][0]["spec"]["acceptance"]}
        assert [item["text"] for item in brief["definitionOfDone"]["criteria"]] == component()["nodes"][0]["criteria"]
        assert all(item["checked"] is False for item in brief["definitionOfDone"]["criteria"])
        assert brief["blocks"][0]["text"] == "Předat přihlašovací údaje API"
        assert brief["boundaries"]["projectRules"][0]["text"] == "Neukládat heslo do logu."
        own = next(card for card in brief["specification"]["cards"] if card["nodeId"] == node_id)
        assert own["spec"]["revision"] == 1


def test_collision_moves_new_component_only_and_dry_run_writes_nothing(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        initial = client.get("/api/view", params=SCOPE).json()["graph"]
        before = snapshot(client)
        plan = component("@s0", {"x": 0, "y": 0})
        preview = send(client, digest, plan, dry=True)
        assert preview.status_code == 200, preview.text
        assert snapshot(client) == before
        response = send(client, digest, plan)
        assert response.status_code == 200, response.text
        nodes = client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]
        assert all(node in nodes for node in initial["nodes"])
        inserted = next(node for node in nodes if node["id"] == response.json()["refs"]["component"])
        assert (inserted["x"], inserted["y"]) != (0, 0)
        assert overlapping(nodes) == []


def test_acceptance_without_optional_criteria_is_not_duplicated(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        plan = component()
        del plan["nodes"][0]["criteria"]
        saved = send(client, digest, plan)
        assert saved.status_code == 200, saved.text
        brief = client.get("/api/desktop-v3/node-brief", params={
            **SCOPE, "nodeId": saved.json()["refs"]["component"],
        }).json()
        assert brief["definitionOfDone"]["criteria"] == []
        assert brief["definitionOfDone"]["acceptance"] == plan["nodes"][0]["spec"]["acceptance"]


@pytest.mark.parametrize("change", [
    {"position": {"x": True, "y": 0}}, {"position": {"x": 1_000_001, "y": 0}},
    {"position": {"x": 0}}, {"card": {"layer": "unknown"}}, {"criteria": [""]},
    {"spec": {"goal": "x" * 4001}},
])
def test_bad_catalog_content_and_stale_digest_write_nothing(tmp_path, change):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        digest = seed(client)
        before = snapshot(client)
        plan = component()
        plan["nodes"][0].update(copy.deepcopy(change))
        assert send(client, digest, plan).status_code == 409
        assert snapshot(client) == before
        assert send(client, "0" * 64, component()).status_code == 409
        assert snapshot(client) == before
        assert app.state.service.db_for("draft").execute("SELECT COUNT(*) FROM node_spec_revisions").fetchone()[0] == 0


@pytest.mark.parametrize("closed", ["n0", "s0"])
def test_catalog_cannot_add_under_closed_card_or_ancestor(tmp_path, closed):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        state = client.get("/api/desktop-v3/state", params=SCOPE).json()
        node = state["state"]["nodes"].setdefault(closed, {"phase": "discover", "criteria": [], "steps": []})
        node["done"] = {"confirmed": True, "at": "2026-10-04T12:00:00+00:00", "by": "human", "note": ""}
        node["evidence"] = evidence()
        saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                            json={**SCOPE, "expectedRevision": state["revision"], "state": state["state"]})
        assert saved.status_code == 200, saved.text
        before = snapshot(client)
        response = send(client, digest, component("@n0"))
        assert response.status_code == 409 and "uzavřená" in response.json()["error"]
        assert snapshot(client) == before
