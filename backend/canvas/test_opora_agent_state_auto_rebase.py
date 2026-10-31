"""Agent-state `proposal` stage reflects auto-rebase: conflicts wait for resolution, settled stale ones vanish."""
import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_auto_rebase import AutoRebase
from backend.canvas.test_opora_auto_rebase import propose
from backend.canvas.test_opora_changesets import AGENT, SCOPE, accept, baseline, service

__all__ = ["service"]


@pytest.fixture(autouse=True)
def no_pull_module():
    original = pulls.source
    pulls.source = lambda: None
    yield
    pulls.source = original


def proposal_stage(service):
    document = AgentState(service).read(**SCOPE)
    return document, next(item for item in document["stages"] if item["id"] == "proposal")


def test_conflict_is_waiting_with_resolve_action_and_no_gap(service):
    root = baseline(service)
    ours, theirs = propose(service, "a", goal="Ours"), propose(service, "a", goal="Theirs")
    accept(service, theirs, root["id"])
    document, stage = proposal_stage(service)
    assert stage["reason"] == "stale_proposals"
    assert "auto_rebase" not in {gap["id"] for gap in document["gaps"]}
    AutoRebase(service).run("draft", "draft")
    document, stage = proposal_stage(service)
    assert (stage["health"], stage["reason"], stage["count"]) == ("waiting", "auto_rebase_conflicts", 1)
    action = next(item for item in document["actions"] if item["verb"] == "proposal.resolve_conflict")
    assert action["preconditions"]["proposalId"] == ours["id"] and action["status"] == "ready"


def test_redundant_stale_proposal_is_settled(service):
    root = baseline(service)
    first, twin = propose(service, "a", goal="Same"), propose(service, "a", goal="Same")
    accept(service, first, root["id"])
    AutoRebase(service).run("draft", "draft")
    _, stage = proposal_stage(service)
    assert stage["health"] == "ok" and twin["id"]


def test_switch_off_restores_explicit_rebase_rules(service, monkeypatch):
    monkeypatch.setenv("OPORA_AUTO_REBASE", "0")
    root = baseline(service)
    first, other = propose(service, "a", goal="One"), propose(service, "b", goal="Two")
    accept(service, first, root["id"])
    document, stage = proposal_stage(service)
    assert stage["reason"] == "stale_proposals" and other["id"]
    assert "auto_rebase" in {gap["id"] for gap in document["gaps"]}
    assert not any(item["verb"] == "proposal.resolve_conflict" for item in document["actions"])


def rebase_targets(document):
    return {item["targetId"] for item in document["actions"] if item["verb"] == "rebase"}


def test_settled_stale_proposal_has_no_rebase_action(service):
    root = baseline(service)
    first, twin = propose(service, "a", goal="Same"), propose(service, "a", goal="Same")
    accept(service, first, root["id"])
    document, _ = proposal_stage(service)
    assert twin["id"] in rebase_targets(document)  # unsettled stale: still offered
    AutoRebase(service).run("draft", "draft")
    document, _ = proposal_stage(service)
    assert twin["id"] not in rebase_targets(document)


def test_keep_accepted_conflict_settles_proposal(service):
    root = baseline(service)
    ours, theirs = propose(service, "a", goal="Ours"), propose(service, "a", goal="Theirs")
    accept(service, theirs, root["id"])
    rebase = AutoRebase(service)
    rebase.run("draft", "draft")
    document, _ = proposal_stage(service)
    assert ours["id"] in rebase_targets(document)
    conflict = rebase.conflicts("draft", "draft", "open")["items"][0]
    rebase.resolve(conflict["id"], {**SCOPE, "keep": "accepted"}, AGENT)
    document, stage = proposal_stage(service)
    assert ours["id"] not in rebase_targets(document) and stage["health"] == "ok"


def test_switch_off_keeps_rebase_for_redundant(service, monkeypatch):
    root = baseline(service)
    first, twin = propose(service, "a", goal="Same"), propose(service, "a", goal="Same")
    accept(service, first, root["id"])
    AutoRebase(service).run("draft", "draft")
    monkeypatch.setenv("OPORA_AUTO_REBASE", "0")
    document, _ = proposal_stage(service)
    assert twin["id"] in rebase_targets(document)
