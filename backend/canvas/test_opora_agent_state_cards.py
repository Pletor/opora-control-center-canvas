"""Per-card loop stage (docs/oporahub-agent-state.md, "Etapa karty"): first matching rule wins."""
from backend.canvas.opora_agent_state_cards import card_stage, page, project, pull_request

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
    # Mrtvý běh bez výsledku, karta znovu nabízí claim: etapa claim, ne lease_past_deadline.
    assert stage(latest=run(deadline=50.0), claim={"status": "ready"}) == ("claim", "ok", "cards_ready")
    assert stage(latest=run(deadline=50.0), claim={"status": "blocked", "blockReason": "budget_exhausted"}) == (
        "claim", "blocking", "budget_exhausted")
    assert stage(latest=run("reported", 1)) == ("review", "waiting", "human_review_required")
    assert stage(latest=run("reported", 1, revision="b" * 40)) == ("evidence", "waiting", "stale_evidence")
    # Agent-state spočte výřez karty (`staleEvidence`); posun hlavy jinde výsledek nezastará.
    assert stage(latest={**run("reported", 1, revision="b" * 40), "staleEvidence": False}) == (
        "review", "waiting", "human_review_required")
    assert stage(latest={**run("reported", 1), "staleEvidence": True}) == ("evidence", "waiting", "stale_evidence")


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
    assert rows[0] == {"nodeId": "a", "stage": "review", "health": "waiting", "reason": "self_checks_missing", "executionId": "e1",
                       "pr": {"number": None, "state": "open"}}
    assert list(rows[1]) == ["nodeId", "stage", "health", "reason", "executionId"]


def test_a_merged_link_beats_a_later_attempt_closed_without_merge():
    """IDLE-002: the card's work merged (#70), a duplicate PR (#77) was opened later and closed; the card is merged."""
    merged = {"executionId": "old", "state": "merged", "cardId": "a", "number": 70, "awaitingHumanClose": True}
    closed = {"executionId": "e1", "state": "closed", "cardId": "a", "number": 77}
    for linked in ([merged, closed], [closed, merged]):
        row = project({"a": {"nodeId": "a"}}, HEAD, [run("reported", 1)], [], linked, None, 100.0)[0]
        assert (row["stage"], row["reason"], row["pr"]) == ("merge", "awaiting_human_close", {"number": 70, "state": "merged"})
    newer = {**merged, "executionId": "e2", "number": 71}
    assert project({"a": {"nodeId": "a"}}, HEAD, [], [], [merged, newer], None, 100.0)[0]["pr"]["number"] == 71


def test_pull_request_badge_facts():
    """`pr` on the card: number and state of the linked PR; none on a closed card or for a stale closed PR."""
    merged = {"executionId": "e1", "state": "merged", "cardId": "n", "number": 42}
    assert pull_request({"nodeId": "n"}, merged, None) == {"number": 42, "state": "merged"}
    assert pull_request({"nodeId": "n", "doneConfirmed": True}, merged, None) is None
    assert pull_request({"nodeId": "n"}, None, run()) is None
    closed = {**merged, "state": "closed"}
    assert pull_request({"nodeId": "n"}, closed, run("reported", 1)) == {"number": 42, "state": "closed"}
    assert pull_request({"nodeId": "n"}, closed, run(ident="e2")) is None
    assert pull_request({"nodeId": "n"}, {**merged, "number": None}, None) == {"number": None, "state": "merged"}
    rows = project({"n": {"nodeId": "n"}}, HEAD, [], [], [{**merged, "awaitingHumanClose": True}], None, 100.0)
    assert rows[0]["reason"] == "awaiting_human_close" and rows[0]["pr"] == {"number": 42, "state": "merged"}


def test_page_orders_by_relevance_and_caps_closed_cards_first():
    def entry(node, stage_, reason):
        return {"nodeId": node, "stage": stage_, "reason": reason}
    rows = [entry("a", "plan_writeback", "card_closed"), entry("b", "plan", "card_in_plan"),
            entry("c", "claim", "blocked_by_predecessor"), entry("d", "claim", "cards_ready"),
            entry("e", "work", "runs_active"), entry("f", "plan_writeback", "plan_written_back"),
            entry("g", "plan_writeback", "merged_without_plan_writeback")]
    shown, total, following = page(rows, 0, 5)
    assert [row["nodeId"] for row in shown] == ["e", "g", "d", "c", "b"] and total == 7 and following == 5
    rest, _, done = page(rows, following, 5)
    assert [row["nodeId"] for row in rest] == ["a", "f"] and done is None


def test_historical_result_with_a_claim_shows_the_claim_stage():
    stale = {**run("reported", 1, revision="b" * 40), "staleEvidence": True}
    assert stage(latest=stale, claim={"status": "ready"}) == ("claim", "ok", "cards_ready")
    assert stage(latest=stale, claim={"status": "blocked", "blockReason": "blocked_by_predecessor"}) == (
        "claim", "blocking", "blocked_by_predecessor")
    # Výsledek jen po posunu hlavy jinde zůstává k review; otevřené PR má dál přednost.
    assert stage(latest={**stale, "staleEvidence": False}, claim={"status": "ready"}) == (
        "review", "waiting", "human_review_required")
    link = {"executionId": "e1", "state": "open", "cardId": "n"}
    assert stage(latest=stale, claim={"status": "ready"}, link=link) == ("pull_request", "waiting", "pull_requests_open")
