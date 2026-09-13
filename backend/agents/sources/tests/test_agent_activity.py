import pytest

from backend.agents.sources.agent_activity import AgentActivityJournal
from backend.agents.sources.agent_bindings import AgentBindings
from backend.domain.service import CanvasService

KNOWN_SOURCES = ("hermes-orchestrator", "oporacc-platno")


@pytest.fixture
def service(tmp_path):
    svc = CanvasService(tmp_path / "data")
    yield svc
    svc.close()


@pytest.fixture
def bindings(service):
    return AgentBindings(service, known_sources=KNOWN_SOURCES)


@pytest.fixture
def journal(service, bindings):
    return AgentActivityJournal(service, known_sources=KNOWN_SOURCES, bindings=bindings)


def _seed_node(service, node_id="n1", sector_id=None):
    nodes = [{"id": node_id, "parentId": sector_id, "kind": "node", "name": "Uzel", "purpose": "", "x": 0, "y": 0}]
    if sector_id:
        nodes.insert(0, {"id": sector_id, "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0})
    graph = {"nodes": nodes, "edges": []}
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", graph, current["digest"])


def _bind(bindings, node_id="n1", run_id="agents-sonnet", expected_revision=0):
    return bindings.bind(
        {
            "project": "draft",
            "workspace": "draft",
            "layer": "",
            "nodeId": node_id,
            "sourceId": "hermes-orchestrator",
            "runId": run_id,
            "sessionId": None,
            "expectedRevision": expected_revision,
            "confirmed": True,
        }
    )


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
        "authorType": "source_event",
    }
    base.update(overrides)
    return base


def test_capture_records_distinct_source_and_ingest_timestamps(service, bindings, journal):
    _seed_node(service)
    _bind(bindings)
    recorded = journal.capture(_entry())
    assert recorded["sourceTimestamp"] == "2026-09-10T01:00:55.512Z"
    assert recorded["ingestTimestamp"] is not None
    assert recorded["ingestTimestamp"] != recorded["sourceTimestamp"]


def test_capture_dedupes_same_source_event_id(service, bindings, journal):
    _seed_node(service)
    _bind(bindings)
    first = journal.capture(_entry())
    second = journal.capture(_entry())
    assert first["entryId"] == second["entryId"]
    listed = journal.list_for_node("draft", "draft", "n1")
    assert len(listed) == 1
    assert listed[0]["authorType"] == "source_event"
    # Deduplikace není ověření pravosti: fixture žádný externí zdroj nedokládá.
    assert listed[0]["sourceTrust"] == "unverified_source_claim"


@pytest.mark.parametrize("field", ["sourceId", "authorType"])
@pytest.mark.parametrize("value", [[], {}])
def test_capture_rejects_non_string_identity_without_internal_error(journal, field, value):
    """Neplatný JSON vstup vrací doménovou chybu, nikoli TypeError/HTTP 500."""
    with pytest.raises(ValueError):
        journal.capture(_entry(**{field: value}))


def test_client_cannot_confirm_fabricated_source_event(service, bindings, journal):
    """Potvrzená vazba běhu nedokazuje existenci ani obsah klientské události."""
    _seed_node(service)
    _bind(bindings)
    journal.capture(_entry(sourceEventId="fabricated-event", summary="Invented successful tests"))
    listed = journal.list_for_node("draft", "draft", "n1")
    assert listed[0]["sourceTrust"] == "unverified_source_claim"


def test_capture_rejects_foreign_node(service, bindings, journal):
    _seed_node(service)
    _bind(bindings)
    with pytest.raises(ValueError):
        journal.capture(_entry(nodeId="missing-node"))


def test_list_for_node_unknown_workspace_raises(service, journal):
    with pytest.raises(ValueError):
        journal.list_for_node("draft", "no-such-workspace", "n1")


def test_capture_is_append_only_distinct_entries_for_distinct_events(service, bindings, journal):
    _seed_node(service)
    _bind(bindings)
    journal.capture(_entry(sourceEventId="evt-1"))
    journal.capture(_entry(sourceEventId="evt-2"))
    listed = journal.list_for_node("draft", "draft", "n1")
    assert len(listed) == 2
    assert listed[0]["sourceEventId"] != listed[1]["sourceEventId"]


def test_capture_rejects_unbound_run(service, bindings, journal):
    _seed_node(service)
    with pytest.raises(ValueError):
        journal.capture(_entry())


def test_capture_rejects_unknown_source(service, bindings, journal):
    _seed_node(service)
    _bind(bindings)
    with pytest.raises(ValueError):
        journal.capture(_entry(sourceId="not-a-real-source"))


def test_capture_operator_note_marked_unverified(service, bindings, journal):
    _seed_node(service)
    _bind(bindings)
    recorded = journal.capture(_entry(sourceEventId="note-1", authorType="operator_note", summary="Ruční poznámka"))
    listed = journal.list_for_node("draft", "draft", "n1")
    entry = next(e for e in listed if e["entryId"] == recorded["entryId"])
    assert entry["authorType"] == "operator_note"
    assert entry["sourceTrust"] == "unverified_note"


def test_capture_redacts_secret_shaped_summary_before_persist(service, bindings, journal):
    _seed_node(service)
    _bind(bindings)
    journal.capture(_entry(summary="token=abcd1234efgh leaked in tool output"))
    listed = journal.list_for_node("draft", "draft", "n1")
    assert "abcd1234efgh" not in listed[0]["summary"]


def test_capture_allows_scope_via_sector_binding(service, bindings, journal):
    _seed_node(service, node_id="child", sector_id="sector")
    _bind(bindings, node_id="sector")
    journal.capture(_entry(nodeId="child"))
    listed = journal.list_for_node("draft", "draft", "child")
    assert len(listed) == 1


def test_list_for_node_derives_trust_ignoring_stale_persisted_value(service, bindings, journal):
    """Read boundary nesmí vracet starou hodnotu source_trust uloženou dřívější (chybnou)
    implementací; důvěra se vždy odvozuje z author_type podle aktuální politiky."""
    _seed_node(service)
    _bind(bindings)
    with service.lock, service.db:
        service.db.execute(
            "INSERT INTO agent_activity_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-entry",
                "draft",
                "draft",
                "n1",
                "hermes-orchestrator",
                "agents-sonnet",
                "legacy-evt",
                "2026-01-01T00:00:00.000Z",
                "2026-01-01T00:00:01.000Z",
                "tool_use",
                "Legacy summary text",
                "source_event",
                "source_confirmed",
            ),
        )
    listed = journal.list_for_node("draft", "draft", "n1")
    entry = next(e for e in listed if e["entryId"] == "legacy-entry")
    assert entry["sourceTrust"] == "unverified_source_claim"
    assert entry["summary"] == "Legacy summary text"


