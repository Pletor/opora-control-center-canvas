import itertools

import pytest

from backend.editor.process.process_lifecycle import TRANSITIONS, allowed_targets, mark_step, set_fix, transition
from backend.editor.process.process_store import STATES, ProcessStore

HUMAN = {"kind": "human", "name": "Pletor"}
AGENT = {"kind": "agent", "name": "claude-code"}
SYSTEM = {"kind": "system", "name": "process_lifecycle"}


def draft(tmp_path, worktree="wt-a"):
    store = ProcessStore(tmp_path / "p")
    return store.create("T", HUMAN, by=HUMAN, steps=["a", "b"], inputs={"worktree": worktree})


def evidence(by=AGENT):
    return {"summary": "ok", "at": "2026-09-14T10:00:00Z", "by": by, "reportId": None, "outputs": []}


def running(tmp_path):
    return transition(draft(tmp_path), "running", by=HUMAN)


def failing(tmp_path):
    process = running(tmp_path)
    return transition(process, "repair", by=SYSTEM, failure={"reason": "test selhal", "stepId": process["steps"][1]["id"], "reportedBy": AGENT})


def test_happy_path_draft_running_done(tmp_path):
    process = running(tmp_path)
    assert process["state"] == "running" and process["history"][-1]["from"] == "draft"
    for step in process["steps"]:
        process = mark_step(process, step["id"], "done", evidence())
    done = transition(process, "done", by=AGENT, note="vše má důkaz")
    assert done["state"] == "done" and [h["to"] for h in done["history"]] == ["draft", "running", "done"]


def test_running_requires_worktree_or_explicit_note(tmp_path):
    process = draft(tmp_path, worktree=None)
    with pytest.raises(ValueError, match="worktree"):
        transition(process, "running", by=HUMAN)
    assert transition(process, "running", by=HUMAN, note="Bez worktree, jen dokumentace")["state"] == "running"


def test_done_requires_every_step_done_with_evidence(tmp_path):
    process = running(tmp_path)
    with pytest.raises(ValueError, match="není hotový"):
        transition(process, "done", by=HUMAN)


def test_failure_moves_to_repair_and_fix_returns_to_running(tmp_path):
    broken = failing(tmp_path)
    assert broken["state"] == "repair"
    failed = [s for s in broken["steps"] if s["state"] == "failed"]
    assert len(failed) == 1 and failed[0]["evidence"]["summary"] == "test selhal"
    assert broken["failure"]["fix"] is None
    with pytest.raises(ValueError, match="popis opravy"):
        transition(broken, "running", by=AGENT)
    fixed = set_fix(broken, "sekundární klíč řazení")
    back = transition(fixed, "running", by=AGENT)
    assert back["state"] == "running" and all(s["state"] == "pending" for s in back["steps"])
    assert len(back["history"]) == 4


def test_repair_requires_failure_payload(tmp_path):
    with pytest.raises(ValueError, match="failure"):
        transition(running(tmp_path), "repair", by=SYSTEM)


def test_done_can_go_to_repair_only_by_human(tmp_path):
    process = running(tmp_path)
    for step in process["steps"]:
        process = mark_step(process, step["id"], "done", evidence())
    done = transition(process, "done", by=HUMAN)
    failure = {"reason": "v provozu spadlo", "stepId": None, "reportedBy": HUMAN}
    with pytest.raises(ValueError, match="smí vyvolat"):
        transition(done, "repair", by=AGENT, failure=failure)
    assert transition(done, "repair", by=HUMAN, failure=failure)["state"] == "repair"


ALLOWED = set(TRANSITIONS)
FORBIDDEN = [(a, b) for a, b in itertools.product(STATES, STATES) if (a, b) not in ALLOWED]


@pytest.mark.parametrize("frm,to", FORBIDDEN)
def test_forbidden_transitions(tmp_path, frm, to):
    builders = {"draft": draft, "running": running, "repair": failing}

    def done_process(path):
        process = running(path)
        for step in process["steps"]:
            process = mark_step(process, step["id"], "done", evidence())
        return transition(process, "done", by=HUMAN)

    builders["done"] = done_process
    process = builders[frm](tmp_path)
    with pytest.raises(ValueError, match="není povolen"):
        transition(process, to, by=HUMAN, failure={"reason": "x", "stepId": None, "reportedBy": HUMAN})


def test_forbidden_count_matches_table():
    assert len(FORBIDDEN) == 16 - len(ALLOWED)


def test_allowed_targets_by_actor(tmp_path):
    process = running(tmp_path)
    assert allowed_targets(process, "system") == ["repair"]
    assert set(allowed_targets(process, "human")) == {"done", "repair"}


def test_transition_does_not_mutate_input(tmp_path):
    process = draft(tmp_path)
    before = len(process["history"])
    transition(process, "running", by=HUMAN)
    assert len(process["history"]) == before and process["state"] == "draft"


def test_mark_step_rules(tmp_path):
    process = running(tmp_path)
    step = process["steps"][0]["id"]
    with pytest.raises(ValueError, match="důkaz"):
        mark_step(process, step, "done")
    with pytest.raises(ValueError, match="neexistuje"):
        mark_step(process, "stp-00000000", "running")
    assert mark_step(process, step, "running")["steps"][0]["state"] == "running"
