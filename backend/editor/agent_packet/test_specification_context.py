"""Navigation follows domain/page identities while card layout stays non-semantic."""
import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, prepared
from backend.editor.agent_packet.specification_context import _navigation


def node(identifier, parent=None, site=None, kind="node"):
    value = {"id": identifier, "parentId": parent, "kind": kind,
             "name": identifier, "purpose": "", "x": 0, "y": 0}
    if site is not None:
        value["site"] = site
    return value


def pages():
    return [
        node("app", site={"kind": "application", "environments": []}, kind="sector"),
        node("home", "app", {"kind": "page", "path": "/"}),
        node("container", "home", kind="sector"),
        node("child", "container", {"kind": "page", "path": "/child"}),
        node("contact", "app", {"kind": "page", "path": "/contact"}),
    ]


def test_navigation_keeps_page_order_and_skips_transparent_containers():
    nodes = pages()
    expected = [{"domainId": "app", "pages": [
        {"nodeId": "home", "parentPageId": None},
        {"nodeId": "child", "parentPageId": "home"},
        {"nodeId": "contact", "parentPageId": None},
    ]}]
    assert _navigation(nodes) == expected
    assert _navigation([nodes[2], *nodes[:2], *nodes[3:]]) == expected
    other = node("other", site={"kind": "application", "environments": []}, kind="sector")
    assert _navigation([other, *nodes]) == expected


def test_brief_version_tracks_page_order_but_not_ordinary_node_order(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        current = client.get("/api/view", params=SCOPE).json()
        value = copy.deepcopy(current["graph"])
        value["nodes"] += pages()

        def save():
            previous = client.get("/api/view", params=SCOPE).json()
            response = client.post("/api/graph", headers=HEADERS,
                                   json={**SCOPE, "graph": value, "digest": previous["digest"]})
            assert response.status_code == 200, response.text
            response = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"})
            assert response.status_code == 200, response.text
            return response.json()

        first = save()
        assert first["specification"]["navigation"] == _navigation(value["nodes"])
        ordinary = value["nodes"].pop(0)
        ordinary["x"] += 500
        value["nodes"].append(ordinary)
        assert save()["contextVersion"] == first["contextVersion"]

        home = next(i for i, item in enumerate(value["nodes"]) if item["id"] == "home")
        contact = next(i for i, item in enumerate(value["nodes"]) if item["id"] == "contact")
        value["nodes"][home], value["nodes"][contact] = value["nodes"][contact], value["nodes"][home]
        reordered = save()
        assert reordered["contextVersion"] != first["contextVersion"]
        assert reordered["specification"]["navigation"][0]["pages"][0]["nodeId"] == "contact"