def test_list_for_node_unknown_legacy_author_type_falls_back_to_conservative_trust(service, bindings, journal):
    """Neznámý (starší) author_type nesmí odvodit žádnou důvěryhodnou úroveň; text
    původní události zůstává zachován beze změny."""
    _seed_node(service)
    _bind(bindings)
    with service.lock, service.db:
        service.db.execute(
            "INSERT INTO agent_activity_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-entry-2",
                "draft",
                "draft",
                "n1",
                "hermes-orchestrator",
                "agents-sonnet",
                "legacy-evt-2",
                "2026-01-01T00:00:00.000Z",
                "2026-01-01T00:00:01.000Z",
                "tool_use",
                "Older schema summary",
                "legacy_unknown_author",
                "source_confirmed",
            ),
        )
    listed = journal.list_for_node("draft", "draft", "n1")
    entry = next(e for e in listed if e["entryId"] == "legacy-entry-2")
    assert entry["sourceTrust"] not in ("source_confirmed",)
    assert entry["summary"] == "Older schema summary"


def test_list_for_node_legacy_row_does_not_leak_across_node_scope(service, bindings, journal):
    """Kombinace: legacy řádek na jednom uzlu, nový capture na jiném uzlu ve stejném
    workspace, scope isolation musí platit i po odvození důvěry při čtení."""
    _seed_node(service, node_id="n1", sector_id=None)
    graph = {
        "nodes": [
            {"id": "n1", "parentId": None, "kind": "node", "name": "n1", "purpose": "", "x": 0, "y": 0},
            {"id": "n2", "parentId": None, "kind": "node", "name": "n2", "purpose": "", "x": 1, "y": 1},
        ],
        "edges": [],
    }
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", graph, current["digest"])
    _bind(bindings, node_id="n1")
    _bind(bindings, node_id="n2")
    with service.lock, service.db:
        service.db.execute(
            "INSERT INTO agent_activity_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-entry-3",
                "draft",
                "draft",
                "n1",
                "hermes-orchestrator",
                "agents-sonnet",
                "legacy-evt-3",
                "2026-01-01T00:00:00.000Z",
                "2026-01-01T00:00:01.000Z",
                "tool_use",
                "Legacy on n1",
                "source_event",
                "source_confirmed",
            ),
        )
    journal.capture(_entry(nodeId="n2", sourceEventId="fresh-evt"))
    listed_n1 = journal.list_for_node("draft", "draft", "n1")
    listed_n2 = journal.list_for_node("draft", "draft", "n2")
    assert [e["entryId"] for e in listed_n1] == ["legacy-entry-3"]
    assert listed_n1[0]["sourceTrust"] == "unverified_source_claim"
    assert len(listed_n2) == 1
    assert listed_n2[0]["entryId"] != "legacy-entry-3"
    assert listed_n2[0]["sourceTrust"] == "unverified_source_claim"


def test_capture_same_event_id_is_isolated_per_node_scope(service, bindings, journal):
    graph = {
        "nodes": [
            {"id": "sector", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
            {"id": "n1", "parentId": "sector", "kind": "node", "name": "n1", "purpose": "", "x": 0, "y": 0},
            {"id": "n2", "parentId": "sector", "kind": "node", "name": "n2", "purpose": "", "x": 1, "y": 1},
        ],
        "edges": [],
    }
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", graph, current["digest"])
    _bind(bindings, node_id="n1")
    _bind(bindings, node_id="n2")
    journal.capture(_entry(nodeId="n1", sourceEventId="shared-evt"))
    journal.capture(_entry(nodeId="n2", sourceEventId="shared-evt"))
    listed_n1 = journal.list_for_node("draft", "draft", "n1")
    listed_n2 = journal.list_for_node("draft", "draft", "n2")
    assert len(listed_n1) == 1
    assert len(listed_n2) == 1
    assert listed_n1[0]["entryId"] != listed_n2[0]["entryId"]
