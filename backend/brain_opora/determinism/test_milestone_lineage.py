import pytest
from copy import deepcopy

from backend.brain_opora.determinism.milestone_lineage import semantic_compatible, _node
from backend.brain_opora.determinism.test_milestone_evidence import integration
from backend.brain_opora.determinism.test_milestones import service
from backend.canvas.test_opora_executions import accept_graph_change

__all__ = ["service", "integration"]


def test_semantic_site_design_and_component_fields_change_signature_while_preview_does_not():
    node = {"id": "n", "kind": "node", "site": {"kind": "page", "path": "/login", "goal": "Login"},
            "design": {"artifactUrl": "https://example.test/login", "version": "1", "previewUrl": "https://example.test/a.png"},
            "card": {"tech": "React", "states": ["ready"], "section": "form", "status": "ready"}}
    original = deepcopy(_node(node))
    node["design"]["previewUrl"] = "https://example.test/b.png"
    node["card"]["status"] = "running"
    assert _node(node) == original
    node["site"]["goal"] = "Authenticate with organization context"
    assert _node(node) != original


def test_relevant_purpose_change_invalidates_proof_but_unrelated_purpose_does_not(service, integration):
    _, _, _, proof = integration
    db = service.db_for("draft")
    accept_graph_change(service, {"updateNodes": [{"id": "a1", "fields": {"purpose": "Other planning purpose"}}]})
    semantic_compatible(db, "draft", "draft", proof["acceptedRevision"], ["n1"])
    accept_graph_change(service, {"updateNodes": [{"id": "n1", "fields": {"purpose": "New functional meaning"}}]})
    with pytest.raises(ValueError, match="Relevant accepted"):
        semantic_compatible(db, "draft", "draft", proof["acceptedRevision"], ["n1"])


def test_collaboration_dependency_contract_is_relevant_and_cycles_terminate(service, integration):
    from backend.canvas.test_opora_auto_rebase import propose
    from backend.canvas.test_opora_changesets import accept
    _, _, _, _ = integration
    current = accept_graph_change(service, {"edges": [
        {"from": "@n1", "to": "@n2", "port": "rule", "relation": "uses"},
        {"from": "@n2", "to": "@n1", "port": "rule", "relation": "communicates_with"}]})
    pinned = current["id"]
    semantic_compatible(service.db_for("draft"), "draft", "draft", pinned, ["n1"])
    accept(service, propose(service, "n2", goal="Changed collaborator contract"), pinned)
    with pytest.raises(ValueError, match="Relevant accepted"):
        semantic_compatible(service.db_for("draft"), "draft", "draft", pinned, ["n1"])
