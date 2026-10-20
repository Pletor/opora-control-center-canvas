"""Actual Git workspace graph acceptance, durable authority, rollback and execution."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_review_scope import context as review_context
from backend.canvas.test_opora_changesets import AGENT, HUMAN
from backend.canvas.test_workspace_graph import GRAPH, repository, workspace
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority


@pytest.fixture
def git_graphs(tmp_path):
    data = tmp_path / "data"
    service = CanvasService(data)
    project, wid, _ = workspace(service, repository(tmp_path, data))
    service.save_graph(project, wid, GRAPH, service.view(project, wid)["digest"])
    original = service.graph_file(project, wid).read_bytes()
    try:
        yield service, {"project": project, "workspace": wid}, original, data
    finally:
        service.close()


def prepared(service, scope):
    graphs = OporaGraphProposals(service)
    context = graphs.context(**scope)
    item = graphs.create({**scope, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                          "subject": "Git plan", "plan": {"nodes": [{"ref": "new", "kind": "node", "name": "New task"}]}}, AGENT)
    payload = {**scope, "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
               "adoptBaseGraphDigest": item["graphDigest"] if item["requiresBaseAdoption"] else None}
    return item, payload


def test_git_acceptance_restart_preserves_file_and_execution_assignment(git_graphs):
    service, scope, original, data = git_graphs
    item, payload = prepared(service, scope)
    result = OporaGraphAcceptance(service).accept(item["id"], payload, HUMAN)
    assert service.graph_file(*scope.values()).read_bytes() == original
    assert review_context(service, *scope.values())["acceptedHead"] == result["id"]
    fresh = CanvasService(data)
    try:
        assert any(node["id"] == item["refs"]["new"] for node in fresh.view(*scope.values())["graph"]["nodes"])
        authority = ExecutionResults(fresh)
        context = authority.context(**scope, node=item["refs"]["new"])
        assert context["available"], context
        claim = authority.claim({**scope, "nodeId": item["refs"]["new"], "requestId": "after-restart", "ttlSeconds": 60,
            "expectedAcceptedHead": result["id"], "expectedContextVersion": context["contextVersion"]}, "agent:worker")
        assert claim["assignment"]["acceptedRevision"] == result["id"]
    finally:
        fresh.close()


def test_git_failed_acceptance_does_not_enroll_or_change_original(git_graphs, monkeypatch):
    service, scope, original, _ = git_graphs
    item, payload = prepared(service, scope)
    def fail(*args):
        raise RuntimeError("injected")
    monkeypatch.setattr(ChangesetRepository, "advance", fail)
    with pytest.raises(RuntimeError, match="injected"):
        OporaGraphAcceptance(service).accept(item["id"], payload, HUMAN)
    assert service.graph_file(*scope.values()).read_bytes() == original
    db = service.db_for(scope["project"])
    assert WorkspaceGraphAuthority(db, *scope.values()).read() is None
    assert ChangesetRepository(db, *scope.values()).head() is None
    assert db.execute("SELECT COUNT(*) FROM opora_graph_manifests").fetchone()[0] == 0


def test_source_deleted_after_proposal_cannot_be_accepted(git_graphs):
    service, scope, original, _ = git_graphs
    graphs = OporaGraphProposals(service)
    context = graphs.context(**scope)
    item = graphs.create({**scope, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
        "subject": "Read source", "plan": {"nodes": [{"ref": "read", "kind": "node", "name": "Read", "parent": "@sector",
        "sourceRef": {"origin": "existing", "kind": "file", "path": "README.md"}}]}}, AGENT)
    source = service.workspace_sources.root(*scope.values()) / "README.md"
    source.unlink()
    with pytest.raises(ValueError):
        OporaGraphAcceptance(service).accept(item["id"], {**scope, "expectedAcceptedHead": context["acceptedHead"],
            "expectedGraphDigest": context["graphDigest"], "adoptBaseGraphDigest": item["graphDigest"]}, HUMAN)
    assert service.graph_file(*scope.values()).read_bytes() == original
