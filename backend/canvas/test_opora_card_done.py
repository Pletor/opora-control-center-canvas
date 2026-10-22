"""The single definition of done and the plan-steps migration (dry run by default)."""
from backend.canvas.opora_card_done import card_done_state, closable, facts, link_for
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_plan_steps_migration import draft_steps, migrate
from backend.canvas.test_opora_changesets import SCOPE, baseline, legacy_save, service
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

__all__ = ["service"]

COMPLETE = {"steps": {"total": 2, "done": 2}, "acceptanceEvidence": True, "gate": {"status": "ready"},
            "merged": True, "planWrittenBack": True, "closed": True}


def test_done_requires_every_part_in_contract_order():
    assert card_done_state(COMPLETE) == {"done": True, "missing": [], "gate": "review"}
    assert card_done_state({})["missing"] == ["steps", "card_acceptance", "gate_ready", "merged",
                                              "plan_written_back", "human_close"]
    assert card_done_state({**COMPLETE, "steps": {"total": 2, "done": 1}})["missing"] == ["steps"]
    assert card_done_state({**COMPLETE, "steps": {"total": 0, "done": 0}})["missing"] == ["steps"]
    assert card_done_state({**COMPLETE, "gate": {"status": "pending"}})["missing"] == ["gate_ready"]
    assert closable(card_done_state({**COMPLETE, "closed": False}))
    assert not closable(card_done_state({**COMPLETE, "closed": False, "planWrittenBack": False}))


def test_gate_ready_by_mode():
    # Review jobs enabled: only the OporaHub review gate counts, a merge alone is not enough.
    assert card_done_state({**COMPLETE, "gate": None})["missing"] == ["gate_ready"]
    # Review jobs disabled: GitHub branch protection is the gate, so a merged PR satisfies it.
    external = {**COMPLETE, "gate": None, "gateMode": "external"}
    assert card_done_state(external) == {"done": True, "missing": [], "gate": "external"}
    assert card_done_state({**external, "merged": False})["missing"] == ["gate_ready", "merged"]
    link = {"cardId": "a", "state": "merged", "executionId": "1", "planWrittenBack": True}
    card = {"steps": {"total": 1, "done": 1}, "acceptanceEvidence": True}
    assert card_done_state(facts(card, link, None, external=True)) == {
        "done": False, "missing": ["human_close"], "gate": "external"}
    assert card_done_state(facts(card, link, None))["missing"] == ["gate_ready", "human_close"]


def test_gates_by_execution_none_when_review_jobs_disabled(service, monkeypatch):
    from backend.canvas import opora_review_risk as risk
    from backend.canvas.opora_card_done import gates_by_execution
    config = risk.load()
    monkeypatch.setattr(risk, "load", lambda: {**config, "enabled": False})
    assert gates_by_execution(service.db_for("draft"), "draft", "draft") is None
    monkeypatch.setattr(risk, "load", lambda: {**config, "enabled": True})
    assert gates_by_execution(service.db_for("draft"), "draft", "draft") == {}


def test_facts_from_card_link_and_gate():
    link = link_for([{"cardId": "a", "state": "closed", "executionId": "1"},
                     {"cardId": "a", "state": "merged", "executionId": "2", "planWrittenBack": True}], "a")
    assert link["executionId"] == "2"
    value = facts({"steps": {"total": 1, "done": 1}, "acceptanceEvidence": True}, link,
                  {"reviewGate": {"status": "ready"}})
    assert card_done_state(value)["missing"] == ["human_close"]


def test_draft_steps_from_blocks_steps_and_criteria():
    node = {"blocks": [{"number": "2", "title": "Second", "state": {"condition": "B holds"}},
                       {"number": "1", "title": "First", "state": {"condition": "A holds"}},
                       {"number": "3", "title": "No condition", "state": {"condition": ""}}],
            "steps": [{"id": "x", "text": "Write docs", "assignee": "", "done": False}],
            "criteria": [{"id": "c", "text": "Tests pass", "checked": False}]}
    steps = draft_steps(node)
    assert [(item["id"], item["title"], item["dependsOn"]) for item in steps] == [
        ("s1", "First", []), ("s2", "Second", ["s1"]), ("s3", "Write docs", ["s2"])]
    assert steps[-1]["acceptance"] == ["Write docs", "Tests pass"]
    assert draft_steps({"criteria": [{"text": "Only criteria"}]})[0]["acceptance"] == ["Only criteria"]
    assert draft_steps({}) == []


def test_migration_dry_run_writes_nothing_and_apply_only_proposes(service):
    legacy_save(service, goal="Legacy card")
    baseline(service)
    store = DesktopV3State(service)
    current = store.read(**SCOPE)
    current["state"]["nodes"]["a"] = {"phase": "discover", "steps": [],
                                      "criteria": [{"id": "c1", "text": "Works", "checked": False}]}
    store.save({**SCOPE, "expectedRevision": current["revision"], "state": current["state"]}, actor="human")
    head = OporaChangesets(service).context("draft", "draft")["acceptedHead"]
    report = migrate(service, "draft", "draft")
    assert report["dryRun"] and [item["nodeId"] for item in report["cards"]] == ["a"]
    assert not report["proposals"] and OporaChangesets(service).list("draft", "draft")["items"] == []
    applied = migrate(service, "draft", "draft", dry_run=False)
    [proposal] = applied["proposals"]
    assert proposal["accepted"] is False
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] == head
    assert "steps" not in service.node_spec("draft", "draft", "a")["fields"]
