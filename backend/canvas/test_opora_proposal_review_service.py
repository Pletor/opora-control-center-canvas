"""Review is exact-ID, actor-aware, append-only and invalidated by subsequent events."""
import pytest

from backend.canvas.opora_proposal_review_service import ProposalReviews
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414


def configure(sparse, threshold="standard", enabled=True, block=True):
    reviews = ProposalReviews(sparse[1].canvas)
    current = reviews.policy(**SCOPE)
    return reviews.configure({**SCOPE, "expectedPolicyHead": current["policyHead"], "enabled": enabled,
        "rules": {"requireAcknowledgementFrom": threshold, "blockOpenFindings": block}}, HUMAN)


def append(sparse, kind, item, body, key="event", by=HUMAN, expected="current"):
    reviews = ProposalReviews(sparse[1].canvas)
    head = reviews.context(*SCOPE.values(), kind, item["id"])["reviewHead"] if expected == "current" else expected
    return reviews.append({**SCOPE, "proposalKind": kind, "proposalId": item["id"],
        "expectedReviewHead": head, "idempotencyKey": key, "body": body}, by)


def acknowledge(sparse, kind, item, key="ack"):
    context = ProposalReviews(sparse[1].canvas).context(*SCOPE.values(), kind, item["id"])
    return append(sparse, kind, item, {"type": "ack", "policyId": context["policyHead"],
        "riskDigest": context["risk"]["digest"], "parentAcceptedHead": context["acceptedHead"]}, key)


def test_comment_finding_anchor_resolution_and_no_independent_vote_claim(sparse):
    _, authority, refs = sparse
    configure(sparse)
    item = propose_spec(authority.canvas, nodes=(refs["a"],))
    finding = append(sparse, "spec", item, {"type": "finding", "message": "<script>plain text</script>",
        "anchor": "/changes/0/fields/goal", "severity": "blocking"}, by=AGENT)
    assert finding["message"] == "<script>plain text</script>"
    with pytest.raises(ValueError, match="human"):
        append(sparse, "spec", item, {"type": "resolve", "targetEventId": finding["id"], "resolution": "accepted", "reason": "Explained"}, "resolve", AGENT)
    acknowledge(sparse, "spec", item)
    with pytest.raises(ValueError, match="blocking"):
        accept_spec(authority.canvas, item, item["parentRevision"])
    append(sparse, "spec", item, {"type": "resolve", "targetEventId": finding["id"], "resolution": "accepted", "reason": "Human accepts this tradeoff"}, "resolve")
    context = ProposalReviews(authority.canvas).context(*SCOPE.values(), "spec", item["id"])
    assert not context["openFindings"] and not context["eligible"]
    assert "independent" in context["identityPolicy"]
    acknowledge(sparse, "spec", item, "ack-after-resolution")
    accepted = accept_spec(authority.canvas, item, item["parentRevision"])
    receipt = ProposalReviews(authority.canvas).receipt(*SCOPE.values(), accepted["id"])["receipt"]
    assert receipt["ackId"] and receipt["policyId"] and receipt["proposalId"] == item["id"]


def test_later_note_and_changed_policy_invalidate_ack_exact_event_retry_is_historical(sparse):
    _, authority, refs = sparse
    configure(sparse)
    item = propose_spec(authority.canvas, nodes=(refs["a"],))
    first = acknowledge(sparse, "spec", item)
    note = append(sparse, "spec", item, {"type": "comment", "message": "A later note", "anchor": ""}, "note")
    with pytest.raises(ValueError, match="acknowledgement"):
        accept_spec(authority.canvas, item, item["parentRevision"])
    configure(sparse, block=False)
    replay = append(sparse, "spec", item, {"type": "ack", "policyId": first["policyId"], "riskDigest": first["riskDigest"],
        "parentAcceptedHead": first["parentAcceptedHead"]}, "ack", expected=None)
    assert replay == first
    current = ProposalReviews(authority.canvas).context(*SCOPE.values(), "spec", item["id"])
    assert current["reviewHead"] == note["id"] and current["acknowledgement"] is None
    acknowledge(sparse, "spec", item, "current-policy")
    result = accept_spec(authority.canvas, item, item["parentRevision"])
    # Already accepted proposal replay is independent of newly changed policy/review.
    configure(sparse)
    assert accept_spec(authority.canvas, item, item["parentRevision"]) == result


@pytest.mark.parametrize("anchor", ["/missing", "/changes/99", "/changes/00", "/changes/~2", "changes/0"])
def test_anchor_must_resolve_within_actual_native_proposal(sparse, anchor):
    _, authority, refs = sparse
    item = propose_spec(authority.canvas, nodes=(refs["a"],))
    with pytest.raises(ValueError, match="anchor|pointer"):
        append(sparse, "spec", item, {"type": "comment", "message": "Bounded", "anchor": anchor})


def test_actor_idempotency_and_stale_cas_do_not_append(sparse):
    _, authority, refs = sparse
    item = propose_spec(authority.canvas, nodes=(refs["a"],))
    body = {"type": "comment", "message": "Original", "anchor": ""}
    first = append(sparse, "spec", item, body, by=AGENT)
    assert append(sparse, "spec", item, body, by=AGENT, expected=None) == first
    with pytest.raises(ValueError, match="idempotency"):
        append(sparse, "spec", item, body, by=HUMAN, expected=None)
    with pytest.raises(ValueError, match="CAS"):
        append(sparse, "spec", item, body, key="stale", expected=None)
    with pytest.raises(ValueError):
        ProposalReviews(authority.canvas).context(*SCOPE.values(), "content", item["id"])
