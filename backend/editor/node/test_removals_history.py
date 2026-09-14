from fastapi.testclient import TestClient

from backend.app.factory import create_app


def test_saved_assignment_history_survives_node_removal_and_restart(tmp_path):
    origin = "http://127.0.0.1:8740"
    headers = {"origin": origin}
    scope = {"project": "draft", "workspace": "draft", "node": "preserve"}
    app = create_app(tmp_path)
    with TestClient(app, base_url=origin) as client:
        graph = {
            "nodes": [
                {
                    "id": "preserve",
                    "parentId": None,
                    "kind": "node",
                    "name": "Saved assignment",
                    "purpose": "",
                    "x": 0,
                    "y": 0,
                }
            ],
            "edges": [],
        }
        view = client.get("/api/view").json()
        assert (
            client.post(
                "/api/graph",
                headers=headers,
                json={
                    "project": "draft",
                    "workspace": "draft",
                    "digest": view["digest"],
                    "graph": graph,
                },
            ).status_code
            == 200
        )
        fields = {
            "goal": "Zachovat důkaz",
            "non_goals": "",
            "acceptance": "Historie přežije odebrání",
        }
        assert (
            client.post(
                "/api/node-spec",
                headers=headers,
                json={**scope, "expected_revision": 0, "fields": fields},
            ).status_code
            == 200
        )
        before = [
            tuple(row) for row in app.state.service.db_for("draft").execute("SELECT * FROM node_spec_revisions")
        ]
        params = {"project": "draft", "workspace": "draft", "kind": "node", "target": "preserve"}
        preview = client.get("/api/removal-preview", params=params).json()
        assert (
            client.post(
                "/api/remove",
                headers=headers,
                json={**params, "digest": preview["digest"], "confirmed": True},
            ).status_code
            == 200
        )
        assert client.get("/api/node-spec", params=scope).status_code == 409
        assert [
            tuple(row) for row in app.state.service.db_for("draft").execute("SELECT * FROM node_spec_revisions")
        ] == before
    restarted = create_app(tmp_path)
    with TestClient(restarted, base_url=origin) as client:
        assert client.get("/api/view").json()["graph"]["nodes"] == []
        assert [
            tuple(row)
            for row in restarted.state.service.db_for("draft").execute("SELECT * FROM node_spec_revisions")
        ] == before
