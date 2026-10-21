"""All existing plan acceptors share one atomic active-policy gate and receipt."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_graph_change_acceptance import OporaGraphChangeAcceptance
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.opora_proposal_review_service import ProposalReviews
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE, baseline
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_content_changes import accepted as accept_content
from backend.canvas.test_opora_content_changes import change
from backend.canvas.test_opora_content_changes import propose as content_proposal
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.canvas.test_opora_graph_proposals import accept as accept_graph
from backend.canvas.test_opora_graph_proposals import proposal as graph_proposal
from backend.canvas.test_opora_proposal_review_service import acknowledge, configure
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_proposal_reviews import AcceptanceReceipts, ProposalReview


def native(sparse, kind):
    graphs, authority, refs = sparse
    if kind == "spec":
        item = propose_spec(authority.canvas, nodes=(refs["a"],))
        return item, lambda: accept_spec(authority.canvas, item, item["parentRevision"])
    if kind == "graph-addition":
        item = graph_proposal(graphs, "Added")
        return item, lambda: accept_graph(graphs, item)
    if kind == "content":
        item = content_proposal(sparse, [change("text", refs["a"], "text", "Reviewed")])
        return item, lambda: accept_content(sparse, item)
    changes = OporaGraphChanges(authority.canvas)
    context = changes.specifications.context("draft", "draft")
    item = changes.create({**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
        "subject": "Reviewed patch", "plan": {"updateNodes": [{"id": refs["b"], "fields": {"name": "Changed B"}}]}}, AGENT)
    return item, lambda: OporaGraphChangeAcceptance(authority.canvas).accept(item["id"], {**SCOPE,
        "expectedAcceptedHead": item["parentRevision"], "expectedGraphDigest": item["graphDigest"],
        "adoptBaseGraphDigest": None, "reviewedChangesId": item["id"]}, HUMAN)


@pytest.mark.parametrize("kind", ["spec", "graph-addition", "graph-change", "content"])
def test_each_acceptor_requires_current_ack_and_seals_same_transaction(sparse, kind):
    _, authority, _ = sparse
    configure(sparse)
    item, accept = native(sparse, kind)
    with pytest.raises(ValueError, match="acknowledgement"):
        accept()
    ack = acknowledge(sparse, kind, item)
    result = accept()
    receipt = ProposalReviews(authority.canvas).receipt(*SCOPE.values(), result["id"])["receipt"]
    assert receipt["proposalKind"] == kind and receipt["proposalId"] == item["id"]
    assert receipt["reviewHead"] == ack["id"] == receipt["ackId"] and not receipt["bootstrap"]
    assert accept() == result


def test_receipt_failure_rolls_back_specs_and_head_without_losing_ack(sparse, monkeypatch):
    _, authority, refs = sparse
    configure(sparse)
    item, accept = native(sparse, "spec")
    ack = acknowledge(sparse, "spec", item)
    before = authority.canvas.node_spec("draft", "draft", refs["a"])

    def failed(*_):
        raise ValueError("Injected receipt failure")

    monkeypatch.setattr(AcceptanceReceipts, "insert", failed)
    with pytest.raises(ValueError, match="receipt failure"):
        accept()
    assert authority.canvas.node_spec("draft", "draft", refs["a"]) == before
    assert ChangesetRepository(authority.canvas.db_for("draft"), "draft", "draft").head() == item["parentRevision"]
    assert ProposalReviews(authority.canvas).context(*SCOPE.values(), "spec", item["id"])["reviewHead"] == ack["id"]


def test_absent_disabled_policy_does_not_read_events_or_write_review_ledger(sparse, monkeypatch):
    configure(sparse, enabled=False)
    item, accept = native(sparse, "spec")

    def forbidden(*_):
        raise AssertionError("Disabled review must not consult event quota or write receipts")

    monkeypatch.setattr(ProposalReview, "events", forbidden)
    monkeypatch.setattr(AcceptanceReceipts, "insert", forbidden)
    assert accept()["parentRevision"] == item["parentRevision"]


def test_active_policy_bootstrap_is_one_time_and_records_explicit_exception(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    try:
        current = canvas.view("draft", "draft")
        canvas.save_graph("draft", "draft", {"nodes": [node("a")], "edges": []}, current["digest"])
        from backend.canvas.opora_execution_results import ExecutionResults
        scope = (None, ExecutionResults(canvas), {"a": "a"})
        configure(scope)
        result = baseline(canvas)
        receipt = ProposalReviews(canvas).receipt(*SCOPE.values(), result["id"])["receipt"]
        assert receipt["bootstrap"] and receipt["policyId"] and receipt["proposalId"] is None
        with canvas.db_for("draft") as db:
            db.execute("DELETE FROM opora_spec_refs WHERE project_id='draft' AND workspace_id='draft'")
        with pytest.raises(ValueError, match="Bootstrap"):
            baseline(canvas)
    finally:
        canvas.close()


def test_first_graph_baseline_under_active_policy_acknowledges_null_parent(empty_graphs):
    from backend.canvas.opora_execution_results import ExecutionResults
    canvas = empty_graphs.service
    scope = (empty_graphs, ExecutionResults(canvas), {})
    configure(scope)
    item = graph_proposal(empty_graphs, "First accepted graph")
    current = ProposalReviews(canvas).context(*SCOPE.values(), "graph-addition", item["id"])
    assert current["parentAcceptedHead"] is None and current["acceptedHead"] is None
    assert current["risk"]["level"] == "critical" and current["acknowledgementRequired"]
    ack = acknowledge(scope, "graph-addition", item)
    assert ack["parentAcceptedHead"] is None
    accepted = accept_graph(empty_graphs, item)
    assert accepted["kind"] == "graph-baseline" and accepted["parentRevision"] is None
    receipt = ProposalReviews(canvas).receipt(*SCOPE.values(), accepted["id"])["receipt"]
    assert receipt["proposalKind"] == "graph-addition" and receipt["risk"] == "critical"
    assert receipt["ackId"] == ack["id"] and not receipt["bootstrap"]
