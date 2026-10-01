"""Adresný blok: čtení jednoho bloku s dětmi/rodičem, zápis add/update/remove/todo pod CAS revizí."""
import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}

GRAPH = {
    "nodes": [
        {"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
        {"id": "dalsi", "parentId": None, "kind": "node", "name": "Další", "purpose": "", "x": 300, "y": 0},
    ],
    "edges": [],
}


def branch():
    return {"kind": "none", "targetId": "", "note": ""}


def block(bid, number, parent="", **overrides):
    item = {
        "id": bid, "number": number, "title": f"Blok {number}", "text": "", "tags": [], "todos": [], "images": [],
        "state": {"status": "open", "condition": "", "onMet": branch(), "onUnmet": branch()},
        "parentBlockId": parent, "ports": [],
    }
    item.update(overrides)
    return item


def base_state():
    """focus: b1 (kořen), b2 (dítě b1, "1.1"), b3 (kořen, "2")."""
    value = copy.deepcopy(EMPTY)
    value["nodes"] = {"focus": {
        "phase": "discover", "criteria": [], "steps": [],
        "blocks": [block("b1", "1"), block("b2", "1.1", parent="b1"), block("b3", "2")],
    }}
    return value


def prepared(client, state=None):
    view = client.get("/api/view", params=SCOPE).json()
    assert client.post("/api/graph", headers=HEADERS,
                       json={**SCOPE, "graph": GRAPH, "digest": view["digest"]}).status_code == 200
    saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                        json={**SCOPE, "expectedRevision": 0, "state": state or base_state()})
    assert saved.status_code == 200, saved.text
    return saved.json()["revision"]


def get_block(client, node_id, block_id):
    return client.get("/api/desktop-v3/block", params={**SCOPE, "nodeId": node_id, "blockId": block_id})


def send(client, body):
    return client.post("/api/desktop-v3/block", headers=HEADERS, json=body)


def op_payload(expected, op, node_id="focus"):
    return {**SCOPE, "nodeId": node_id, "expectedRevision": expected, "op": op}


