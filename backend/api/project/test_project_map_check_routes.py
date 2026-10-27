from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.project.project_map_check_routes import create_project_map_check_router


def make_client(source_kind="git"):
    graph = {"nodes": [{"id": "app", "parentId": None, "kind": "sector", "site": {"kind": "application"}},
                       {"id": "p", "parentId": "app", "kind": "node", "site": {"kind": "page", "path": "/"}},
                       {"id": "a", "parentId": "p", "kind": "node"}, {"id": "b", "parentId": "p", "kind": "node"}],
             "edges": [{"id": "e1", "source": "a", "target": "b"}]}
    seen = []

    def view(project, wid):
        seen.append((project, wid))
        return {"graph": graph}

    service = SimpleNamespace(
        project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourceKind": source_kind}}), view=view)
    app = FastAPI()
    app.include_router(create_project_map_check_router(service))
    return TestClient(app), seen


def test_map_check_reads_the_accepted_graph_and_returns_findings():
    client, seen = make_client()
    body = client.get("/api/project-architecture/map-check", params={"project": "p1"}).json()
    assert seen == [("p1", "main")]
    assert body["findings"] == [{"rule": "page.no-goal", "nodeId": "p", "message": "Stránka nemá cíl (goal)."},
                                {"rule": "edge.carries-unset", "edgeId": "e1",
                                 "message": "Vazba neříká, co nese (carries)."}]
    assert body["summary"]["page.no-goal"] == 1 and body["summary"]["edge.carries-unset"] == 1


def test_map_check_uses_draft_without_git_and_requires_project():
    client, seen = make_client(source_kind="folder")
    assert client.get("/api/project-architecture/map-check", params={"project": "p1"}).status_code == 200
    assert seen == [("p1", "draft")]
    assert client.get("/api/project-architecture/map-check").status_code == 422
