import pytest

from backend.live_run.agent_bindings import AgentBindings
from backend.canvas.canvas_service import CanvasService


@pytest.fixture
def service(tmp_path):
    svc = CanvasService(tmp_path / "data")
    yield svc
    svc.close()


@pytest.fixture
def bindings(service):
    return AgentBindings(service, known_sources=("hermes-orchestrator", "oporacc-platno"))


def _seed_graph(service, sector_id="sec1", child_id="n1"):
    graph = {
        "nodes": [
            {"id": sector_id, "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
            {"id": child_id, "parentId": sector_id, "kind": "node", "name": "Uzel", "purpose": "", "x": 1, "y": 1},
        ],
        "edges": [],
    }
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", graph, current["digest"])


def test_bind_and_list_activity_for_node(service, bindings):
    _seed_graph(service)
    result = bindings.bind(
        {
            "project": "draft",
            "workspace": "draft",
            "layer": "",
            "nodeId": "n1",
            "sourceId": "hermes-orchestrator",
            "runId": "agents-sonnet",
            "sessionId": "abc123",
            "expectedRevision": 0,
            "confirmed": True,
        }
    )
    assert result["revision"] == 1
    listed = bindings.list_for_node("draft", "draft", "n1")
    assert listed["revision"] == 1
    assert len(listed["items"]) == 1
    assert listed["items"][0]["runId"] == "agents-sonnet"


def test_bind_requires_confirmation(service, bindings):
    _seed_graph(service)
    with pytest.raises(ValueError):
        bindings.bind(
            {
                "project": "draft",
                "workspace": "draft",
                "layer": "",
                "nodeId": "n1",
                "sourceId": "hermes-orchestrator",
                "runId": "agents-sonnet",
                "sessionId": None,
                "expectedRevision": 0,
                "confirmed": False,
            }
        )


def test_bind_rejects_foreign_node(service, bindings):
    _seed_graph(service)
    with pytest.raises(ValueError):
        bindings.bind(
            {
                "project": "draft",
                "workspace": "draft",
                "layer": "",
                "nodeId": "does-not-exist",
                "sourceId": "hermes-orchestrator",
                "runId": "agents-sonnet",
                "sessionId": None,
                "expectedRevision": 0,
                "confirmed": True,
            }
        )


def test_bind_rejects_unknown_source(service, bindings):
    _seed_graph(service)
    with pytest.raises(ValueError):
        bindings.bind(
            {
                "project": "draft",
                "workspace": "draft",
                "layer": "",
                "nodeId": "n1",
                "sourceId": "not-a-real-source",
                "runId": "agents-sonnet",
                "sessionId": None,
                "expectedRevision": 0,
                "confirmed": True,
            }
        )


def test_bind_cas_conflict_on_stale_revision(service, bindings):
    _seed_graph(service)
    payload = {
        "project": "draft",
        "workspace": "draft",
        "layer": "",
        "nodeId": "n1",
        "sourceId": "hermes-orchestrator",
        "runId": "agents-sonnet",
        "sessionId": None,
        "expectedRevision": 0,
        "confirmed": True,
    }
    bindings.bind(payload)
    with pytest.raises(ValueError):
        bindings.bind(payload)  # stale expectedRevision=0 again


def test_sector_aggregate_dedupes_across_children(service, bindings):
    _seed_graph(service)
    bindings.bind(
        {
            "project": "draft",
            "workspace": "draft",
            "layer": "",
            "nodeId": "n1",
            "sourceId": "hermes-orchestrator",
            "runId": "agents-sonnet",
            "sessionId": None,
            "expectedRevision": 0,
            "confirmed": True,
        }
    )
    bindings.bind(
        {
            "project": "draft",
            "workspace": "draft",
            "layer": "",
            "nodeId": "n1",
            "sourceId": "hermes-orchestrator",
            "runId": "agents-sonnet",
            "sessionId": None,
            "expectedRevision": 1,
            "confirmed": True,
        }
    )
    aggregate = bindings.sector_aggregate("draft", "draft", "sec1")
    assert len(aggregate["items"]) == 1


def test_unbound_excludes_already_bound_runs(service, bindings):
    _seed_graph(service)
    bindings.bind(
        {
            "project": "draft",
            "workspace": "draft",
            "layer": "",
            "nodeId": "n1",
            "sourceId": "hermes-orchestrator",
            "runId": "agents-sonnet",
            "sessionId": None,
            "expectedRevision": 0,
            "confirmed": True,
        }
    )
    candidates = [
        {"sourceId": "hermes-orchestrator", "runId": "agents-sonnet"},
        {"sourceId": "hermes-orchestrator", "runId": "ample-sonnet"},
    ]
    unbound = bindings.filter_unbound(candidates)
    assert unbound == [{"sourceId": "hermes-orchestrator", "runId": "ample-sonnet"}]
