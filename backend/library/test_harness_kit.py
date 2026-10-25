"""Pinned tools follow real accepted specifications and sparse execution authority."""
import copy
import hashlib

import pytest

from backend.library.harness_kit import kit_of_assignment, validate_kit
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_process_sync import ProcessSync
from backend.canvas.test_opora_changesets import AGENT, FIELDS, SCOPE, accept
from backend.canvas.test_opora_execution_context import claimed, prepared
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414


def kit(content="Run the repository checks before reporting completion."):
    return {"schema": "harness.kit/1", "problems": ["ts.references"], "resources": [{
        "slot": "rules.quality", "resource": "rule:quality", "category": "rules",
        "digest": hashlib.sha256(content.encode()).hexdigest(), "content": content,
        "requires": ["command:npm"]}]}


def propose_kit(sparse, value, extra_fields=None):
    graphs, _, refs = sparse
    changesets = OporaChangesets(graphs.service)
    context = changesets.context("draft", "draft")
    document = next(row for row in context["documents"] if row["nodeId"] == refs["a"])
    proposal = changesets.create({**SCOPE, "subject": "Pin tested tools", "parentRevision": context["acceptedHead"],
                                 "expectedGraphDigest": context["graphDigest"], "changes": [{
                                     "nodeId": refs["a"], "expectedRevision": document["revision"],
                                     "fields": {**FIELDS, **(extra_fields or {}), "harness": value}}]}, AGENT)
    return proposal, context["acceptedHead"]


def test_valid_empty_and_unicode_kits():
    validate_kit(kit("Ověř typy a testy před odevzdáním."))
    validate_kit({"schema": "harness.kit/1", "problems": ["typescript"], "resources": []})


@pytest.mark.parametrize("field,value", [("schema", "harness.kit/2"), ("problems", []),
    ("problems", ["same", "same"]), ("problems", ["x" * 201]), ("resources", [None])])
def test_invalid_kit_fields(field, value):
    with pytest.raises(ValueError):
        validate_kit({**kit(), field: value})


@pytest.mark.parametrize("patch", [{"digest": "a" * 64}, {"content": "changed"}, {"category": []},
    {"requires": ["same", "same"]}, {"requires": ["bad\n"]}, {"content": "bad\0"},
    {"content": "bad\ud800"}, {"slot": "constructor"}, {"resource": "bad\n"}, {"verified": True}])
def test_reject_wrong_content_claims_invalid_ids_and_authority_fields(patch):
    value = kit()
    value["resources"][0].update(patch)
    with pytest.raises(ValueError):
        validate_kit(value)


