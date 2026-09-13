import json
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

from backend.agents.runs.llm_runs import PlanRuns


class Canvas:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "canvas.sqlite", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.graph_lock = threading.RLock()


def context(project, workspace, layer):
    return {
        "project": {"id": project, "name": "Project"}, "workspace": workspace, "layer": layer,
        "configRevision": 3,
        "settings": {"goal": "Make a safe plan", "provider": "openai-codex", "model": "gpt-6-astra", "budgetSeconds": 10},
        "drawing": {"label": "only saved context"},
    }


def child_command(marker, noisy=False):
    child = f"from pathlib import Path; import time; Path({str(marker)!r}).write_text('child'); time.sleep(60)"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(60)"
    if noisy:
        parent = "print('x'*70000); " + parent
    return [sys.executable, "-c", parent]


def make_runtime(tmp_path, command=None, builder=context):
    canvas = Canvas(tmp_path)
    runtime = PlanRuns(canvas, builder, command_builder=command, tool_probe=lambda: True)
    return canvas, runtime


def preview(runtime):
    return runtime.preview("p1", "w1", "layer1")


def start(runtime, item):
    return runtime.start({"project": "p1", "workspace": "w1", "layer": "layer1", "digest": item["digest"], "confirmed": True})


def wait_for(runtime, run_id, expected, seconds=5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        found = next(x for x in runtime.list()["runs"] if x["id"] == run_id)
        if found["status"] == expected:
            return found
        time.sleep(.03)
    raise AssertionError("run did not reach " + expected)


def test_preview_capabilities_and_strict_start_payload(tmp_path):
    canvas, runtime = make_runtime(tmp_path, lambda prompt, settings: [sys.executable, "-c", "print('ok')"])
    assert runtime.capabilities() == {"available": True, "mode": "proposal_only", "provider_billing": "unverified"}
    item = preview(runtime)
    assert item["context"]["project"]["id"] == "p1"
    with pytest.raises(ValueError):
        runtime.start({"project": "p1"})
    with pytest.raises(ValueError):
        runtime.start({"project": "p1", "workspace": "w1", "layer": "layer1", "digest": item["digest"], "confirmed": True, "command": "evil"})
    with pytest.raises(ValueError):
        runtime.start({"project": "p1", "workspace": "w1", "layer": "layer1", "digest": "stale", "confirmed": True})
    runtime.close(); canvas.db.close()


def test_only_one_active_run_and_frozen_context(tmp_path):
    marker = tmp_path / "marker"
    canvas, runtime = make_runtime(tmp_path, lambda prompt, settings: child_command(marker))
    first = start(runtime, preview(runtime))
    assert first["status"] in ("starting", "running")
    with pytest.raises(ValueError):
        start(runtime, preview(runtime))
    stored = json.loads(canvas.db.execute("SELECT context FROM llm_runs WHERE id=?", (first["id"],)).fetchone()[0])
    assert stored["settings"]["goal"] == "Make a safe plan"
    runtime.stop({"project": "p1", "runId": first["id"], "confirmed": True})
    wait_for(runtime, first["id"], "stopped_local")
    runtime.close(); canvas.db.close()


def test_stop_kills_real_parent_and_sleeping_child_tree(tmp_path):
    marker = tmp_path / "tree-marker"
    canvas, runtime = make_runtime(tmp_path, lambda prompt, settings: child_command(marker))
    run = start(runtime, preview(runtime))
    end = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < end:
        time.sleep(.03)
    assert marker.exists(), "fixture child never started: " + repr(runtime.list())
    stopped = runtime.stop({"project": "p1", "runId": run["id"], "confirmed": True})
    assert stopped["status"] in ("stopping", "stopped_local")
    stopped = wait_for(runtime, run["id"], "stopped_local")
    assert stopped["provider_billing"] == "unverified"
    assert runtime.stop({"project": "p1", "runId": run["id"], "confirmed": True})["status"] == "stopped_local"
    runtime.close(); canvas.db.close()


def test_output_cap_stops_run(tmp_path):
    canvas, runtime = make_runtime(tmp_path, lambda prompt, settings: [sys.executable, "-c", "print('x'*70000); import time; time.sleep(10)"])
    run = start(runtime, preview(runtime))
    assert wait_for(runtime, run["id"], "failed")["message"] == "Procesní výstup překročil bezpečný limit."
    runtime.close(); canvas.db.close()


def test_context_size_and_empty_goal_fail_closed(tmp_path):
    huge = lambda p, w, l: {**context(p, w, l), "extra": "x" * 50000}
    canvas, runtime = make_runtime(tmp_path, builder=huge)
    with pytest.raises(ValueError): runtime.preview("p1", "w1", "layer1")
    runtime.close(); canvas.db.close()
    empty = lambda p, w, l: {**context(p, w, l), "settings": {**context(p,w,l)["settings"], "goal": ""}}
    canvas, runtime = make_runtime(tmp_path / "empty", builder=empty)
    item = runtime.preview("p1", "w1", "layer1")
    with pytest.raises(ValueError): start(runtime, item)
    runtime.close(); canvas.db.close()
