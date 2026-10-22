"""Plan steps are a validated, versioned spec field that merges per step id."""
import pytest

from backend.canvas.opora_auto_rebase import AutoRebase
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_plan_steps import merge_steps, topological, validate_steps
from backend.canvas.test_opora_auto_rebase import propose
from backend.canvas.test_opora_changesets import AGENT, SCOPE, accept, baseline, service
from backend.editor.node.node_specs import validate_payload

__all__ = ["service"]


def step(identifier, order, depends=(), title=None, **extra):
    return {"id": identifier, "order": order, "title": title or f"Step {identifier}",
            "acceptance": [f"{identifier} works"], "dependsOn": list(depends), **extra}


PLAN = [step("s1", 1), step("s2", 2, ["s1"], kind="test", files=["backend/**/*.py"]), step("s3", 3, ["s1"])]


def test_valid_plan_and_topological_order():
    assert validate_steps(PLAN) == PLAN
    assert topological([step("b", 2, ["a"]), step("a", 1)]) == ["a", "b"]
    assert validate_steps([]) == []


@pytest.mark.parametrize(("steps", "message"), [
    ([step("s1", 1), step("s1", 2)], "jedinečná"),
    ([step("s1", 1), step("s2", 1)], "Pořadí kroků"),
    ([step("s1", 1, ["missing"])], "neexistujícím"),
    ([step("s1", 1, ["s1"])], "sám na sobě"),
    ([step("s1", 2, ["s2"]), step("s2", 1, ["s1"])], "cyklus"),
    ([step("s1", 2), step("s2", 1, ["s1"])], "větší"),
    ([{**step("s1", 1), "acceptance": []}], "podmínek"),
    ([{**step("s1", 1), "kind": "deploy"}], "Druh"),
    ([{**step("s1", 1), "extra": 1}], "vyžaduje"),
    ([step("bad id", 1)], "ID kroku"),
])
def test_invalid_plans_are_rejected(steps, message):
    with pytest.raises(ValueError, match=message):
        validate_steps(steps)


def test_spec_payload_accepts_optional_steps_only():
    base = {"project": "p", "workspace": "w", "node": "n", "expected_revision": 0,
            "fields": {"goal": "", "non_goals": "", "acceptance": ""}}
    validate_payload(base)
    validate_payload({**base, "fields": {**base["fields"], "steps": PLAN}})
    with pytest.raises(ValueError, match="cyklus"):
        validate_payload({**base, "fields": {**base["fields"], "steps": [step("a", 1, ["b"]), step("b", 2, ["a"])]}})
    with pytest.raises(ValueError):
        validate_payload({**base, "fields": {**base["fields"], "other": []}})


def test_merge_steps_per_step_id():
    ours = [PLAN[0], {**PLAN[1], "title": "Ours"}, PLAN[2]]
    theirs = [PLAN[0], PLAN[1], {**PLAN[2], "title": "Theirs"}]
    outcomes, merged = merge_steps("k", PLAN, ours, theirs)
    assert outcomes == ["clean"] and [item["title"] for item in merged] == ["Step s1", "Ours", "Theirs"]
    added = [*PLAN, step("s4", 4, ["s2"])]
    outcomes, merged = merge_steps("k", PLAN, added, theirs)
    assert [item["id"] for item in merged] == ["s1", "s2", "s3", "s4"]
    conflict = [PLAN[0], PLAN[1], {**PLAN[2], "title": "Ours"}]
    outcomes, merged = merge_steps("k", PLAN, conflict, theirs)
    assert merged is None and outcomes[0]["key"] == "k:s3"
    # Each side valid, combined plan invalid (s4 depends on s3 that theirs removed) → conflict.
    outcomes, merged = merge_steps("k", PLAN, [*PLAN, step("s4", 4, ["s3"])], PLAN[:2])
    assert merged is None and outcomes[0]["reason"] == "steps_invalid_after_merge"


def test_steps_change_through_changesets_and_rebase(service):
    initial = baseline(service)
    proposal = propose(service, "a", steps=PLAN)
    head = accept(service, proposal, initial["id"])
    assert service.node_spec("draft", "draft", "a")["fields"]["steps"] == PLAN
    accepted = OporaChangesets(service).context("draft", "draft")["acceptedDocuments"]
    assert next(item for item in accepted if item["nodeId"] == "a")["fields"]["steps"] == PLAN
    stale = propose(service, "b", steps=PLAN[:1])
    newer = accept(service, propose(service, "a", goal="Moved on"), head["id"])
    moved = OporaChangesets(service).rebase(stale["id"], {**SCOPE, "expectedAcceptedHead": newer["id"]}, AGENT)
    accept(service, moved, newer["id"])
    assert service.node_spec("draft", "draft", "b")["fields"]["steps"] == PLAN[:1]


def test_auto_rebase_merges_disjoint_steps_and_flags_same_step(service):
    initial = baseline(service)
    head = accept(service, propose(service, "a", steps=PLAN), initial["id"])["id"]
    mine = propose(service, "a", steps=[PLAN[0], {**PLAN[1], "title": "Mine"}, PLAN[2]])
    clash = propose(service, "a", steps=[PLAN[0], PLAN[1], {**PLAN[2], "title": "Clash"}])
    head = accept(service, propose(service, "a", steps=[PLAN[0], PLAN[1], {**PLAN[2], "title": "Theirs"}]), head)["id"]
    summary = AutoRebase(service).run("draft", "draft")
    rebased = {item["proposalId"]: item["resultId"] for item in summary["rebased"]}
    assert mine["id"] in rebased and clash["id"] not in rebased
    result = OporaChangesets(service).read("draft", "draft", rebased[mine["id"]])
    assert [item["title"] for item in result["changes"][0]["fields"]["steps"]] == ["Step s1", "Mine", "Theirs"]
    accept(service, result, head)
    assert service.node_spec("draft", "draft", "a")["fields"]["steps"][1]["title"] == "Mine"
