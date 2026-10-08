from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.node.test_removals import (
    HEADERS,
    ORIGIN,
    SCOPE,
    branch,
    desktop_state,
    edge_report,
    install_desktop_state,
    install_graph,
    nested_graph,
    state_block,
    state_node,
)


def remove(client, kind, target):
    params = {**SCOPE, "kind": kind, "target": target}
    preview = client.get("/api/removal-preview", params=params)
    assert preview.status_code == 200, preview.text
    result = client.post(
        "/api/remove", headers=HEADERS, json={**params, "digest": preview.json()["digest"], "confirmed": True}
    )
    assert result.status_code == 200, result.text
    return preview.json(), result.json()


def restore(client, recovery_id, digest=None):
    if digest is None:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
    return client.post(
        "/api/remove/restore", headers=HEADERS, json={**SCOPE, "recoveryId": recovery_id, "digest": digest}
    )


def test_selection_preview_and_remove_covers_targets_descendants_and_edges(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, nested_graph())
        preview, result = remove(client, "selection", "sector,keep2")
        assert preview["nodeIds"] == ["child", "child2", "deep", "keep2", "sector"]
        assert preview["nodeCount"] == 5 and preview["edgeCount"] == 3
        assert preview["label"] == "2 položky"
        assert [n["id"] for n in result["view"]["graph"]["nodes"]] == ["keep"]
        assert result["view"]["graph"]["edges"] == []
        assert isinstance(result["recoveryId"], str) and result["recoveryId"]
        single = client.get("/api/removal-preview", params={**SCOPE, "kind": "selection", "target": "keep"})
        assert single.json()["label"] == "keep"


def test_selection_rejects_missing_duplicate_and_invalid_ids(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, nested_graph())
        for target, message in (
            ("keep,missing", "Položka již v plátně neexistuje."),
            ("keep,keep", "Neplatný výběr"),
            ("keep,bad id", "Neplatný výběr"),
            ("", "Neplatný výběr"),
            (",".join(f"n{i}" for i in range(501)), "Neplatný výběr"),
        ):
            response = client.get("/api/removal-preview", params={**SCOPE, "kind": "selection", "target": target})
            assert response.status_code == 409 and message in response.json()["error"]


def test_node_and_edge_removals_return_recovery_id(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, nested_graph())
        _, edge = remove(client, "edge", "untouched")
        _, node = remove(client, "node", "keep2")
        assert edge["recoveryId"] != node["recoveryId"]


def test_restore_returns_nodes_edges_state_branches_and_agent_workspace(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        graph = nested_graph()
        install_graph(client, graph)
        install_desktop_state(
            client,
            desktop_state(
                nodes={
                    "sector": state_node(blocks=[state_block()]),
                    "deep": state_node(),
                    "keep": state_node(blocks=[state_block(bid="b-keep", on_met=branch("node", "child"))]),
                },
                edges={"outer": edge_report(), "inner": edge_report(summary="Vnitřní.")},
            ),
        )
        saved = client.post(
            "/api/desktop-v3/agent-workspace", headers=HEADERS,
            json={**SCOPE, "nodeId": "deep", "expectedRevision": 0, "sections": {"log": "Postup."}, "by": "agent"},
        )
        assert saved.status_code == 200, saved.text
        before_state = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]
        _, result = remove(client, "selection", "sector")
        state = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]
        assert state["nodes"]["keep"]["blocks"][0]["state"]["onMet"] == branch()

        response = restore(client, result["recoveryId"])
        assert response.status_code == 200, response.text
        restored = response.json()["view"]["graph"]
        assert [n["id"] for n in restored["nodes"]] == [n["id"] for n in graph["nodes"]]
        assert sorted(e["id"] for e in restored["edges"]) == ["inner", "outer", "untouched"]
        state = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]
        assert state["nodes"] == before_state["nodes"]
        assert state["edges"] == before_state["edges"]
        workspace = client.get("/api/desktop-v3/agent-workspace", params={**SCOPE, "nodeId": "deep"}).json()
        assert workspace["revision"] == 1 and workspace["workspace"]["log"] == "Postup."


def test_restore_keeps_newer_branch_and_is_single_use(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [*nested_graph()["nodes"]], "edges": []})
        install_desktop_state(
            client,
            desktop_state(nodes={"keep": state_node(blocks=[state_block(bid="b", on_met=branch("node", "keep2"))])}),
        )
        _, result = remove(client, "node", "keep2")
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        changed = current["state"]
        changed["nodes"]["keep"]["blocks"][0]["state"]["onMet"] = branch("node", "sector")
        assert client.post(
            "/api/desktop-v3/state", headers=HEADERS,
            json={**SCOPE, "expectedRevision": current["revision"], "state": changed},
        ).status_code == 200
        assert restore(client, result["recoveryId"]).status_code == 200
        state = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]
        assert state["nodes"]["keep"]["blocks"][0]["state"]["onMet"] == branch("node", "sector")
        again = restore(client, result["recoveryId"])
        assert again.status_code == 409 and again.json()["error"] == "Obnovení už bylo použito."


def test_restore_rejects_stale_digest_and_unknown_record(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, nested_graph())
        _, result = remove(client, "node", "keep2")
        stale = restore(client, result["recoveryId"], digest="stale")
        assert stale.status_code == 409
        assert stale.json()["error"] == "Plátno se změnilo v jiném okně. Obnovte ho."
        assert restore(client, "0" * 32).status_code == 409
        bad = client.post(
            "/api/remove/restore", headers=HEADERS,
            json={**SCOPE, "recoveryId": result["recoveryId"], "digest": "x", "extra": 1},
        )
        assert bad.status_code == 409
        assert "keep2" not in [n["id"] for n in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]]
        assert restore(client, result["recoveryId"]).status_code == 200
