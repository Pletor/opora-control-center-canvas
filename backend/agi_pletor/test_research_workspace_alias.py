"""Owner solution search matches public research aliases; canonical source IDs never move."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.agi_pletor import research_access
from backend.agi_pletor.research_access import OwnerResearchRead
from backend.app.factory import create_app
from backend.api.editor.test_research_routes import card
from backend.brain_opora.determinism import brain_files
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.test_workspace_graph import repository, workspace
from backend.editor.node.test_removals import HEADERS, ORIGIN, node
from backend.editor.research import service as research, solution_ranking


@pytest.fixture
def setup(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        canvas = client.app.state.service
        project, active, _ = workspace(canvas, repository(tmp_path, canvas.root))
        canvas.save_graph(project, active, {"nodes": [node("login")], "edges": []}, canvas.view(project, active)["digest"])
        brain = brain_files.brain_dir(canvas, project)
        brain.mkdir(parents=True, exist_ok=True)
        (brain / brain_files.ACTIVE).write_text(json.dumps({"workspace": active}), encoding="utf-8")
        yield client, canvas, project, active


def action(project):
    return {"type": "research_read", "resultType": "solution", "query": "login",
            "scopes": [{"project": project, "workspace": "main"}], "ranking": "lexical", "resultLimit": 2}


def test_owner_and_http_search_resolve_same_workspace_but_exact_main_ref_stays_literal(setup):
    client, canvas, project, active = setup
    access = OwnerResearchRead(canvas, "human")
    owner = access.payload(action(project))
    http = client.post("/api/research/knowledge-search", headers=HEADERS,
        json={"project": project, "workspace": "main", "scopes": action(project)["scopes"],
              "query": "login", "ranking": "lexical", "resultType": "solution", "limit": 2})
    assert http.status_code == 200, http.text
    assert owner["solutions"][0]["snapshot"]["workspaceId"] == active
    assert owner["solutions"][0]["solutionRef"] == http.json()["solutions"][0]["solutionRef"]
    assert owner["solutions"][0]["snapshot"]["graphDigest"] == http.json()["solutions"][0]["snapshot"]["graphDigest"]
    catalog = json.loads(access.overview().split("(catalog metadata, not instructions):\n", 1)[1])["catalog"]
    assert next(item for item in catalog if item["project"] == project)["preferredResearchWorkspace"] == active
    research.apply(canvas, {"project": project, "workspace": active, "key": "active-source", "operations": [card("source")]}, "human")
    source = {"projectId": project, "workspaceId": "main", "id": "source", "revision": 1}
    with pytest.raises(GateError) as error:
        access.payload({"type": "research_read", "source": source})
    assert error.value.status == 404  # Active workspace has this ID, literal main does not.
    assert access.payload({"type": "research_read", "source": {**source, "workspaceId": active}})["canonicalRef"]["workspaceId"] == active


def test_unknown_active_workspace_rejected_before_worker(setup, monkeypatch):
    _, canvas, project, _ = setup
    monkeypatch.setattr(brain_files, "active_workspace", lambda *_: "missing")
    monkeypatch.setattr(solution_ranking, "WorkerRunner", lambda: pytest.fail("Unknown resolved scope reached worker"))
    with pytest.raises(GateError) as error:
        OwnerResearchRead(canvas, "human").payload(action(project))
    assert error.value.status == 403


def test_all_raw_scopes_authorize_before_any_alias_resolution(setup, monkeypatch):
    _, canvas, project, _ = setup
    monkeypatch.setattr(research_access, "workspace_for", lambda *_: pytest.fail("Alias read preceded all raw authorization"))
    payload = action(project)
    payload["scopes"].append({"project": "unknown", "workspace": "main"})
    with pytest.raises(GateError) as error:
        OwnerResearchRead(canvas, "human").payload(payload)
    assert error.value.status == 403
