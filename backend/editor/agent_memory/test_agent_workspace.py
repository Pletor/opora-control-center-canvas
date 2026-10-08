"""Pracovní prostor agenta u karty: pět sekcí, částečný zápis pod CAS, smazání s kartou."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY_STATE = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}
GRAPH = {
    "nodes": [
        {"id": "sektor", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
        {"id": "focus", "parentId": "sektor", "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
        {"id": "soused", "parentId": "sektor", "kind": "node", "name": "Soused", "purpose": "", "x": 400, "y": 0},
    ],
    "edges": [],
}


def seed_graph(client, graph=None):
    view = client.get("/api/view", params=SCOPE).json()
    saved = client.post("/api/graph", headers=HEADERS,
                        json={**SCOPE, "graph": graph or GRAPH, "digest": view["digest"]})
    assert saved.status_code == 200, saved.text
    return saved.json()


def read(client, node_id="focus", **scope):
    return client.get("/api/desktop-v3/agent-workspace", params={**SCOPE, **scope, "nodeId": node_id})


def write(client, sections, expected=0, node_id="focus", by="agent", **overrides):
    payload = {**SCOPE, "nodeId": node_id, "expectedRevision": expected, "sections": sections, "by": by}
    payload.update(overrides)
    return client.post("/api/desktop-v3/agent-workspace", headers=HEADERS, json=payload)


def test_empty_workspace_is_revision_zero_with_empty_sections(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        response = read(client)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "revision": 0,
            "workspace": {"frame": "", "log": "", "failures": "", "fixes": "", "handoff": "",
                          "updatedAt": "", "by": "human"},
            "readOnly": False,
        }


def test_save_writes_revision_and_partial_update_keeps_other_sections(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        first = write(client, {"frame": "Dodat kartu.", "log": "Založil jsem modul."})
        assert first.status_code == 200, first.text
        assert first.json()["revision"] == 1
        assert first.json()["workspace"]["frame"] == "Dodat kartu."
        assert first.json()["workspace"]["by"] == "agent"
        assert first.json()["workspace"]["updatedAt"]
        assert first.json()["workspace"]["failures"] == ""

        second = write(client, {"handoff": "Pokračuj u testu."}, expected=1, by="human")
        assert second.status_code == 200, second.text
        stored = second.json()["workspace"]
        assert stored["handoff"] == "Pokračuj u testu."
        # Neuvedená sekce si drží hodnotu z předchozí revize.
        assert stored["frame"] == "Dodat kartu." and stored["log"] == "Založil jsem modul."
        assert stored["by"] == "human"
        assert second.json()["revision"] == 2
        assert read(client).json() == second.json()


def test_stale_revision_is_rejected_and_nothing_is_written(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, {"frame": "První"}).status_code == 200
        assert write(client, {"frame": "Druhý z jiného okna"}, expected=0).status_code == 409
        assert read(client).json()["workspace"]["frame"] == "První"
        assert read(client).json()["revision"] == 1


@pytest.mark.parametrize("sections,by", [
    ({"neznama": "x"}, "agent"),
    ({"frame": "x" * 12001}, "agent"),
    ({"frame": 5}, "agent"),
    ({"frame": "x"}, "robot"),
    ({"frame": "x"}, ""),
])
def test_unknown_section_long_text_and_foreign_author_are_rejected(tmp_path, sections, by):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, sections, by=by).status_code == 409
        assert read(client).json()["revision"] == 0


def test_section_at_the_limit_is_accepted(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, {"log": "x" * 12000}).status_code == 200
        assert len(read(client).json()["workspace"]["log"]) == 12000


def test_closed_card_refuses_the_write(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, {"frame": "Před uzavřením"}).status_code == 200
        state = {**EMPTY_STATE, "nodes": {"focus": {
            "phase": "discover", "criteria": [], "steps": [],
            "done": {"confirmed": True, "at": "2026-09-14T09:00:00+00:00", "by": "human", "note": "Hotovo."},
        }}}
        from backend.editor.agent_memory.test_completion_evidence import evidence
        state["nodes"]["focus"]["evidence"] = evidence()
        saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                            json={**SCOPE, "expectedRevision": 0, "state": state})
        assert saved.status_code == 200, saved.text
        refused = write(client, {"frame": "Po uzavření"}, expected=1)
        assert refused.status_code == 409
        assert "uzavřená" in refused.json()["error"]
        assert read(client).json()["workspace"]["frame"] == "Před uzavřením"
        # Sousední karta uzavřením ohniska omezená není.
        assert write(client, {"frame": "Soused píše dál."}, node_id="soused").status_code == 200


def test_missing_card_is_404_and_invalid_identifier_is_409(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert read(client, "nikdo").status_code == 404
        assert read(client, "ne platné!").status_code == 409
        assert write(client, {"frame": "x"}, node_id="nikdo").status_code == 409
        assert write(client, {"frame": "x"}, node_id="ne platné!").status_code == 409
        assert client.post("/api/desktop-v3/agent-workspace", headers=HEADERS,
                           json={**SCOPE, "nodeId": "focus", "sections": {}, "by": "agent"}).status_code == 409


def test_workspace_is_scoped_per_card_and_survives_restart(tmp_path):
    root = tmp_path / "data"
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, {"frame": "Ohnisko"}).status_code == 200
        assert write(client, {"frame": "Soused"}, node_id="soused").status_code == 200
        assert read(client, "soused").json()["workspace"]["frame"] == "Soused"
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        assert read(client).json()["workspace"]["frame"] == "Ohnisko"
        assert read(client, "soused").json()["workspace"]["frame"] == "Soused"


def test_removing_the_card_removes_its_workspace(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, {"frame": "Zmizí s kartou."}).status_code == 200
        assert write(client, {"frame": "Zůstává."}, node_id="soused").status_code == 200
        params = {**SCOPE, "kind": "node", "target": "focus"}
        preview = client.get("/api/removal-preview", params=params).json()
        removed = client.post("/api/remove", headers=HEADERS,
                              json={**params, "digest": preview["digest"], "confirmed": True})
        assert removed.status_code == 200, removed.text
        rows = app.state.service.db_for("draft").execute(
            "SELECT node_id FROM agent_workspace_revisions"
        ).fetchall()
        assert [row["node_id"] for row in rows] == ["soused"]
        assert read(client, "focus").status_code == 404
        assert read(client, "soused").json()["workspace"]["frame"] == "Zůstává."


def git_project(tmp_path):
    """Git projekt s uloženým grafem; `main` je pouze pro čtení stejně jako u textu uzlu."""
    import json
    import subprocess

    repo = tmp_path / "git"
    repo.mkdir()

    def run(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    run("init", "-b", "main")
    (repo / "opora-canvas.json").write_text(json.dumps(GRAPH), encoding="utf-8")
    run("add", ".")
    run("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture")
    app = create_app(tmp_path / "data")
    app.state.service.register_repository("p", "P", repo, "https://github.com/example/p", "main")
    return app


def test_main_of_a_git_project_is_read_only(tmp_path):
    scope = {"project": "p", "workspace": "main"}
    with TestClient(git_project(tmp_path), base_url=ORIGIN) as client:
        response = client.get("/api/desktop-v3/agent-workspace", params={**scope, "nodeId": "focus"})
        assert response.status_code == 200, response.text
        assert response.json() == {
            "revision": 0,
            "workspace": {"frame": "", "log": "", "failures": "", "fixes": "", "handoff": "",
                          "updatedAt": "", "by": "human"},
            "readOnly": True,
        }
        refused = client.post("/api/desktop-v3/agent-workspace", headers=HEADERS, json={
            **scope, "nodeId": "focus", "expectedRevision": 0, "sections": {"frame": "x"}, "by": "agent",
        })
        assert refused.status_code == 409
        assert "pouze pro čtení" in refused.json()["error"]


def summaries(client, **scope):
    return client.get("/api/desktop-v3/agent-workspace-summaries", params={**SCOPE, **scope})


def test_summaries_of_a_freshly_seeded_graph_are_all_zero(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        response = summaries(client)
        assert response.status_code == 200, response.text
        zero = {"filled": 0, "by": "human", "updatedAt": ""}
        assert response.json() == {
            "readOnly": False,
            "items": {"sektor": zero, "focus": zero, "soused": zero},
        }


def test_summaries_reflect_a_write_only_for_the_written_card(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, {"frame": "x", "log": "y"}, by="agent").status_code == 200
        items = summaries(client).json()["items"]
        assert items["focus"]["filled"] == 2
        assert items["focus"]["by"] == "agent"
        assert items["focus"]["updatedAt"]
        assert items["sektor"] == {"filled": 0, "by": "human", "updatedAt": ""}
        assert items["soused"] == {"filled": 0, "by": "human", "updatedAt": ""}


def test_summaries_skip_comment_nodes(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        graph = {
            "nodes": [*GRAPH["nodes"],
                      {"id": "note", "parentId": "sektor", "kind": "comment", "name": "Poznámka",
                       "purpose": "Text.", "x": 0, "y": 0}],
            "edges": GRAPH["edges"],
        }
        seed_graph(client, graph)
        items = summaries(client).json()["items"]
        assert "note" not in items
        assert set(items) == {"sektor", "focus", "soused"}


def test_summaries_of_git_main_are_read_only_with_zeros(tmp_path):
    scope = {"project": "p", "workspace": "main"}
    with TestClient(git_project(tmp_path), base_url=ORIGIN) as client:
        response = client.get("/api/desktop-v3/agent-workspace-summaries", params=scope)
        assert response.status_code == 200, response.text
        zero = {"filled": 0, "by": "human", "updatedAt": ""}
        assert response.json() == {
            "readOnly": True,
            "items": {"sektor": zero, "focus": zero, "soused": zero},
        }


def test_summaries_of_invalid_identifier_is_409(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert summaries(client, project="ne platné!").status_code == 409
        assert summaries(client, workspace="ne platné!").status_code == 409


def test_removing_a_sector_removes_the_workspace_of_every_descendant(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        seed_graph(client)
        assert write(client, {"frame": "Uzel pod sektorem."}).status_code == 200
        assert write(client, {"frame": "Sektor sám."}, node_id="sektor").status_code == 200
        params = {**SCOPE, "kind": "node", "target": "sektor"}
        preview = client.get("/api/removal-preview", params=params).json()
        removed = client.post("/api/remove", headers=HEADERS,
                              json={**params, "digest": preview["digest"], "confirmed": True})
        assert removed.status_code == 200, removed.text
        assert app.state.service.db_for("draft").execute(
            "SELECT COUNT(*) FROM agent_workspace_revisions"
        ).fetchone()[0] == 0
