"""Rebase, process reopening and simultaneous review/acceptance preserve exact evidence."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_proposal_review_service import ProposalReviews
from backend.canvas.test_opora_changesets import AGENT, SCOPE
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.canvas.test_opora_proposal_review_service import acknowledge, configure


def test_rebased_id_does_not_inherit_discussion_or_ack(sparse):
    _, authority, refs = sparse
    configure(sparse)
    original = propose_spec(authority.canvas, nodes=(refs["a"],))
    sibling = propose_spec(authority.canvas, nodes=(refs["b"],))
    acknowledge(sparse, "spec", original)
    acknowledge(sparse, "spec", sibling)
    head = accept_spec(authority.canvas, sibling, sibling["parentRevision"])
    moved = OporaChangesets(authority.canvas).rebase(original["id"], {**SCOPE, "expectedAcceptedHead": head["id"]}, AGENT)
    current = ProposalReviews(authority.canvas).context(*SCOPE.values(), "spec", moved["id"])
    assert not current["events"] and current["acknowledgement"] is None
    with pytest.raises(ValueError, match="acknowledgement"):
        accept_spec(authority.canvas, moved, moved["parentRevision"])


def test_receipt_review_and_policy_reopen_unchanged(sparse):
    _, authority, refs = sparse
    configure(sparse)
    item = propose_spec(authority.canvas, nodes=(refs["a"],))
    acknowledge(sparse, "spec", item)
    accepted = accept_spec(authority.canvas, item, item["parentRevision"])
    before = ProposalReviews(authority.canvas).context(*SCOPE.values(), "spec", item["id"])
    root = authority.canvas.root
    authority.canvas.close()
    reopened = CanvasService(root)
    try:
        current = ProposalReviews(reopened).context(*SCOPE.values(), "spec", item["id"])
        assert current == before and current["acceptedRevision"] == accepted["id"]
    finally:
        reopened.close()


def test_finding_vs_acceptance_serializes_under_actual_sqlite_transactions(sparse):
    _, authority, refs = sparse
    configure(sparse)
    item = propose_spec(authority.canvas, nodes=(refs["a"],))
    ack = acknowledge(sparse, "spec", item)
    other = CanvasService(authority.canvas.root)
    barrier = Barrier(2)

    def finding():
        barrier.wait()
        return ProposalReviews(other).append({**SCOPE, "proposalKind": "spec", "proposalId": item["id"],
            "expectedReviewHead": ack["id"], "idempotencyKey": "racing-finding", "body": {
                "type": "finding", "message": "Concurrent blocker", "anchor": "", "severity": "blocking"}}, AGENT)

    def accepting():
        barrier.wait()
        try:
            return accept_spec(authority.canvas, item, item["parentRevision"])
        except ValueError:
            return None

    try:
        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(finding), pool.submit(accepting)
            event, accepted = a.result(), b.result()
        context = ProposalReviews(authority.canvas).context(*SCOPE.values(), "spec", item["id"])
        assert context["reviewHead"] == event["id"] and context["openFindings"]
        if accepted:
            assert context["receipt"]["reviewHead"] == ack["id"]
        else:
            assert context["acceptedRevision"] is None and context["receipt"] is None
    finally:
        other.close()


def test_distinct_spec_proposals_race_one_accepted_head_only(sparse):
    _, authority, refs = sparse
    configure(sparse)
    left = propose_spec(authority.canvas, nodes=(refs["a"],))
    right = propose_spec(authority.canvas, nodes=(refs["b"],))
    acknowledge(sparse, "spec", left)
    acknowledge(sparse, "spec", right)
    other = CanvasService(authority.canvas.root)
    barrier = Barrier(2)

    def accepting(canvas, item):
        barrier.wait()
        try:
            return accept_spec(canvas, item, item["parentRevision"])
        except ValueError:
            return None

    try:
        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(accepting, authority.canvas, left)
            b = pool.submit(accepting, other, right)
            results = [a.result(), b.result()]
        assert sum(result is not None for result in results) == 1
        count = authority.canvas.db_for("draft").execute(
            "SELECT COUNT(*) FROM opora_spec_revisions WHERE project_id='draft' AND workspace_id='draft' AND proposal_id IN (?,?)",
            (left["id"], right["id"]),
        ).fetchone()[0]
        assert count == 1
    finally:
        other.close()
