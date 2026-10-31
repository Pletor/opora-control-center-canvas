"""Etapa `evidence`: výsledky uzavřených karet se nepočítají (docs/oporahub-agent-state.md)."""
from backend.canvas import opora_agent_state_rules as rules

HEAD = "a" * 40


def result(node, stale):
    return {"id": "e-" + node, "nodeId": node, "results": 1, "acceptedRevision": HEAD, "staleEvidence": stale}


def evidence(reported, cards):
    entry = rules.evidence_stage(rules.open_results(reported, cards), HEAD)
    return entry["count"], entry["health"], entry["reason"]


def test_closed_card_with_stale_result_does_not_stale_stage():
    cards = {"n": {"doneConfirmed": True}}
    assert evidence([result("n", True)], cards) == (0, "ok", "no_evidence")


def test_open_card_with_stale_result_still_waits():
    cards = {"n": {"doneConfirmed": False}, "m": {"doneConfirmed": True}}
    assert evidence([result("n", True), result("m", True)], cards) == (1, "waiting", "stale_evidence")
