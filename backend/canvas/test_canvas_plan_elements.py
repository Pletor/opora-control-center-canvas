"""Agent plans preserve domain types and meaning; invalid dependencies are atomic."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import ORIGIN, SCOPE, seed, send, snapshot


def element_plan():
    return {"nodes": [
        {"ref": "service", "kind": "node", "name": "Identity", "element": {"kind": "service"}, "text": "Service contract"},
        {"ref": "entity", "kind": "node", "name": "Organization", "element": {"kind": "entity"}},
    ], "edges": [{"from": "service", "to": "entity", "port": "next", "carries": "data", "relation": "uses", "reason": "Tenant isolation"}]}


def test_agent_plan_creates_elements_and_semantic_relations(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        response = send(client, seed(client), element_plan())
        assert response.status_code == 200, response.text
        refs = response.json()["refs"]
        graph = client.get("/api/view", params=SCOPE).json()["graph"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        assert nodes[refs["service"]]["element"] == {"kind": "service"}
        assert nodes[refs["entity"]]["element"] == {"kind": "entity"}
        [edge] = [edge for edge in graph["edges"] if edge.get("relation")]
        assert {key: edge[key] for key in ("source", "target", "port", "carries", "relation", "reason")} == {
            "source": refs["service"], "target": refs["entity"], "port": "next", "carries": "data", "relation": "uses", "reason": "Tenant isolation"}


@pytest.mark.parametrize("invalid", ["cycle", "element", "relation"])
def test_invalid_element_plan_writes_nothing(tmp_path, invalid):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        before = snapshot(client)
        body = element_plan()
        if invalid == "cycle":
            body["edges"][0]["relation"] = "requires"
            body["edges"].append({"from": "entity", "to": "service", "relation": "requires"})
        elif invalid == "element":
            body["nodes"][0]["element"]["kind"] = "task"
        else:
            body["edges"][0]["relation"] = "contains"
        response = send(client, digest, body)
        assert response.status_code == 409, response.text
        assert snapshot(client) == before
        assert len(client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]) == 3


def test_agent_extension_changes_element_role_without_changing_identity(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        revision = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
        response = send(client, digest, {"extend": [{"node": "@n0", "expectedRevision": revision, "element": {"kind": "service"}}]})
        assert response.status_code == 200, response.text
        graph = client.get("/api/view", params=SCOPE).json()["graph"]
        node = next(node for node in graph["nodes"] if node["id"] == "n0")
        assert node["element"] == {"kind": "service"} and node["parentId"] == "s0"
