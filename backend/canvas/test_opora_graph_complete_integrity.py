"""Stable complete-plan identities, fragment pins, CAS and historical compatibility."""
from copy import deepcopy

import pytest

from backend.canvas.test_opora_changesets import AGENT, SCOPE
from backend.canvas.test_opora_graph_changes import approve, edits, working_edit
from backend.canvas.test_opora_graph_complete import full_plan
from backend.canvas.test_opora_graph_proposals import graphs, proposal, service
from backend.editor.brief_vault.brief_vault import BriefVault

__all__ = ["edits", "graphs", "service"]


def test_complete_receipt_replays_after_acceptance_without_duplicate_ids(edits):
    context = edits.context(**SCOPE)
    body = {**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
            "subject": "Complete receipt", "operationId": "full-plan-repeat", "plan": full_plan()}
    item = edits.create(body, AGENT)
    approve(edits, item)
    assert edits.create(body, AGENT) == item
    assert sum(row["id"] == item["id"] for row in edits.list(**SCOPE)["items"]) == 1
    changed = deepcopy(body)
    changed["plan"]["nodes"][0]["text"] = "Different intent"
    with pytest.raises(ValueError):
        edits.create(changed, AGENT)


def test_fragment_is_pinned_and_native_metadata_reloads(edits, service):
    vault = BriefVault(service)
    fragment = vault.apply({**SCOPE, "op": "create", "scopeNodeId": "", "discipline": "ux", "title": "Research", "text": "Observed evidence"},
                           actor="human", intake=False)["fragment"]
    plan = full_plan()
    plan["nodes"][0]["fragmentRef"] = {"fragmentId": fragment["id"]}
    item = proposal(edits, plan=plan)
    source = item["refs"]["source"]
    refs = item["contentEffects"]["after"]["nodes"][source]["fragmentRefs"]
    assert refs[0]["fragmentId"] == fragment["id"] and refs[0]["revision"] == fragment["revision"]
    assert refs[0]["contentHash"]
    assert edits.read(**SCOPE, record_id=item["id"])["contentEffects"] == item["contentEffects"]
    approve(edits, item)


def test_rebase_keeps_identity_for_unrelated_graph_change_and_rejects_conflicting_target(edits, service):
    plan = full_plan()
    plan["updateNodes"] = [{"id": "a", "fields": {"name": "Reviewed"}}]
    item = proposal(edits, plan=plan)
    working_edit(service, "b", purpose="Unrelated drift")
    context = edits.context(**SCOPE)
    rebased = edits.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                      "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert rebased["refs"] == item["refs"] and rebased["blocks"] == item["blocks"]
    assert rebased["supersedes"] == item["id"]
    working_edit(service, "a", name="Concurrent rename")
    context = edits.context(**SCOPE)
    with pytest.raises(ValueError, match="Affected graph"):
        edits.rebase(rebased["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                   "expectedGraphDigest": context["graphDigest"]}, AGENT)


def test_generated_security_block_uses_stable_identity(edits):
    plan = full_plan()
    plan["nodes"][0]["downloadsUrl"] = True
    item = proposal(edits, plan=plan)
    assert edits.read(**SCOPE, record_id=item["id"])["contentEffects"] == item["contentEffects"]


def test_complete_record_tamper_cannot_add_unreviewed_content(edits):
    from backend.canvas.opora_graph_change_records import validate_record
    item = proposal(edits, plan=full_plan())
    changed = deepcopy(item)
    changed["contentEffects"]["documents"][1]["value"] = "Unrequested instruction"
    with pytest.raises(ValueError, match="content differs"):
        validate_record(changed)