def test_resource_duplicates_and_total_bytes_are_bounded():
    value = kit()
    value["resources"].append(copy.deepcopy(value["resources"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_kit(value)
    with pytest.raises(ValueError, match="96 KiB"):
        validate_kit(kit("x" * (96 * 1024)))


def test_unaccepted_kit_does_not_enter_assignment_then_acceptance_pins_content(sparse):
    graphs, authority, refs = sparse
    proposed, head = propose_kit(sparse, kit())
    first = claimed(sparse)
    assert kit_of_assignment(first["assignment"], refs["a"]) is None
    authority.release(first["executionId"], {**SCOPE, "token": first["token"], "epoch": first["epoch"]})
    accept(graphs.service, proposed, head)
    second = claimed(sparse, request="accepted")
    assert kit_of_assignment(second["assignment"], refs["a"]) == kit()
    assert kit_of_assignment(second["assignment"], refs["b"]) is None
    assert first["assignmentDigest"] != second["assignmentDigest"]
    assert second["assignment"]["contextProtocolVersion"] == 2


def test_changed_live_kit_invalidates_active_context_without_rewriting_assignment(sparse):
    graphs, authority, refs = sparse
    proposed, head = propose_kit(sparse, kit())
    accept(graphs.service, proposed, head)
    first = claimed(sparse)
    saved = graphs.service.node_spec("draft", "draft", refs["a"])
    graphs.service.node_spec("draft", "draft", refs["a"], {**SCOPE, "node": refs["a"],
        "expected_revision": saved["revision"], "fields": {**FIELDS, "harness": kit("Different instructions")}})
    with pytest.raises(ValueError, match="scope changed|specifications differ"):
        authority.heartbeat(first["executionId"], {**SCOPE, "token": first["token"], "epoch": first["epoch"], "ttlSeconds": 60})
    assert kit_of_assignment(first["assignment"], refs["a"]) == kit()


def test_content_is_revalidated_after_transport_or_redaction():
    value = kit()
    assignment = {"documents": [{"nodeId": "a", "fields": {"harness": value}}]}
    value["resources"][0]["content"] = "[redacted]"
    with pytest.raises(ValueError, match="SHA-256"):
        kit_of_assignment(assignment, "a")


def test_redacted_accepted_content_blocks_preparation_before_issuing_pin(sparse):
    graphs, authority, _ = sparse
    proposed, head = propose_kit(sparse, kit("password=fictional_example_value"))
    accept(graphs.service, proposed, head)
    with pytest.raises(ValueError, match="SHA-256"):
        prepared(sparse)
    db = authority.canvas.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_execution_context_pins").fetchone()[0] == 0


def test_explicit_null_is_not_silently_treated_as_legacy_assignment():
    with pytest.raises(ValueError):
        kit_of_assignment({"documents": [{"nodeId": "a", "fields": {"harness": None}}]}, "a")


def test_kit_changes_affect_prepared_context_even_when_goal_is_same(sparse):
    graphs, authority, _ = sparse
    before = prepared(sparse)
    proposed, head = propose_kit(sparse, kit())
    accept(graphs.service, proposed, head)
    after = prepared(sparse)
    assert before["contextVersion"] != after["contextVersion"]
    with pytest.raises(ValueError):
        claimed(sparse, context=before)


def test_rebase_can_remove_kit_while_retaining_another_accepted_text_change():
    from backend.canvas.opora_auto_rebase_merge import spec

    base = {"nodeId": "a", "ownerWorkspace": "draft", "fields": {**FIELDS, "harness": kit()}}
    proposal = {"changes": [{"nodeId": "a", "acceptedBefore": base, "fields": FIELDS}]}
    latest = {**base, "fields": {**base["fields"], "goal": "Independently accepted text"}}
    outcome, conflicts, changes = spec(proposal, [latest])
    assert outcome == "clean" and conflicts == []
    assert changes[0]["fields"] == {**FIELDS, "goal": "Independently accepted text"}


def test_accepted_kit_refuses_legacy_context_and_claim_without_creating_an_execution(sparse):
    graphs, authority, refs = sparse
    proposed, head = propose_kit(sparse, kit())
    accept(graphs.service, proposed, head)
    context = authority.context("draft", "draft", refs["a"])
    # Claimable, but only through the sparse context: no legacy contextVersion a v1 office could claim with.
    assert context["available"] is True and context["contextProtocolVersion"] == 2 and context["contextVersion"] is None
    process = ProcessSync(graphs.service).read("draft", "draft", node=refs["a"])["items"][0]
    assert "contextProtocolVersion" not in (process["executionAvailability"]["unavailableReason"] or "")
    claim = AgentState(graphs.service).claims("draft", "draft", [{"nodeId": refs["a"], "status": "ready"}])[0]
    assert claim["status"] == "ready" and claim["context"]["contextProtocolVersion"] == 2
    with pytest.raises(ValueError, match="contextProtocolVersion 2"):
        authority.claim({**SCOPE, "nodeId": refs["a"], "requestId": "legacy", "ttlSeconds": 60,
                         "expectedAcceptedHead": head, "expectedContextVersion": "legacy"}, "agent:worker")
    assert graphs.service.db_for("draft").execute("SELECT COUNT(*) FROM opora_executions").fetchone()[0] == 0
    assert claimed(sparse)["assignment"]["contextProtocolVersion"] == 2
