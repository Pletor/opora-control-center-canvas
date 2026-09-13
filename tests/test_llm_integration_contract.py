import os
import sys
import threading
import time

import pytest
from test_llm_runs import Canvas, context, preview, start, wait_for

from backend.agents.runs.llm_runs import PlanRuns


def test_root_layer_is_a_valid_planning_scope(tmp_path):
    canvas = Canvas(tmp_path)
    runtime = PlanRuns(canvas, context, command_builder=lambda p, s: [sys.executable, "-c", "print('root answer')"], tool_probe=lambda: True)
    try:
        packet = runtime.preview("p1", "w1", "")
        result = runtime.start({"project": "p1", "workspace": "w1", "layer": "", "digest": packet["digest"], "confirmed": True})
        assert wait_for(runtime, result["id"], "completed")["output"] == "root answer"
    finally:
        runtime.close()
        canvas.db.close()


def test_completed_run_returns_real_output(tmp_path):
    canvas = Canvas(tmp_path)
    runtime = PlanRuns(canvas, context, command_builder=lambda p, s: [sys.executable, "-c", "print('actual proposal text')"], tool_probe=lambda: True)
    try:
        result = start(runtime, preview(runtime))
        record = wait_for(runtime, result["id"], "completed")
        assert record["output"] == "actual proposal text"
    finally:
        runtime.close()
        canvas.db.close()


def test_valid_configured_model_is_not_rejected_by_stale_model_catalog(tmp_path):
    canvas = Canvas(tmp_path)
    def make_context(p, w, l):
        value = context(p, w, l)
        value["settings"]["model"] = "future-model-123"
        return value
    runtime = PlanRuns(canvas, make_context, command_builder=lambda p, s: [sys.executable, "-c", "print('model accepted')"], tool_probe=lambda: True)
    try:
        result = start(runtime, preview(runtime))
        assert wait_for(runtime, result["id"], "completed")["output"] == "model accepted"
    finally:
        runtime.close()
        canvas.db.close()


def test_close_during_preflight_never_launches_a_later_process(tmp_path):
    canvas = Canvas(tmp_path)
    entered, release = threading.Event(), threading.Event()
    spawned = []
    def probe():
        entered.set()
        release.wait(4)
        return True
    def command(p, s):
        spawned.append(True)
        return [sys.executable, "-c", "print('must not launch')"]
    runtime = PlanRuns(canvas, context, command_builder=command, tool_probe=probe)
    start(runtime, preview(runtime))
    assert entered.wait(2)
    closer = threading.Thread(target=runtime.close)
    closer.start()
    until = time.monotonic() + 2
    while not runtime._closed and time.monotonic() < until:
        time.sleep(0.01)
    release.set()
    closer.join(5)
    assert not closer.is_alive()
    assert spawned == []
    assert runtime.list()["active"] is None
    canvas.db.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows containment regression")
def test_failed_job_assignment_terminates_suspended_process(tmp_path, monkeypatch):
    import backend.agents.runs.llm_runs as module
    created = []
    original = module.subprocess.Popen
    def capture(*args, **kwargs):
        proc = original(*args, **kwargs)
        created.append(proc)
        return proc
    def fail(*args):
        raise OSError("test assignment failure")
    monkeypatch.setattr(module.subprocess, "Popen", capture)
    monkeypatch.setattr(module._WindowsJob, "assign_and_resume", fail)
    canvas = Canvas(tmp_path)
    runtime = PlanRuns(canvas, context, command_builder=lambda p, s: [sys.executable, "-c", "import time; time.sleep(30)"], tool_probe=lambda: True)
    try:
        result = start(runtime, preview(runtime))
        wait_for(runtime, result["id"], "failed")
        assert created and all(proc.poll() is not None for proc in created)
    finally:
        for proc in created:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
        runtime.close()
        canvas.db.close()
