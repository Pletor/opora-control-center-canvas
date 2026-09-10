import pytest

from backend.agent_activity import AgentActivityJournal
from backend.service import CanvasService


@pytest.fixture
def service(tmp_path):
    svc = CanvasService(tmp_path / "data")
    yield svc
    svc.close()


@pytest.fixture
def journal(service):
    return AgentActivityJournal(service)


def _seed_node(service, node_id="n1"):
    graph = {
        "nodes": [
            {"id": node_id, "parentId": None, "kind": "node", "name": "Uzel", "purpose": "", "x": 0, "y": 0},
        ],
        "edges": [],
    }
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", graph, current["digest"])


def _entry(**overrides):
    base = {
        "project": "draft",
        "workspace": "draft",
        "nodeId": "n1",
        "sourceId": "hermes-orchestrator",
        "runId": "agents-sonnet",
        "sourceEventId": "evt-1",
        "sourceTimestamp": "2026-09-10T01:00:55.512Z",
        "kind": "tool_use",
        "summary": "Bash: git status",
    }
    base.update(overrides)
    return base


def test_capture_records_distinct_source_and_ingest_timestamps(service, journal):
    _seed_node(service)
    recorded = journal.capture(_entry())
    assert recorded["sourceTimestamp"] == "2026-09-10T01:00:55.512Z"
    assert recorded["ingestTimestamp"] is not None
    assert recorded["ingestTimestamp"] != recorded["sourceTimestamp"]


def test_capture_dedupes_same_source_event_id(service, journal):
    _seed_node(service)
    first = journal.capture(_entry())
    second = journal.capture(_entry())
    assert first["entryId"] == second["entryId"]
    listed = journal.list_for_node("draft", "draft", "n1")
    assert len(listed) == 1


def test_capture_rejects_foreign_node(service, journal):
    _seed_node(service)
    with pytest.raises(ValueError):
        journal.capture(_entry(nodeId="missing-node"))


def test_list_for_node_unknown_workspace_raises(service, journal):
    with pytest.raises(ValueError):
        journal.list_for_node("draft", "no-such-workspace", "n1")


def test_capture_is_append_only_distinct_entries_for_distinct_events(service, journal):
    _seed_node(service)
    journal.capture(_entry(sourceEventId="evt-1"))
    journal.capture(_entry(sourceEventId="evt-2"))
    listed = journal.list_for_node("draft", "draft", "n1")
    assert len(listed) == 2
    assert listed[0]["sourceEventId"] != listed[1]["sourceEventId"]
