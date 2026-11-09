"""Exact native graph snapshots preserve identities and require human authority."""
from copy import deepcopy

import pytest

from backend.canvas.opora_graph_candidate import create
from backend.canvas.test_opora_graph_changes import approve, edits
from backend.canvas.test_opora_graph_proposals import service, graphs
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

__all__ = ["service", "graphs", "edits"]


def prepare(edits, graph=None, operation="candidate", undo=False):
    context = edits.context(**SCOPE)
    graph = deepcopy(graph or context["workingGraph"])
    if graph == context["workingGraph"]:
        graph["nodes"][0]["name"] += " reviewed"
    payload = {**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
               "subject": "Full candidate", "graph": graph, "undo": undo, "operationId": operation}
    return payload, create(edits.service, payload, AGENT)


def test_exact_ids_comments_and_content_not_silently_approved(edits, service):
    before = deepcopy(service.view("draft", "draft")["graph"])
    state = deepcopy(DesktopV3State(service).current("draft", "draft"))
    graph = deepcopy(before)
    graph["nodes"].append({"id": "preserved-comment", "kind": "comment", "name": "Exact comment", "purpose": "Full comment text", "parentId": None, "x": 15, "y": 42})
    payload, item = prepare(edits, graph)
    assert service.view("draft", "draft")["graph"] == before
    assert edits.read(**SCOPE, record_id=item["id"]) == item
    accepted = approve(edits, item)
    assert service.view("draft", "draft")["graph"] == graph
    assert DesktopV3State(service).current("draft", "draft") == state
    assert all(d["nodeId"] != "preserved-comment" for d in accepted["documents"])
    assert create(service, payload, AGENT) == item
    assert approve(edits, item) == accepted


def test_undo_preserves_content_history_but_only_remaining_cards_are_selected(edits, service):
    from backend.canvas.test_opora_graph_complete import full_plan
    from backend.canvas.test_opora_graph_proposals import proposal
    from backend.canvas.opora_content_execution import require_accepted_content, selected_content
    from backend.canvas.opora_graph_execution import require_accepted_graph
    from database.repositories.opora_content_records import ContentRecords
    complete = proposal(edits, plan=full_plan())
    original = approve(edits, complete)
    source, target = complete["refs"]["source"], complete["refs"]["target"]
    manifest = ContentRecords(service.db_for("draft"), "draft", "draft").read(original["contentManifestId"], manifest=True)
    text = deepcopy(service.texts.read(("draft", "draft", source)))
    graph = deepcopy(service.view("draft", "draft")["graph"])
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != source]
    graph["edges"] = [e for e in graph["edges"] if source not in (e["source"], e["target"])]
    _, item = prepare(edits, graph, operation="undo-content", undo=True)
    accepted = approve(edits, item)
    assert source not in {d["nodeId"] for d in accepted["documents"]}
    assert service.texts.read(("draft", "draft", source)) == text
    assert ContentRecords(service.db_for("draft"), "draft", "draft").read(accepted["contentManifestId"], manifest=True) == manifest
    selected = selected_content(service.db_for("draft"), "draft", "draft", accepted, {target})
    assert all(e["target"] != source for e in selected["entries"])
    require_accepted_graph(service, "draft", "draft", accepted["id"], graph)
    require_accepted_content(service, "draft", "draft", accepted["id"], {target}, graph)


def test_full_candidate_stale_state_and_graph_refuse_without_mutation(edits, service):
    _, item = prepare(edits)
    view = service.view("draft", "draft")
    changed = deepcopy(view["graph"])
    changed["nodes"][0]["x"] += 1
    service.save_graph("draft", "draft", changed, view["digest"])
    with pytest.raises(ValueError, match="stale"):
        approve(edits, item)
    assert service.view("draft", "draft")["graph"] == changed


def test_candidate_undo_preserves_historical_content_and_rollback_on_failure(edits, service, monkeypatch):
    graph = deepcopy(service.view("draft", "draft")["graph"])
    target = graph["nodes"][-1]["id"]
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != target]
    graph["edges"] = [e for e in graph["edges"] if target not in (e["source"], e["target"])]
    with pytest.raises(ValueError, match="Deleting"):
        prepare(edits, graph)
    _, item = prepare(edits, graph, undo=True)
    before = deepcopy(service.view("draft", "draft")["graph"])
    head = edits.context(**SCOPE)["acceptedHead"]
    from database.repositories.opora_changesets import ChangesetRepository
    def fail(*args):
        raise RuntimeError("injected accepted-head failure")
    monkeypatch.setattr(ChangesetRepository, "advance", fail)
    with pytest.raises(RuntimeError, match="injected"):
        approve(edits, item)
    assert service.view("draft", "draft")["graph"] == before
    assert edits.context(**SCOPE)["acceptedHead"] == head


def test_changed_request_conflicts_and_agent_cannot_accept(edits):
    payload, item = prepare(edits)
    from backend.canvas.payload_errors import NextStep
    with pytest.raises(NextStep):
        create(edits.service, {**payload, "subject": "Different"}, AGENT)
    from backend.canvas.opora_graph_candidate_acceptance import accept
    with pytest.raises(ValueError):
        accept(edits.service, item["id"], {**SCOPE, "expectedAcceptedHead": item["parentRevision"], "expectedGraphDigest": item["graphDigest"], "adoptBaseGraphDigest": None, "reviewedChangesId": item["id"]}, AGENT)
