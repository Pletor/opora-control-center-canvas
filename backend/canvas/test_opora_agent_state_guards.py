"""Guard findings in agent-state (docs/strazci.md §5): `guards` and `cards[].guardFindings` without map holes."""
import time

from backend.canvas import opora_agent_state_guards as guards_state
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.strazci import findings
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414

NOW = time.time()


def item(key, severity="warn", **extra):
    return {"key": key, "rule": "test.rule", "severity": severity, "message": f"Nález {key}", **extra}


def test_guards_leave_map_holes_out_and_mark_cards(service):
    findings.apply(service, "draft", "mapa", [item("map:1", "block", nodeId="a")], NOW)
    findings.apply(service, "draft", "prace", [item("w:1", nodeId="a"), item("w:2", "info", nodeId="b"),
                                               item("w:other", nodeId="a", workspaceId="w9")], NOW)
    findings.apply(service, "draft", "cesty", [item("j:1", "block", nodeId="a", journeyId="kampan")], NOW)
    document = AgentState(service, clock=time.time).read(**SCOPE)
    guards = document["guards"]
    assert guards["open"] == {"block": 1, "warn": 1, "info": 1}
    assert [entry["key"] for entry in guards["findings"]] == ["j:1", "w:1", "w:2"]
    assert guards["findings"][0] == {"key": "j:1", "guard": "cesty", "rule": "test.rule", "severity": "block",
                                     "message": "Nález j:1", "nodeId": "a", "journeyId": "kampan",
                                     "workspaceId": "draft", "firstSeen": findings.at_of(NOW),
                                     "lastSeen": findings.at_of(NOW)}
    cards = {card["nodeId"]: card for card in document["cards"]}
    assert cards["a"]["guardFindings"] == {"count": 2, "severity": "block"}
    assert cards["b"]["guardFindings"] == {"count": 1, "severity": "info"}


def test_without_findings_guards_are_empty_and_cards_unchanged(service):
    document = AgentState(service, clock=time.time).read(**SCOPE)
    assert document["guards"] == {"open": {"block": 0, "warn": 0, "info": 0}, "findings": []}
    assert all("guardFindings" not in card for card in document["cards"])


def test_findings_are_capped_at_twenty_block_first():
    rows = [{"key": f"k{i}", "guard": "prace", "rule": "r", "severity": "block" if i == 25 else "warn",
             "message": "m", "nodeId": None} for i in range(30)]
    rows.sort(key=lambda row: row["severity"] != "block")
    summary = guards_state.summary(rows)
    assert len(summary["findings"]) == guards_state.LIMIT == 20 and summary["findings"][0]["key"] == "k25"
    assert summary["open"] == {"block": 1, "warn": 29, "info": 0}


def test_node_findings_are_at_most_three_rule_and_message(service):
    findings.apply(service, "draft", "mapa", [item("map:1", nodeId="a")], NOW)
    findings.apply(service, "draft", "prace", [item(f"w:{i}", nodeId="a") for i in range(5)], NOW)
    db = service.db_for("draft")
    found = guards_state.node_findings(db, "draft", "draft", "a")
    assert len(found) == 3 and all(set(entry) == {"rule", "message"} for entry in found)
    assert all(entry["rule"] == "test.rule" for entry in found)


def test_failed_and_stale_journeys_stay_with_map_gaps(service):
    findings.apply(service, "draft", "cesty", [
        {**item("j:failed", nodeId="a"), "rule": "journey.failed"},
        {**item("j:stale", nodeId="a"), "rule": "journey.stale"},
        {**item("j:blocks", "block", nodeId="a"), "rule": "journey.blocks-card"}], NOW)
    guards = AgentState(service, clock=time.time).read(**SCOPE)["guards"]
    assert [entry["key"] for entry in guards["findings"]] == ["j:blocks"]
