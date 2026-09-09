import time

from fastapi.testclient import TestClient
from test_llm_runs import child_command

from backend.app import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}


def test_real_coding_process_tree_stop_and_single_global_run(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    marker = tmp_path / "child.marker"
    plans = app.state.plan_runs
    actual_spawn = plans._spawn
    monkeypatch.setattr(plans, "_spawn", lambda command: actual_spawn(child_command(marker)))
    with TestClient(app, base_url=ORIGIN) as client:
        settings = client.get("/api/project-settings?project=draft").json()
        client.post("/api/project-settings", headers=HEADERS, json={"project": "draft", "expected_revision": 0, "name": "Test", "settings": {**settings["settings"], "goal": "Stop-control oracle"}}).raise_for_status()
        target = client.post("/api/coding/workspaces", headers=HEADERS, json={"project": "draft", "workspace": "draft", "layer": "", "confirmed": True}).json()
        request = {"targetId": target["id"], "task": "Stop oracle, no provider."}
        preview = client.post("/api/coding/preview", headers=HEADERS, json=request).json()
        payload = {**request, "digest": preview["digest"], "confirmed": True}
        started = client.post("/api/coding/start", headers=HEADERS, json=payload)
        assert started.status_code == 200, started.text
        run = started.json()
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.03)
        assert marker.exists()
        assert client.post("/api/coding/start", headers=HEADERS, json=payload).status_code == 409
        plan = client.get("/api/llm/preview?project=draft&workspace=draft").json()
        assert client.post("/api/llm/start", headers=HEADERS, json={"project": "draft", "workspace": "draft", "layer": "", "digest": plan["digest"], "confirmed": True}).status_code == 409
        stop = {"project": "draft", "runId": run["id"], "confirmed": True}
        assert client.post("/api/coding/stop", headers=HEADERS, json={**stop, "confirmed": False}).status_code == 409
        assert client.post("/api/coding/stop", headers=HEADERS, json={**stop, "project": "other"}).status_code == 409
        with app.state.service.lock:
            process, _job = app.state.coding_runs.handles[run["id"]]
            assert process.poll() is None
        stopped = client.post("/api/coding/stop", headers=HEADERS, json=stop).json()
        assert stopped["status"] == "stopped_local"
        assert stopped["localTreeInactive"] and stopped["pid"] is None
        assert process.poll() is not None
        assert stopped["providerBilling"] == "unverified"
        assert client.post("/api/coding/stop", headers=HEADERS, json=stop).json()["status"] == "stopped_local"
        time.sleep(.1)
        assert client.get("/api/coding/runs").json()["active"] is None


def test_changed_source_invalidates_confirmed_preview(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        target = client.post("/api/coding/workspaces", headers=HEADERS, json={"project": "draft", "workspace": "draft", "layer": "", "confirmed": True}).json()
        request = {"targetId": target["id"], "task": "Fix addition"}
        preview = client.post("/api/coding/preview", headers=HEADERS, json=request).json()
        from pathlib import Path
        Path(target["path"], "calculator.py").write_text("def add(a, b):\n    return a - b\n")
        result = client.post("/api/coding/start", headers=HEADERS, json={**request, "digest": preview["digest"], "confirmed": True})
        assert result.status_code == 409
        assert client.get("/api/coding/runs").json()["runs"] == []
