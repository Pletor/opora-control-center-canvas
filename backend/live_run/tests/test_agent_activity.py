import pytest

from backend.live_run.agent_activity import AgentActivityJournal
from backend.canvas.canvas_service import CanvasService


@pytest.fixture
def service(tmp_path):
    svc = CanvasService(tmp_path / "data")
    yield svc
    svc.close()


@pytest.fixture
def journal(service):
    return AgentActivityJournal(service)


def _seed_node(service, node_id="n1", sector_id=None):
    nodes = [{"id": node_id, "parentId": sector_id, "kind": "node", "name": "Uzel", "purpose": "", "x": 0, "y": 0}]
    if sector_id:
        nodes.insert(0, {"id": sector_id, "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0})
    graph = {"nodes": nodes, "edges": []}
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", graph, current["digest"])


def _insert_entry(service, entry_id, node_id, event_id, summary, author_type, trust="source_confirmed"):
    with service.lock, service.db:
        service.db.execute(
            "INSERT INTO agent_activity_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                entry_id, "draft", "draft", node_id, "hermes-orchestrator", "agents-sonnet", event_id,
                "2026-01-01T00:00:00.000Z", "2026-01-01T00:00:01.000Z", "tool_use", summary, author_type, trust,
            ),
        )


def test_list_for_node_unknown_workspace_raises(service, journal):
    with pytest.raises(ValueError):
        journal.list_for_node("draft", "no-such-workspace", "n1")


def test_list_for_node_derives_trust_ignoring_stale_persisted_value(service, journal):
    """Read boundary nesmí vracet starou hodnotu source_trust uloženou dřívější (chybnou)
    implementací; důvěra se vždy odvozuje z author_type podle aktuální politiky."""
    _seed_node(service)
    _insert_entry(service, "legacy-entry", "n1", "legacy-evt", "Legacy summary text", "source_event")
    listed = journal.list_for_node("draft", "draft", "n1")
    entry = next(e for e in listed if e["entryId"] == "legacy-entry")
    assert entry["sourceTrust"] == "unverified_source_claim"
    assert entry["summary"] == "Legacy summary text"


def test_list_for_node_unknown_legacy_author_type_falls_back_to_conservative_trust(service, journal):
    """Neznámý (starší) author_type nesmí odvodit žádnou důvěryhodnou úroveň; text
    původní události zůstává zachován beze změny."""
    _seed_node(service)
    _insert_entry(service, "legacy-entry-2", "n1", "legacy-evt-2", "Older schema summary", "legacy_unknown_author")
    listed = journal.list_for_node("draft", "draft", "n1")
    entry = next(e for e in listed if e["entryId"] == "legacy-entry-2")
    assert entry["sourceTrust"] not in ("source_confirmed",)
    assert entry["summary"] == "Older schema summary"


def test_list_for_node_redacts_and_keeps_node_scope(service, journal):
    _seed_node(service, node_id="n1")
    _insert_entry(service, "e-n1", "n1", "evt-1", "token=abcd1234efgh leaked in tool output", "operator_note")
    listed = journal.list_for_node("draft", "draft", "n1")
    assert [e["entryId"] for e in listed] == ["e-n1"]
    assert "abcd1234efgh" not in listed[0]["summary"]
    assert listed[0]["sourceTrust"] == "unverified_note"
    assert journal.list_for_node("draft", "draft", "n1") == listed
