"""A revised draft retains identities and never mutates accepted authority."""
from copy import deepcopy

import pytest

from backend.canvas.test_opora_graph_complete import full_plan
from backend.canvas.test_opora_graph_changes import approve, edits
from backend.canvas.test_opora_graph_proposals import graphs, proposal, service
from backend.canvas.payload_errors import NextStep

AUTHOR = {"kind": "agent", "name": "heart"}


def request(edits, old, operation="revision-one"):
    context = edits.context("draft", "draft")
    return {"project": "draft", "workspace": "draft", "expectedAcceptedHead": context["acceptedHead"],
            "expectedGraphDigest": context["graphDigest"], "subject": "Readable reviewed draft",
            "plan": deepcopy(old["plan"]), "observeResearchSources": True, "operationId": operation}


def test_revise_preserves_ids_and_old_record_and_exact_lost_response(edits, service):
    old = proposal(edits, plan=full_plan())
    before = deepcopy(service.view("draft", "draft")["graph"])
    payload = request(edits, old)
    payload["plan"]["nodes"][0].update(name="Readable title", text="Revised complete content")
    item = edits.revise(old["id"], payload, AUTHOR)
    assert item["id"] != old["id"] and item["supersedes"] == old["id"] and not item["accepted"]
    assert item["refs"] == old["refs"] and item["blocks"] == old["blocks"]
    assert item["parentRevision"] == old["parentRevision"]
    assert service.view("draft", "draft")["graph"] == before
    assert edits.read("draft", "draft", old["id"]) == {**old, "supersededBy": item["id"], "latestProposalId": item["id"]}
    assert edits.read("draft", "draft", item["id"]) == item
    assert edits.revise(old["id"], payload, AUTHOR) == item
    approve(edits, item)
    assert edits.revise(old["id"], payload, AUTHOR) == item  # receipt snapshot, no second write
    assert service.texts.read(("draft", "draft", old["refs"]["source"]))["text"] == "Revised complete content"


@pytest.mark.parametrize("change", ["kind", "ref"])
def test_shape_changes_fail_without_record_or_receipt(edits, change):
    old = proposal(edits, plan=full_plan())
    payload = request(edits, old)
    if change == "order":
        payload["plan"]["nodes"].reverse()
    elif change == "block":
        payload["plan"]["nodes"][0]["blocks"].append({"ref": "new", "title": "New"})
    else:
        payload["plan"]["nodes"][0][change] = "sector" if change == "kind" else "renamed"
    before = edits.list("draft", "draft")
    with pytest.raises(ValueError):
        edits.revise(old["id"], payload, AUTHOR)
    assert edits.list("draft", "draft") == before


def test_reorder_add_remove_restore_preserves_native_refs_blocks_and_edges(edits):
    old = proposal(edits, plan=full_plan())
    payload = request(edits, old)
    payload["plan"]["nodes"].reverse()
    payload["plan"]["nodes"].insert(0, {"ref": "extra", "kind": "node", "name": "Extra"})
    item = edits.revise(old["id"], payload, AUTHOR)
    assert {ref: item["refs"][ref] for ref in old["refs"]} == old["refs"]
    assert item["blocks"] == old["blocks"]
    assert item["additions"]["edges"] == old["additions"]["edges"]
    removed = request(edits, item, "remove-source")
    removed["plan"]["nodes"] = [node for node in removed["plan"]["nodes"] if node["ref"] != "source"]
    removed["plan"]["edges"] = []
    missing = edits.revise(item["id"], removed, AUTHOR)
    assert "source" not in missing["refs"]
    restored = request(edits, missing, "restore-source")
    restored["plan"] = deepcopy(item["plan"])
    back = edits.revise(missing["id"], restored, AUTHOR)
    assert back["refs"] == item["refs"] and back["blocks"] == item["blocks"]
    assert back["additions"]["edges"] == item["additions"]["edges"]
    restored["operationId"] = "wrong-restored-kind"
    next(node for node in restored["plan"]["nodes"] if node["ref"] == "source")["kind"] = "sector"
    with pytest.raises(ValueError, match="kind"):
        edits.revise(back["id"], restored, AUTHOR)
    assert edits.read("draft", "draft", old["id"]) == {**old, "supersededBy": item["id"], "latestProposalId": back["id"]}


def test_stale_context_accepted_proposal_and_missing_observation_reject(edits):
    old = proposal(edits, plan=full_plan())
    payload = request(edits, old)
    payload["observeResearchSources"] = False
    with pytest.raises(ValueError, match="explicit"):
        edits.revise(old["id"], payload, AUTHOR)
    payload = request(edits, old)
    payload["expectedGraphDigest"] = "0" * 64
    with pytest.raises(ValueError, match="changed"):
        edits.revise(old["id"], payload, AUTHOR)
    approve(edits, old)
    with pytest.raises(ValueError, match="unaccepted"):
        edits.revise(old["id"], request(edits, old), AUTHOR)


def test_new_accepted_head_requires_separate_explicit_rebase(edits):
    old = proposal(edits, plan=full_plan())
    another = proposal(edits, plan={"nodes": [{"ref": "elsewhere", "kind": "node", "name": "Other"}]})
    approve(edits, another)
    with pytest.raises(ValueError, match="accepted base changed"):
        edits.revise(old["id"], request(edits, old), AUTHOR)


