"""Accepted graph authority and pending proposal history cannot silently disappear."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.migrate_architecture_backup import down
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_changesets import AGENT, HUMAN
from backend.canvas.test_opora_graph_git import git_graphs, prepared
from backend.canvas.workspace_graph_storage import save_authoritative
from database.repositories.opora_changesets import ChangesetRepository


def test_missing_authority_cannot_fallback_write_or_reenroll(git_graphs):
    service, scope, original, _data = git_graphs
    pid, wid = scope.values()
    item, payload = prepared(service, scope)
    accepted = OporaGraphAcceptance(service).accept(item["id"], payload, HUMAN)
    view = service.view(pid, wid)
    pending, pending_payload = prepared(service, scope)
    db = service.db_for(pid)
    db.execute("DELETE FROM workspace_graph_authority WHERE project_id=? AND workspace_id=?", (pid, wid))
    db.commit()
    for operation in (
        lambda: service.view(pid, wid),
        lambda: service.save_graph(pid, wid, view["graph"], view["digest"]),
        lambda: save_authoritative(service, pid, wid, view["graph"], {}, 0, False, "human", (), commit=True),
        lambda: OporaGraphAcceptance(service).accept(pending["id"], pending_payload, HUMAN),
    ):
        with pytest.raises(ValueError, match="authority is missing"):
            operation()
    assert ChangesetRepository(db, pid, wid).head() == accepted["id"]
    assert db.execute("SELECT COUNT(*) FROM workspace_graph_authority").fetchone()[0] == 0
    assert service.graph_file(pid, wid).read_bytes() == original


def test_initial_unaccepted_proposal_blocks_legacy_backup_restore(tmp_path, monkeypatch):
    service = CanvasService(tmp_path / "data")
    try:
        graphs = OporaGraphProposals(service)
        scope = {"project": "draft", "workspace": "draft"}
        context = graphs.context(**scope)
        item = graphs.create({**scope, "parentRevision": None, "expectedGraphDigest": context["graphDigest"],
                              "subject": "Initial pending plan", "plan": {"nodes": [
                                  {"ref": "new", "kind": "node", "name": "New task"}]}}, AGENT)

        def fail(*args):
            pytest.fail("Pending proposal history was not guarded before reading backup")

        monkeypatch.setattr("backend.canvas.migrate_architecture_backup.read_manifest", fail)
        with pytest.raises(ValueError, match="after graph proposal history"):
            down(service, "draft", "architecture-20261021T010000Z-12345678", force=True)
        assert graphs.read("draft", "draft", item["id"])["accepted"] is False
        assert ChangesetRepository(service.db_for("draft"), "draft", "draft").head() is None
    finally:
        service.close()
