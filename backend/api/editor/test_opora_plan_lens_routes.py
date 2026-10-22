"""`GET /api/oporahub/plan-lens`: identita jako review-lens, pohled projektu a oblasti, ETag/304."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.node.test_removals import ORIGIN, SCOPE, install_graph

URL = "/api/oporahub/plan-lens"
AGENT = {"x-opora-actor": "agent; name=planner"}


def graph():
    def node(key, x, y, kind="node", **extra):
        return {"id": key, "parentId": None, "kind": kind, "name": key, "purpose": "Účel karty.", "x": x, "y": y, **extra}
    return {"nodes": [node("oblast", 0, 0, "area", size={"w": 1000, "h": 1000}), node("karta", 10, 10),
                      node("venku", 4000, 4000)],
            "edges": []}


def test_plan_lens_route_contract(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph())
        session = dict(client.cookies)
        client.cookies.clear()  # bez cookie UI a bez X-Opora-Actor není kdo čte
        assert client.get(URL, params=SCOPE).status_code == 428
        client.cookies.update(session)
        assert client.get(URL, params=SCOPE).status_code == 200  # člověk s cookie UI
        first = client.get(URL, params=SCOPE, headers=AGENT)
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["kind"] == "plan" and body["area"] is None and body["graphify"] == {"available": False}
        assert body["stats"] == {"areas": 1, "cards": 2, "withCode": 0, "planned": 2, "standalone": 2, "unassigned": 1}
        assert {item["id"] for item in body["spec"]["nodes"]} == {"area:oblast", "nezarazeno:plan"}
        tag = first.headers["etag"]
        again = client.get(URL, params=SCOPE, headers={**AGENT, "If-None-Match": tag})
        assert again.status_code == 304 and again.content == b""
        area = client.get(URL, params={**SCOPE, "area": "oblast"}, headers=AGENT)
        assert area.status_code == 200 and area.headers["etag"] != tag
        assert [item["id"] for item in area.json()["spec"]["nodes"]] == ["card:karta"]
        assert client.get(URL, params={**SCOPE, "area": "karta"}, headers=AGENT).json()["code"] == "area_not_found"
        grown = graph()
        grown["nodes"].append({**grown["nodes"][2], "id": "dalsi", "name": "dalsi", "x": 6000})
        install_graph(client, grown)
        changed = client.get(URL, params=SCOPE, headers={**AGENT, "If-None-Match": tag})
        assert changed.status_code == 200 and changed.json()["stats"]["unassigned"] == 2
