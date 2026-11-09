"""Complete acceptance reviews the legacy baseline and preserves prior content authority."""
from copy import deepcopy

import pytest

from backend.canvas.opora_content_execution import require_accepted_content
from backend.canvas.test_opora_graph_changes import approve, edits
from backend.canvas.test_opora_graph_proposals import graphs, proposal, service

__all__ = ["edits", "graphs", "service"]


def plan():
    return {"draftVersion": 3, "nodes": [{"ref": "new", "kind": "node", "name": "Executable"}]}


def test_first_complete_manifest_requires_explicit_baseline_and_covers_empty_sources(edits, service):
    item = proposal(edits, plan=plan())
    assert item["contentBase"]["requiresAdoption"]
    with pytest.raises(ValueError, match="Explicit adoption"):
        approve(edits, item, adoptBaseContentDigest=None)
    accepted = approve(edits, item)
    graph = service.view("draft", "draft")["graph"]
    require_accepted_content(service, "draft", "draft", accepted["id"], [item["refs"]["new"], "a"], graph)
    assert approve(edits, item) == accepted


def test_reviewed_baseline_rejects_unrelated_text_drift(edits, service):
    item = proposal(edits, plan=plan())
    before = edits.context("draft", "draft")["acceptedHead"]
    with service.db_for("draft"):
        service.texts.save_in_transaction(("draft", "draft", "a"), 0, "Unreviewed unrelated instruction")
    with pytest.raises(ValueError, match="base content revision"):
        approve(edits, item)
    assert edits.context("draft", "draft")["acceptedHead"] == before
    assert item["refs"]["new"] not in {node["id"] for node in service.view("draft", "draft")["graph"]["nodes"]}


def test_prior_authority_is_not_replaced_by_unrelated_live_drift(edits, service):
    first = proposal(edits, plan=plan())
    approve(edits, first)
    with service.db_for("draft"):
        service.texts.save_in_transaction(("draft", "draft", "a"), 0, "Unreviewed unrelated instruction")
    second = proposal(edits, plan=plan())
    assert second["contentBase"]["requiresAdoption"] is False
    accepted = approve(edits, second)
    graph = service.view("draft", "draft")["graph"]
    require_accepted_content(service, "draft", "draft", accepted["id"], [second["refs"]["new"]], graph)
    with pytest.raises(ValueError, match="content differs"):
        require_accepted_content(service, "draft", "draft", accepted["id"], ["a"], graph)


def test_legacy_complete_record_reads_without_implicit_baseline_adoption(edits):
    from backend.canvas.opora_graph_change_records import validate_record
    item = proposal(edits, plan=plan())
    legacy = deepcopy(item)
    legacy.pop("contentBase")
    validate_record(legacy)
    damaged = deepcopy(item)
    damaged["contentBase"]["entries"][0]["value"] = "Tampered"
    with pytest.raises(ValueError, match="baseline"):
        validate_record(damaged)
