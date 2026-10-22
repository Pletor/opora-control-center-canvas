"""Per-card loop stage (docs/oporahub-agent-state.md, "Etapa karty"): first matching rule wins."""
from backend.canvas.opora_agent_state_cards import card_stage, project

HEAD = "a" * 40


def run(state="running", results=0, revision=HEAD, deadline=200.0, ident="e1"):
    return {"id": ident, "nodeId": "n", "state": state, "acceptedRevision": revision, "deadline": deadline, "results": results}


def gate(status, reasons):
    return {"executionId": "e1", "reviewGate": {"status": status, "reasons": reasons}}


def stage(card=None, latest=None, claim=None, link=None, gate_=None, accepted=HEAD, now=100.0):
    entry = card_stage(card or {"nodeId": "n"}, accepted, latest, claim, link, gate_, now)
    return entry["stage"], entry["health"], entry["reason"]


def test_plan_and_claim():
    assert stage() == ("plan", "ok", "card_in_plan")
    assert stage(accepted=None) == ("plan", "blocking", "no_accepted_baseline")
    assert stage(claim={"status": "ready"}) == ("claim", "ok", "cards_ready")
    assert stage(claim={"status": "blocked", "blockReason": "budget_exhausted"}) == ("claim", "blocking", "budget_exhausted")


def test_work_and_evidence():
    assert stage(latest=run()) == ("work", "ok", "runs_active")
    assert stage(latest=run(deadline=50.0)) == ("work", "blocking", "lease_past_deadline")
    assert stage(latest=run("reported", 1)) == ("review", "waiting", "human_review_required")
    assert stage(latest=run("reported", 1, revision="b" * 40)) == ("evidence", "waiting", "stale_evidence")


def test_open_pull_request_uses_the_merge_gate_rule():
    link = {"executionId": "e1", "state": "open", "cardId": "n"}
    assert stage(latest=run("reported", 1), link=link) == ("pull_request", "waiting", "pull_requests_open")
    held = gate("pending", ["template_incomplete", "stale_against_main"])
    assert stage(link=link, gate_=held) == ("review", "waiting", "stale_against_main")
    assert stage(link=link, gate_=gate("blocked", ["open_security_findings"])) == ("review", "blocking", "open_security_findings")
    assert stage(link=link, gate_=gate("ready", [])) == ("review", "ok", "review_gate_ready")


def test_merge_and_writeback():
    merged = {"executionId": "e1", "state": "merged", "cardId": "n"}
    assert stage(link={**merged, "awaitingHumanClose": True}) == ("merge", "waiting", "awaiting_human_close")
    assert stage(link={**merged, "planWrittenBack": True}) == ("plan_writeback", "ok", "plan_written_back")
    assert stage(link=merged) == ("plan_writeback", "waiting", "merged_without_plan_writeback")
    assert stage(card={"nodeId": "n", "doneConfirmed": True}, link=merged) == ("plan_writeback", "ok", "card_closed")


def test_project_is_sorted_and_prefers_the_open_link():
    cards = {"b": {"nodeId": "b"}, "a": {"nodeId": "a"}}
    linked = [{"executionId": "old", "state": "merged", "cardId": "a"}, {"executionId": "e1", "state": "open", "cardId": "a"}]
    rows = project(cards, HEAD, [], [], linked, {"gates": [gate("pending", ["self_checks_missing"])]}, 100.0)
    assert [row["nodeId"] for row in rows] == ["a", "b"]
    assert rows[0] == {"nodeId": "a", "stage": "review", "health": "waiting", "reason": "self_checks_missing", "executionId": "e1"}
    assert list(rows[1]) == ["nodeId", "stage", "health", "reason", "executionId"]
