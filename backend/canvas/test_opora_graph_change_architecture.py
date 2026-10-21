"""Shared architecture adoption is explicit, immutable and does not approve content drift."""
from copy import deepcopy

import pytest

from backend.canvas.opora_graph_records import combined
from backend.canvas.test_opora_changesets import AGENT, FIELDS, SCOPE
from backend.canvas.test_opora_graph_changes import (
    approve,
    change,
    edits,
    graphs,
    service,
    working_edit,
)

__all__ = ["edits", "graphs", "service"]


def rename_architecture(service, name="Current domain"):
    architecture = service.architecture.read("draft")
    graph = deepcopy(architecture["graph"])
    graph["nodes"][0]["name"] = name
    service.architecture.save({**SCOPE, "expectedRevision": architecture["revision"], "graph": graph}, actor="human")


def test_context_adoption_is_explicit_and_does_not_write_architecture(edits, service):
    rename_architecture(service)
    working_edit(service, "b", purpose="Unreviewed working purpose")
    item = change(edits, {"adoptArchitectureContext": True})
    before = deepcopy(service.architecture.read("draft"))
    assert {item["nodeId"] for item in item["architectureDocuments"]} == {"app", "page"}
    revision = approve(edits, item)
    assert service.architecture.read("draft") == before
    manifest = edits.repository("draft", "draft").read(revision["graphManifestId"], manifest=True)
    accepted = {node["id"]: node for node in combined(manifest)["nodes"]}
    assert accepted["app"]["name"] == "Current domain"
    assert accepted["b"].get("purpose") != "Unreviewed working purpose"


def test_boundary_document_change_requires_new_explicit_review(edits, service):
    rename_architecture(service)
    item = change(edits, {"adoptArchitectureContext": True})
    current = service.node_spec("draft", "draft", "app")
    service.node_spec("draft", "draft", "app", {**SCOPE, "node": "app", "expected_revision": current["revision"], "fields": FIELDS})
    with pytest.raises(ValueError, match="dependency documents"):
        approve(edits, item)
    context = edits.specifications.context("draft", "draft")
    with pytest.raises(ValueError, match="dependency documents"):
        edits.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                 "expectedGraphDigest": context["graphDigest"]}, AGENT)
    fresh = change(edits, {"adoptArchitectureContext": True})
    assert next(doc for doc in fresh["architectureDocuments"] if doc["nodeId"] == "app")["fields"] == FIELDS
    approve(edits, fresh)


def test_context_adoption_removes_old_boundary_docs_only_from_new_revision(edits, service):
    old = edits.specifications.repository("draft", "draft").read(edits.specifications.repository("draft", "draft").head())
    architecture = service.architecture.read("draft")
    graph = deepcopy(architecture["graph"])
    graph["nodes"] = [node for node in graph["nodes"] if node["id"] != "page"]
    service.architecture.save({**SCOPE, "expectedRevision": architecture["revision"], "graph": graph}, actor="human")
    item = change(edits, {"adoptArchitectureContext": True})
    revision = approve(edits, item)
    assert "page" not in {doc["nodeId"] for doc in revision["documents"]}
    assert "page" in {doc["nodeId"] for doc in edits.specifications.repository("draft", "draft").read(old["id"])["documents"]}
