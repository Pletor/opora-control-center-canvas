"""Accepted content participates in scoped execution and survives other acceptances."""
import pytest

from backend.canvas.graph import digest
from backend.canvas.opora_content_execution import selected_content
from backend.canvas.opora_execution_context import prepare
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_content_changes import accepted, change, propose
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_execution_lineage import graph_change
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.canvas.test_opora_graph_proposals import accept as accept_graph
from backend.canvas.test_opora_graph_proposals import proposal as graph_proposal
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords


def adopt(sparse):
    _, _, refs = sparse
    return accepted(sparse, propose(sparse, [change("text", refs["a"], "text", "A accepted")]))


def test_unrelated_content_acceptance_keeps_sparse_origin_related_change_revokes(sparse):
    _, authority, refs = sparse
    baseline = adopt(sparse)
    record = claimed(sparse)
    other = accepted(sparse, propose(sparse, [change("text", refs["b"], "text", "B accepted")]))
    renewed = authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
    assert renewed["assignmentDigest"] == record["assignmentDigest"]
    assert renewed["acceptedRevision"] == baseline["id"]
    assert renewed["contextValidation"]["checkedAcceptedRevision"] == other["id"]
    accepted(sparse, propose(sparse, [change("text", refs["a"], "text", "Changed A")]))
    with pytest.raises(ValueError, match="scope changed"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})


@pytest.mark.parametrize("context_v2", [False, True])
def test_claim_compares_actual_raw_content_to_accepted_manifest(sparse, context_v2):
    _, authority, refs = sparse
    adopt(sparse)
    with authority.canvas.db_for("draft") as db:
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", refs["a"], 2, "Unaccepted", "now"))
    if context_v2:
        with pytest.raises(ValueError, match="content differs"):
            prepare(authority, {**SCOPE, "nodeId": refs["a"], "contextProtocolVersion": 2})
    else:
        context = authority.context(**SCOPE, node=refs["a"])
        assert not context["available"] and "content differs" in context["unavailableReason"]


def test_spec_graph_addition_and_graph_patch_preserve_content_manifest(sparse):
    graphs, authority, refs = sparse
    original = adopt(sparse)
    spec = accept_spec(graphs.service, propose_spec(graphs.service, nodes=(refs["a"],)), original["id"])
    assert spec["contentManifestId"] == original["contentManifestId"]
    graph = accept_graph(graphs, graph_proposal(graphs, "New C"))
    assert graph["contentManifestId"] == original["contentManifestId"]
    patched = graph_change(graphs, {"updateNodes": [{"id": refs["b"], "fields": {"name": "B renamed"}}]})
    assert patched["contentManifestId"] == original["contentManifestId"]
    # A card added by a graph proposal has no content entries: accepted only in its native empty form.
    new_id = next(item["id"] for item in authority.canvas.view("draft", "draft")["graph"]["nodes"] if item["name"] == "New C")
    context = authority.context(**SCOPE, node=new_id)
    assert "content differs" not in (context.get("unavailableReason") or "")
    with authority.canvas.db_for("draft") as db:
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", new_id, 1, "Unreviewed", "now"))
    context = authority.context(**SCOPE, node=new_id)
    assert not context["available"] and "content differs" in context["unavailableReason"]


def test_hash_valid_revision_with_missing_content_manifest_fails_read(sparse):
    _, authority, _ = sparse
    original = adopt(sparse)
    db = authority.canvas.db_for("draft")
    repo = ChangesetRepository(db, "draft", "draft")
    content = {key: value for key, value in original.items() if key != "id"}
    content.update(parentRevision=original["id"], proposalId="e" * 40, contentManifestId="f" * 40)
    with db:
        db.execute("BEGIN IMMEDIATE")
        invalid = repo.insert(content)
    with pytest.raises(ValueError, match="Content record"):
        repo.read(invalid["id"])
    manifest = ContentRecords(db, "draft", "draft").read(original["contentManifestId"], manifest=True)
    assert manifest["entries"]


def test_config_accepted_aba_checks_intermediate_even_with_equal_endpoint_projection(sparse):
    _, authority, refs = sparse
    baseline = adopt(sparse)
    record = claimed(sparse)
    accepted(sparse, propose(sparse, [change("config", refs["a"], "rules", [{"id": "rule", "text": "Temporary", "kind": "must"}])]))
    restored = accepted(sparse, propose(sparse, [change("config", refs["a"], "rules", [])]))
    db = authority.canvas.db_for("draft")
    assert digest(selected_content(db, "draft", "draft", baseline, [refs["a"]])) == digest(
        selected_content(db, "draft", "draft", restored, [refs["a"]]))
    with pytest.raises(ValueError, match="scope changed within"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
