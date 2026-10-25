"""H01: výslovné logické členství v oblasti (`memberOf`) a jeho hranice (docs/kontrakt-identity.md)."""

import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.areas import area_of, members_of, strip_area_membership
from backend.canvas.graph import validate_graph
from backend.canvas.test_canvas_plan import GRAPH, HEADERS, ORIGIN, SCOPE, seed, send


def node(node_id, parent=None, kind="node", **extra):
    return {"id": node_id, "parentId": parent, "kind": kind, "name": node_id, "purpose": "", "x": 0, "y": 0, **extra}


def area(area_id, parent=None):
    return {"id": area_id, "parentId": parent, "kind": "area", "name": area_id, "purpose": "",
            "x": 5000, "y": 5000, "size": {"w": 200, "h": 200}}


def harness(**members):
    """Stránka › vrstva › dva sektory a oblast vedle nich; `members` dává sektorům `memberOf`."""
    nodes = [
        node("page", kind="sector"),
        node("layer", "page"),
        node("s1", "layer", kind="sector"),
        node("s2", "layer", kind="sector"),
        node("task", "s1"),
        area("ar", "layer"),
        area("other", "page"),
    ]
    for item in nodes:
        if item["id"] in members:
            item["memberOf"] = members[item["id"]]
    return {"nodes": nodes, "edges": []}


def test_explicit_membership_is_kept_and_never_taken_from_position():
    graph = validate_graph(harness(s1="ar", s2="ar"))
    assert members_of("ar", graph["nodes"]) == ["s1", "s2"]
    # Poloha nic nepřidá: oblast leží jinde a geometrické `areaId` ji ke kartám nepřiřadí.
    assert area_of(graph["nodes"][2], graph["nodes"]) is None
    assert members_of("other", graph["nodes"]) == []


@pytest.mark.parametrize("members", [
    {"s1": "other"},   # oblast jiného rodiče (sourozenecká vrstva / stránka)
    {"s1": "s2"},      # členem lze být jen v oblasti
    {"s1": "missing"},  # oblast z jiného projektu či prostoru v tomto grafu neexistuje
    {"s1": "s1"},
])
def test_membership_outside_its_parent_or_graph_is_refused(members):
    with pytest.raises(ValueError, match="Členství v oblasti"):
        validate_graph(harness(**members))


def test_only_a_card_or_sector_carries_membership():
    graph = harness()
    graph["nodes"].append(node("note", "layer", kind="comment", memberOf="ar"))
    with pytest.raises(ValueError, match="jen uzel nebo sektor"):
        validate_graph(graph)
    graph = harness()
    graph["nodes"].append({**area("ar2", "layer"), "memberOf": "ar"})
    with pytest.raises(ValueError, match="jen uzel nebo sektor"):
        validate_graph(graph)


def test_move_or_vanished_area_is_refused_not_remapped():
    moved = harness(s1="ar")
    next(n for n in moved["nodes"] if n["id"] == "s1")["parentId"] = "page"
    with pytest.raises(ValueError, match="před přesunem karty nebo smazáním oblasti"):
        validate_graph(moved)
    gone = harness(s1="ar")
    gone["nodes"] = [n for n in gone["nodes"] if n["id"] != "ar"]
    with pytest.raises(ValueError, match="Členství v oblasti"):
        validate_graph(gone)
    # Cyklus rodičů dál odmítá stávající validace; členství ho neobchází.
    loop = harness()
    next(n for n in loop["nodes"] if n["id"] == "page")["parentId"] = "task"
    with pytest.raises(ValueError, match="cyklus"):
        validate_graph(loop)


def test_migration_is_reversible():
    before = harness()
    after = validate_graph(harness(s1="ar"))
    rolled = strip_area_membership(after)
    assert rolled == before
    assert validate_graph(rolled) == before
    assert "memberOf" in after["nodes"][2], "rollback vrací kopii, původní graf nemění"


def test_canvas_plan_sets_and_clears_membership_and_refuses_a_bad_one(tmp_path):
    def member(client, node_id):
        nodes = client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]
        return next(n for n in nodes if n["id"] == node_id).get("memberOf")

    def revision(client):
        return client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        # Sektor s0 a oblast a0 mají stejného rodiče (kořen): členství projde.
        joined = send(client, digest, {"extend": [{"node": "@s0", "expectedRevision": revision(client), "memberOf": "@a0"}]})
        assert joined.status_code == 200, joined.text
        assert member(client, "s0") == "a0"
        # Karta n0 leží pod s0, ne vedle oblasti: validace grafu ji odmítne a nic se nezapíše.
        wrong = send(client, joined.json()["digest"], {"extend": [{"node": "@n0", "expectedRevision": revision(client), "memberOf": "@a0"}]})
        assert wrong.status_code == 409 and member(client, "n0") is None
        bad = send(client, joined.json()["digest"], {"extend": [{"node": "@n0", "expectedRevision": revision(client), "memberOf": "@s0"}]})
        assert bad.status_code == 409 and "memberOf" in bad.text
        # Nová karta z dávky se k oblasti přihlásí přes ref i přes @id.
        planned = send(client, joined.json()["digest"], {"nodes": [
            {"ref": "lane", "kind": "area", "parent": None, "name": "Nová oblast", "size": {"w": 300, "h": 300}},
            {"ref": "new", "kind": "sector", "parent": None, "name": "Nový sektor", "purpose": "Sektor nové oblasti.", "memberOf": "lane"},
        ]})
        assert planned.status_code == 200, planned.text
        nodes = client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]
        new = next(n for n in nodes if n["name"] == "Nový sektor")
        assert next(n for n in nodes if n["id"] == new["memberOf"])["name"] == "Nová oblast"
        cleared = send(client, planned.json()["digest"], {"extend": [{"node": "@s0", "expectedRevision": revision(client), "memberOf": None}]})
        assert cleared.status_code == 200, cleared.text
        assert member(client, "s0") is None


def test_area_with_members_is_not_removed_until_membership_is_cleared(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        view = client.get("/api/view", params=SCOPE).json()
        graph = copy.deepcopy(GRAPH)
        graph["nodes"][0]["memberOf"] = "a0"
        saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        params = {**SCOPE, "kind": "node", "target": "a0"}
        refused = client.get("/api/removal-preview", params=params)
        assert refused.status_code in (400, 409, 422) and "členství" in refused.text
        graph["nodes"][0].pop("memberOf")
        cleared = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": saved.json()["digest"]})
        assert cleared.status_code == 200, cleared.text
        assert client.get("/api/removal-preview", params=params).status_code == 200
