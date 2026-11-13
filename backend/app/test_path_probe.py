"""Průchodový test cesty (§11): zelený průchod dvakrát po sobě, hranice člověka, selhání kroku a uzavření záznamu."""
from fastapi.testclient import TestClient

from backend.app import errors, path_probe
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import ORIGIN


def statuses(result):
    return {step["id"]: step["status"] for step in result["steps"]}


def opened(source="path"):
    return errors.read(source=source)


def test_human_founds_the_sandbox_and_the_path_stays_green(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        first = path_probe.run(client.app, dict(client.cookies))
        assert first["ok"] is True, path_probe.text(first)
        assert set(statuses(first).values()) == {"ok"} and all(s["ms"] is not None for s in first["steps"])
        settings = client.get("/api/project-settings", params={"project": first["project"]}).json()
        assert settings["agentAutonomy"]["full"] is True and settings["agentAutonomy"]["by"] == "human"
        maps = client.get("/api/map-refresh/status", params={"project": first["project"]}).json()
        assert maps["automatic"]["graphify"] is False and maps["status"] != "queued", maps
        # Druhý den: agent bez dokladu člověka, stejné pískoviště, nová karta, přijetí přes akce agent-state.
        second = path_probe.run(client.app)
        assert second["ok"] is True and second["by"] == "agent", path_probe.text(second)
        assert second["project"] == first["project"]
        assert path_probe.last(client.app.state.service.root) == second
        assert path_probe.headline(second).startswith("PRŮCHOD CESTY: zelený")


def test_agent_on_fresh_root_needs_a_human_and_creates_nothing(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        result = path_probe.run(client.app)
        assert statuses(result) == {"projekt": "human", **{key: "unchecked" for key, _ in path_probe.STEPS[1:]}}
        assert result["project"] is None and not (path_probe.folder(client.app.state.service.root) / "repo").exists()
        [row] = opened()
        assert row["kind"] == "blocked" and row["subject"] == "projekt" and "POST /api/pletor/path-probe" in row["lever"]
        assert "stojí na kroku projekt" in path_probe.headline(result)


def test_failed_step_is_logged_rest_unchecked_and_green_run_resolves_it(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        assert path_probe.run(client.app, dict(client.cookies))["ok"] is True

        def boom():
            raise RuntimeError("podvržený krok")

        failed = path_probe.run(client.app, steps={"start": boom})
        assert failed["ok"] is False
        assert [statuses(failed)[key] for key, _ in path_probe.STEPS] == ["ok", "ok", "ok", "fail", "unchecked",
                                                                           "unchecked", "unchecked"]
        [row] = opened()
        assert row["kind"] == "exception" and row["subject"] == "start" and "podvržený krok" in row["cause"]
        assert row["project"] == failed["project"]
        # Zelený průchod podmínku zavře.
        assert path_probe.run(client.app)["ok"] is True
        assert opened() == [] and errors.read(source="path", open_only=False)[0]["resolved_at"]


def test_due_only_with_sandbox_and_after_a_day(tmp_path):
    root = tmp_path
    assert path_probe.due(root) is False
    path_probe._save(root, {"project": "p", "last": {"at": "2026-11-13T00:00:00+00:00"}})
    stamp = path_probe.datetime.fromisoformat("2026-11-13T00:00:00+00:00").timestamp()
    assert path_probe.due(root, stamp + 3600) is False and path_probe.due(root, stamp + path_probe.DAY) is True


def test_daily_tick_lives_with_the_app(tmp_path):
    import threading

    def alive():
        return any(thread.name == "opora-pruchod-tik" and thread.is_alive() for thread in threading.enumerate())

    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN):
        assert alive()
    for thread in threading.enumerate():
        if thread.name == "opora-pruchod-tik":
            thread.join(timeout=2)
    assert not alive()