def test_get_returns_block_with_children_and_parent(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        response = get_block(client, "focus", "b1")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["node"] == {"id": "focus", "name": "Ohnisko"}
        assert result["block"]["id"] == "b1"
        assert [item["id"] for item in result["children"]] == ["b2"]
        assert result["parent"] is None

        child = get_block(client, "focus", "b2").json()
        assert child["parent"]["id"] == "b1"
        assert child["children"] == []


def test_add_appends_root_block_and_renumbers(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "add", "parentBlockId": "", "title": "Nový blok", "text": "Obsah."}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["revision"] == revision + 1 and result["readOnly"] is False
        assert result["block"]["number"] == "3"
        assert result["block"]["title"] == "Nový blok" and result["block"]["text"] == "Obsah."
        assert result["block"]["tags"] == [] and result["block"]["todos"] == [] and result["block"]["ports"] == []
        assert result["block"]["state"] == {"status": "open", "condition": "", "onMet": branch(), "onUnmet": branch()}
        numbers = {item["number"] for item in result["state"]["nodes"]["focus"]["blocks"]}
        assert numbers == {"1", "1.1", "2", "3"}


def test_add_child_block_gets_nested_number(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "add", "parentBlockId": "b1", "title": "Dítě", "text": ""}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["block"]["number"] == "1.2"
        assert result["block"]["parentBlockId"] == "b1"


def test_add_with_unknown_parent_writes_nothing(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "add", "parentBlockId": "0" * 32, "title": "X", "text": ""}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 409, response.text
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert current["revision"] == revision


def test_update_patches_only_the_allowed_fields(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "update", "blockId": "b1", "patch": {"title": "Přejmenováno", "tags": ["a"]}}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["block"]["title"] == "Přejmenováno"
        assert result["block"]["tags"] == ["a"]
        assert result["block"]["number"] == "1"


def test_update_rejects_disallowed_patch_key(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "update", "blockId": "b1", "patch": {"number": "9"}}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 409


def test_remove_removes_block_and_descendants_and_renumbers(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "remove", "blockId": "b1"}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["block"] is None
        blocks = result["state"]["nodes"]["focus"]["blocks"]
        assert [item["id"] for item in blocks] == ["b3"]
        assert blocks[0]["number"] == "1"


def test_remove_clears_branches_pointing_at_removed_block(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        state = base_state()
        state["nodes"]["focus"]["blocks"][2]["state"]["onMet"] = {"kind": "block", "targetId": "b1", "note": "jde na b1"}
        revision = prepared(client, state)
        response = send(client, op_payload(revision, {"kind": "remove", "blockId": "b1"}))
        assert response.status_code == 200, response.text
        blocks = response.json()["state"]["nodes"]["focus"]["blocks"]
        remaining = next(item for item in blocks if item["id"] == "b3")
        assert remaining["state"]["onMet"] == branch()


def test_todo_add_toggle_and_remove(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        add = send(client, op_payload(revision, {
            "kind": "todo", "blockId": "b1", "todo": {"kind": "add", "text": "Udělat", "assignee": "sonnet"},
        }))
        assert add.status_code == 200, add.text
        added = add.json()
        todo = added["block"]["todos"][0]
        assert todo["text"] == "Udělat" and todo["assignee"] == "sonnet" and todo["done"] is False

        toggle = send(client, op_payload(added["revision"], {
            "kind": "todo", "blockId": "b1", "todo": {"kind": "toggle", "id": todo["id"]},
        }))
        assert toggle.status_code == 200, toggle.text
        toggled = toggle.json()
        assert toggled["block"]["todos"][0]["done"] is True

        remove = send(client, op_payload(toggled["revision"], {
            "kind": "todo", "blockId": "b1", "todo": {"kind": "remove", "id": todo["id"]},
        }))
        assert remove.status_code == 200, remove.text
        assert remove.json()["block"]["todos"] == []


def test_todo_toggle_of_unknown_id_writes_nothing(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "todo", "blockId": "b1", "todo": {"kind": "toggle", "id": "0" * 32}}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 409, response.text
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert current["revision"] == revision


def test_stale_revision_is_refused_and_nothing_is_written(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        op = {"kind": "update", "blockId": "b1", "patch": {"title": "X"}}
        assert send(client, op_payload(revision, op)).status_code == 200
        again = send(client, op_payload(revision, op))
        assert again.status_code == 409 and "revi" in again.json()["error"].lower()
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert current["revision"] == revision + 1
        assert current["state"]["nodes"]["focus"]["blocks"][0]["title"] == "X"


def test_closed_card_refuses_the_operation(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        state = base_state()
        state["nodes"]["focus"]["done"] = {"confirmed": True, "at": "2026-09-14T08:00:00+00:00",
                                           "by": "human", "note": "Zavřeno."}
        revision = prepared(client, state)
        op = {"kind": "update", "blockId": "b1", "patch": {"title": "X"}}
        response = send(client, op_payload(revision, op))
        assert response.status_code == 409 and "uzavřen" in response.json()["error"].lower()
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert current["revision"] == revision
        assert current["state"]["nodes"]["focus"]["blocks"][0]["title"] == "Blok 1"


def test_unknown_block_is_404_on_get_and_409_on_post(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        missing = "0" * 32
        assert get_block(client, "focus", missing).status_code == 404

        response = send(client, op_payload(revision, {"kind": "update", "blockId": missing, "patch": {"title": "X"}}))
        assert response.status_code == 409, response.text
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert current["revision"] == revision


def test_unknown_node_is_404_on_get_and_409_on_post(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        assert get_block(client, "neexistuje", "b1").status_code == 404

        response = send(client, op_payload(revision, {"kind": "update", "blockId": "b1", "patch": {"title": "X"}}, node_id="neexistuje"))
        assert response.status_code == 409, response.text