def test_cross_scope_and_caller_identity_registry_are_rejected(edits):
    old = proposal(edits, plan=full_plan())
    payload = request(edits, old)
    with pytest.raises(ValueError):
        edits.revise(old["id"], {**payload, "workspace": "other"}, AUTHOR)
    with pytest.raises(ValueError):
        edits.revise(old["id"], {**payload, "identityAllocation": {}}, AUTHOR)
    assert not edits.read("draft", "draft", old["id"])["accepted"]


def test_receipt_binds_source_payload_and_actor(edits):
    old = proposal(edits, plan=full_plan())
    payload = request(edits, old)
    item = edits.revise(old["id"], payload, AUTHOR)
    with pytest.raises(NextStep):
        edits.revise(item["id"], payload, AUTHOR)
    with pytest.raises(NextStep):
        edits.revise(old["id"], {**payload, "subject": "Different"}, AUTHOR)
    with pytest.raises(NextStep):
        edits.revise(old["id"], payload, {"kind": "agent", "name": "other"})


def test_two_sessions_cannot_branch_or_accept_superseded_proposal(edits):
    from backend.canvas.opora_graph_revise import SupersededProposal
    old = proposal(edits, plan=full_plan())
    payload = request(edits, old)
    first = edits.revise(old["id"], payload, AUTHOR)
    with pytest.raises(SupersededProposal) as conflict:
        edits.revise(old["id"], {**payload, "operationId": "second-session"}, {"kind": "agent", "name": "other"})
    assert conflict.value.body()["latestProposalId"] == first["id"]
    assert edits.revise(old["id"], payload, AUTHOR) == first
    with pytest.raises(SupersededProposal):
        approve(edits, old)
    with pytest.raises(SupersededProposal):
        edits.rebase(old["id"], {key: payload[key] for key in ("project", "workspace", "expectedAcceptedHead", "expectedGraphDigest")}, AUTHOR)
    second = edits.revise(first["id"], request(edits, first, "next-revision"), AUTHOR)
    with pytest.raises(SupersededProposal) as conflict:
        edits.revise(old["id"], {**payload, "operationId": "third-session"}, AUTHOR)
    assert conflict.value.body()["latestProposalId"] == second["id"]
    assert edits.read("draft", "draft", old["id"]) == {**old, "supersededBy": first["id"], "latestProposalId": second["id"]}
    summary = next(item for item in edits.list("draft", "draft")["items"] if item["id"] == old["id"])
    assert summary["supersededBy"] == first["id"] and summary["latestProposalId"] == second["id"]
    assert edits.repository("draft", "draft").read(old["id"]) == {key: value for key, value in old.items() if key != "accepted"}


def test_block_port_and_edge_removal_restore_and_new_ids(edits):
    old = proposal(edits, plan=full_plan())
    payload = request(edits, old)
    payload["plan"]["nodes"][0]["blocks"].insert(0, {"ref": "another", "title": "Another", "ports": [{"ref": "out"}]})
    payload["plan"]["edges"].insert(0, {"from": "source", "to": "target", "port": "block", "block": "another", "blockPort": "out"})
    added = edits.revise(old["id"], payload, AUTHOR)
    assert added["blocks"]["source/proof"] == old["blocks"]["source/proof"]
    assert added["additions"]["edges"][1]["id"] == old["additions"]["edges"][0]["id"]
    removed = request(edits, added, "remove-blocks")
    removed["plan"]["nodes"][0]["blocks"] = []
    removed["plan"]["edges"] = []
    missing = edits.revise(added["id"], removed, AUTHOR)
    restore = request(edits, missing, "restore-blocks")
    restore["plan"] = deepcopy(added["plan"])
    back = edits.revise(missing["id"], restore, AUTHOR)
    assert back["blocks"] == added["blocks"]
    assert back["additions"]["edges"] == added["additions"]["edges"]
    assert edits.read("draft", "draft", back["id"]) == back


def test_explicit_revise_observes_fresh_map_proof_without_changing_old_pins(tmp_path):
    from backend.api.editor.test_brief_vault_routes import client_with_sector
    from backend.api.editor.test_research_routes import card, post
    from backend.editor.research.test_fragment_evidence import setup, fragment_plan
    from backend.canvas.opora_graph_changes import OporaGraphChanges
    with client_with_sector(tmp_path) as client:
        sparse, imported = setup(client)
        graphs, authority, refs = sparse
        original, _ = fragment_plan(client, sparse, imported["continuation"])
        old = graphs.create(original, AUTHOR)
        frozen = deepcopy(old["contentInputs"]["researchEvidenceByNode"])
        assert post(client, [card("finding", expectedRevision=1, content="New observed finding")], "revise-evidence").status_code == 200
        with pytest.raises(ValueError, match="inputs changed"):
            approve(OporaGraphChanges(authority.canvas), old)
        payload = request(graphs, old)
        fresh = graphs.revise(old["id"], payload, AUTHOR)
        pins = fresh["contentInputs"]["researchEvidenceByNode"][refs["a"]][0]
        assert next(pin for pin in pins["evidence"]["items"] if pin["id"] == "finding")["revision"] == 2
        assert pins["assessment"] == "observed-unverified" and pins["runStatus"] == "assigned"
        assert graphs.read("draft", "draft", old["id"])["contentInputs"]["researchEvidenceByNode"] == frozen
        approve(OporaGraphChanges(authority.canvas), fresh)
