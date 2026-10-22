"""Navigation follows domain/page identities while card layout stays non-semantic."""
import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, prepared
from backend.editor.agent_packet.specification_context import _navigation, capture_specification


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


def test_legacy_context_versions_compare_without_rewriting_originals(tmp_path):
    """Karta P3: projekce grafu se počítá jednou na digest grafu, ale contextVersion zůstává bit
    po bitu stejný jako před cache (hodnoty spočítané kódem 4bdec60 nad stejným plátnem); jinak by
    všechny uložené výsledky agentů vypadaly jako „změněné zadání“. Hodnoty přepočteny 2026-10-15
    po vyjmutí kritérií a kroků ze zadání (B1: tolerovaná stará data do otisku nevstupují)."""
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        current = client.get("/api/view", params=SCOPE).json()
        value = copy.deepcopy(current["graph"])
        value["nodes"] += pages()
        response = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": value, "digest": current["digest"]})
        assert response.status_code == 200, response.text
        from backend.canvas.graph import digest
        from backend.editor.agent_packet.assignment_scope import same_assignment
        from backend.editor.agent_packet.specification_context import _graph_part
        canvas = client.app.state.service
        shared = _graph_part(canvas, "draft", "draft", canvas.view("draft", "draft"))
        versions = []
        for identifier in ("focus", "app", "home"):
            current = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": identifier}).json()
            legacy = {**current["specification"], **shared}
            original = copy.deepcopy(legacy)
            version = digest(legacy)
            versions.append(version)
            assert same_assignment({"contextVersion": version, "specification": legacy}, current)
            assert legacy == original
        assert versions == ["1f209cbba29e48b8c126150087c763a4b44d1d505bb0ecd087ec0510622721be",
                            "0777a75333ca9444e92ca87f6750ef306b3eb6d01e0a91a90d75eec1ce0f28a9",
                            "612d0b7318f3d14a525eb33e01eae94203ab9d5201f8ac324f1997a28d423c99"]


def test_capture_under_the_project_lock_builds_the_view_once(tmp_path, monkeypatch):
    """Every related card's spec and drawing read the view again, and under the project lock `view` does not
    memoize: on a Git project that was hundreds of git subprocesses per OporaHub context read."""
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        service = client.app.state.service
        current = client.get("/api/view", params=SCOPE).json()
        value = copy.deepcopy(current["graph"])
        value["nodes"] += pages()
        client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": value, "digest": current["digest"]})
        built, original = [], service._view
        monkeypatch.setattr(service, "_view", lambda pid, wid: built.append(wid) or original(pid, wid))
        with service.graph_lock_for(SCOPE["project"]), service.lock_for(SCOPE["project"]):
            captured = capture_specification(service, SCOPE["project"], SCOPE["workspace"], "app")
        assert len(captured["specification"]["cards"]) > 2
        assert built == [SCOPE["workspace"]]
