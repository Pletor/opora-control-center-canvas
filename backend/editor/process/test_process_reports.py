import json

import pytest

from backend.editor.process.process_lifecycle import mark_step, transition
from backend.editor.process.process_reports import ProcessReports
from backend.editor.process.process_store import ProcessStore

HUMAN = {"kind": "human", "name": "Pletor"}
AGENT = {"kind": "agent", "name": "Claude Code"}


def running(tmp_path):
    store = ProcessStore(tmp_path / "p")
    process = store.create("T", HUMAN, by=HUMAN, steps=["a", "b"], inputs={"worktree": "wt-a"})
    process = store.save(transition(process, "running", by=HUMAN), expected_revision=1)
    return store, ProcessReports(store), process


def report(process, kind, **extra):
    return {"kind": kind, "by": AGENT, "summary": "hotovo", "processRevision": process["revision"], **extra}


def test_step_done_adds_evidence_and_keeps_process_running(tmp_path):
    store, reports, process = running(tmp_path)
    step = process["steps"][0]["id"]
    result = reports.submit(process["id"], report(process, "step_done", stepId=step, outputs=[{"kind": "file", "ref": "worktrees/wt-a/x.py"}]))
    updated = result["process"]
    assert updated["state"] == "running" and updated["revision"] == 3
    assert updated["steps"][0]["state"] == "done" and updated["steps"][0]["evidence"]["reportId"] == result["report"]["id"]
    assert updated["outputs"][0]["ref"] == "worktrees/wt-a/x.py"
    files = list(reports.directory(process["id"]).glob("*.json"))
    assert len(files) == 1 and "-claude-code-" in files[0].name
    assert json.loads(files[0].read_text(encoding="utf-8"))["context"]["worktree"] == "wt-a"


def test_step_failed_moves_running_process_to_repair_with_history(tmp_path):
    store, reports, process = running(tmp_path)
    step = process["steps"][1]["id"]
    result = reports.submit(process["id"], report(process, "step_failed", stepId=step, error="pytest: 2 failed"))
    updated = result["process"]
    assert updated["state"] == "repair" and updated["failure"]["reason"] == "pytest: 2 failed"
    assert updated["failure"]["stepId"] == step and updated["steps"][1]["state"] == "failed"
    assert [h["to"] for h in updated["history"]] == ["draft", "running", "repair"]
    assert updated["history"][-1]["by"]["kind"] == "system"


def test_reports_never_interrupt_and_stale_is_marked(tmp_path):
    store, reports, process = running(tmp_path)
    first = reports.submit(process["id"], report(process, "progress"))
    assert first["process"]["revision"] == process["revision"] and first["report"]["stale"] is False
    second = reports.submit(process["id"], report(process, "question", processRevision=1))
    assert second["report"]["stale"] is True
    assert len(reports.list(process["id"])) == 2
    assert reports.list(process["id"])[0]["kind"] == "progress"


def test_result_appends_outputs(tmp_path):
    store, reports, process = running(tmp_path)
    result = reports.submit(process["id"], report(process, "result", outputs=[{"kind": "md", "ref": "processes/x/result.md"}, {"kind": "db", "ref": "process_outputs:x:1"}]))
    assert [o["kind"] for o in result["process"]["outputs"]] == ["md", "db"]


def test_validation(tmp_path):
    store, reports, process = running(tmp_path)
    cases = [
        report(process, "weird"),
        {**report(process, "progress"), "by": {"kind": "robot", "name": "x"}},
        {**report(process, "progress"), "summary": ""},
        {**report(process, "progress"), "processRevision": "1"},
        report(process, "step_done", stepId="stp-00000000"),
        report(process, "step_failed", stepId=process["steps"][0]["id"]),
        {**report(process, "result"), "outputs": [{"kind": "pdf", "ref": "x"}]},
    ]
    for payload in cases:
        with pytest.raises(ValueError):
            reports.submit(process["id"], payload)
    assert reports.list(process["id"]) == []
    with pytest.raises(ValueError):
        reports.submit("prc-000000000000", report(process, "progress"))


def process_in_state(tmp_path, state):
    store, reports, process = running(tmp_path)
    if state == "done":
        for step in process["steps"]:
            updated = mark_step(process, step["id"], "done", {"summary": "připraveno", "at": process["updatedAt"], "by": HUMAN})
            process = store.save(updated, expected_revision=process["revision"])
        process = store.save(transition(process, "done", by=HUMAN), expected_revision=process["revision"])
    return store, reports, process


@pytest.mark.parametrize("state", ("running", "done"))
@pytest.mark.parametrize("kind", ("step_done", "step_failed", "result"))
@pytest.mark.parametrize("revision_offset", (-1, 1), ids=("older", "newer"))
def test_stale_mutating_report_is_stored_without_changing_process(tmp_path, monkeypatch, state, kind, revision_offset):
    store, reports, process = process_in_state(tmp_path, state)
    process_file = store.directory(process["id"]) / "process.json"
    before_bytes = process_file.read_bytes()
    before_process = store.get(process["id"])
    save_calls = []
    original_save = store.save

    def save(*args, **kwargs):
        save_calls.append((args, kwargs))
        return original_save(*args, **kwargs)

    monkeypatch.setattr(store, "save", save)
    outputs = [{"kind": "md", "ref": "processes/x/late.md"}]
    extra: dict = {"outputs": outputs}
    if kind != "result":
        extra["stepId"] = process["steps"][0]["id"]
    if kind == "step_failed":
        extra["error"] = "pozdní selhání"
    result = reports.submit(
        process["id"],
        report(process, kind, summary="pozdní odpověď", processRevision=process["revision"] + revision_offset, **extra),
    )

    stored = reports.list(process["id"])[-1]
    assert result["report"]["stale"] is True
    assert stored["summary"] == "pozdní odpověď" and stored["outputs"] == result["report"]["outputs"]
    assert stored["error"] == ("pozdní selhání" if kind == "step_failed" else None)
    assert save_calls == []
    assert result["process"] == before_process
    assert process_file.read_bytes() == before_bytes
    assert store.get(process["id"])["revision"] == before_process["revision"]


@pytest.mark.parametrize("kind", ("progress", "question"))
def test_stale_nonmutating_report_is_still_stored(tmp_path, monkeypatch, kind):
    store, reports, process = running(tmp_path)
    process_file = store.directory(process["id"]) / "process.json"
    before_bytes = process_file.read_bytes()
    save_calls = []
    original_save = store.save

    def save(*args, **kwargs):
        save_calls.append((args, kwargs))
        return original_save(*args, **kwargs)

    monkeypatch.setattr(store, "save", save)
    result = reports.submit(
        process["id"],
        report(process, kind, summary="pozdní zpráva", processRevision=process["revision"] + 1),
    )

    assert result["report"]["stale"] is True
    assert reports.list(process["id"])[-1]["kind"] == kind
    assert save_calls == []
    assert process_file.read_bytes() == before_bytes
