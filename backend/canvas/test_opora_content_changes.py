"""Native content is proposed immutably, rebased by key and accepted by a human."""
import copy

import pytest

from backend.canvas.opora_content_acceptance import OporaContentAcceptance
from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords


def change(kind, target, field, value):
    return {"kind": kind, "target": target, "field": field, "value": value}


def propose(sparse, changes, subject="Content change"):
    _, authority, _ = sparse
    canvas = authority.canvas
    head = ChangesetRepository(canvas.db_for("draft"), "draft", "draft").head()
    return OporaContentChanges(canvas).create({**SCOPE, "expectedAcceptedHead": head,
                                              "subject": subject, "changes": changes}, AGENT)


def accepted(sparse, item, **extra):
    _, authority, _ = sparse
    return OporaContentAcceptance(authority.canvas).accept(item["id"], {**SCOPE,
        "expectedAcceptedHead": item["parentRevision"], "reviewedProposalId": item["id"],
        "adoptBaseContentDigest": item["baseContentDigest"] if item["requiresBaseContentAdoption"] else None, **extra}, HUMAN)


def test_all_three_kinds_require_exact_human_review_and_full_baseline_adoption(sparse):
    _, authority, refs = sparse
    item = propose(sparse, [change("text", refs["a"], "text", "Accepted article"),
                           change("drawing", "", "scene", {"elements": []}),
                           change("config", refs["a"], "rules", [{"id": "r", "text": "Must test", "kind": "must"}])])
    assert item["requiresBaseContentAdoption"] and len(item["baseContent"]) == 17
    assert authority.canvas.texts.read(("draft", "draft", refs["a"]))["revision"] == 0
    with pytest.raises(ValueError, match="adoption"):
        accepted(sparse, item, adoptBaseContentDigest=None)
    with pytest.raises(ValueError, match="exact"):
        accepted(sparse, item, reviewedProposalId="a" * 40)
    with pytest.raises(ValueError, match="human"):
        OporaContentAcceptance(authority.canvas).accept(item["id"], {**SCOPE,
            "expectedAcceptedHead": item["parentRevision"], "reviewedProposalId": item["id"],
            "adoptBaseContentDigest": item["baseContentDigest"]}, AGENT)
    result = accepted(sparse, item)
    assert result == accepted(sparse, item)
    assert result["graphManifestId"] and result["contentManifestId"]
    assert authority.canvas.texts.read(("draft", "draft", refs["a"]))["text"] == "Accepted article"
    manifest = ContentRecords(authority.canvas.db_for("draft"), "draft", "draft").read(result["contentManifestId"], manifest=True)
    assert len(manifest["entries"]) == 17


def test_independent_first_proposals_rebase_after_explicit_baseline_adoption(sparse):
    _, authority, refs = sparse
    left = propose(sparse, [change("text", refs["a"], "text", "A")])
    right = propose(sparse, [change("text", refs["b"], "text", "B")])
    first = accepted(sparse, left)
    with pytest.raises(ValueError, match="rebase"):
        accepted(sparse, right)
    moved = OporaContentChanges(authority.canvas).rebase(right["id"], {**SCOPE, "expectedAcceptedHead": first["id"]}, AGENT)
    assert moved["conflicts"] == [] and moved["proposal"]["supersedes"] == right["id"]
    assert not moved["proposal"]["requiresBaseContentAdoption"]
    second = accepted(sparse, moved["proposal"])
    assert second["parentRevision"] == first["id"]
    assert authority.canvas.texts.read(("draft", "draft", refs["a"]))["text"] == "A"
    assert authority.canvas.texts.read(("draft", "draft", refs["b"]))["text"] == "B"
    assert OporaContentChanges(authority.canvas).read("draft", "draft", right["id"])["proposal"] == right


def test_same_field_live_or_accepted_conflict_does_not_change_original(sparse):
    _, authority, refs = sparse
    first = propose(sparse, [change("text", refs["a"], "text", "One")])
    sibling = propose(sparse, [change("text", refs["a"], "text", "Two")])
    before = copy.deepcopy(sibling)
    result = accepted(sparse, first)
    conflict = OporaContentChanges(authority.canvas).rebase(sibling["id"], {**SCOPE, "expectedAcceptedHead": result["id"]}, AGENT)
    assert conflict["proposal"] is None and conflict["conflicts"][0]["target"] == refs["a"]
    assert OporaContentChanges(authority.canvas).read("draft", "draft", sibling["id"])["proposal"] == before


def test_first_adoption_recaptures_unrelated_baseline(sparse):
    _, authority, refs = sparse
    item = propose(sparse, [change("text", refs["a"], "text", "A")])
    with authority.canvas.db_for("draft") as db:
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", refs["b"], 1, "Unreviewed B", "now"))
    with pytest.raises(ValueError, match="base content changed"):
        accepted(sparse, item)


def test_native_write_and_manifest_and_accepted_head_roll_back_together(sparse, monkeypatch):
    _, authority, refs = sparse
    item = propose(sparse, [change("text", refs["a"], "text", "Rollback")])
    original = ContentRecords.insert

    def fail(self, record, *, manifest=False):
        if manifest:
            raise ValueError("Injected manifest failure")
        return original(self, record, manifest=manifest)

    monkeypatch.setattr(ContentRecords, "insert", fail)
    with pytest.raises(ValueError, match="manifest failure"):
        accepted(sparse, item)
    assert authority.canvas.texts.read(("draft", "draft", refs["a"]))["revision"] == 0
    assert ChangesetRepository(authority.canvas.db_for("draft"), "draft", "draft").head() == item["parentRevision"]
