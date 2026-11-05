import json
from types import SimpleNamespace

from backend.agi_pletor.monitoring.monitor import Monitor

HOST = {"domainId": "web", "environment": "prod", "host": "a.cz", "healthPath": None}
OK = {"ok": True, "status": 200, "latency_ms": 100, "error": None}
FAIL = {"ok": False, "status": None, "latency_ms": None, "error": "HTTP 502"}
SLOW = {"ok": True, "status": 200, "latency_ms": 2500, "error": None}


def make(tmp_path, results, hosts=(HOST,), settings=None):
    project = tmp_path / "p"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({"settings": settings or {"monitor": {"enabled": True}}}), encoding="utf-8")
    folder = SimpleNamespace(path=project, read=lambda: json.loads((project / "project.json").read_text(encoding="utf-8")))
    service = SimpleNamespace(folder=lambda pid: folder, project_ids=lambda: ["draft", "p"])
    feed, logged = iter(results), []
    monitor = Monitor(service, probe=lambda host, path: next(feed), hosts=lambda s, p: list(hosts),
                      log=lambda svc, project, canvas, kind, payload, author: logged.append((project, canvas, kind, payload["state"], author)))
    return monitor, logged


def run(monitor, times):
    return [monitor.run("p") for _ in range(times)]


def test_outage_written_once_then_recovery(tmp_path):
    monitor, logged = make(tmp_path, [FAIL] * 5 + [OK, OK])
    run(monitor, 7)
    assert logged == [("p", 4, "outage.failed", "down", "monitor"), ("p", 4, "outage.recovered", "ok", "monitor")]
    state = json.loads((tmp_path / "p" / "brain" / "monitor_state.json").read_text(encoding="utf-8"))
    assert state["a.cz"]["state"] == "ok" and len(state["a.cz"]["history"]) == 3


def test_two_failures_are_not_an_outage(tmp_path):
    monitor, logged = make(tmp_path, [FAIL, FAIL, OK, FAIL, FAIL])
    run(monitor, 5)
    assert logged == []


def test_slow_and_recovery(tmp_path):
    monitor, logged = make(tmp_path, [SLOW] * 4 + [OK])
    run(monitor, 5)
    assert [entry[2] for entry in logged] == ["slow.failed", "outage.recovered"]


def test_slow_threshold_from_project_settings(tmp_path):
    monitor, logged = make(tmp_path, [SLOW] * 3, settings={"monitor": {"enabled": True, "slowMs": 3000}})
    run(monitor, 3)
    assert logged == []


def test_disabled_project_and_draft_are_not_measured(tmp_path):
    monitor, logged = make(tmp_path, [], settings={"goal": ""})
    assert monitor.run("p") == [] and monitor.run("draft") == [] and logged == []


def test_project_without_hosts(tmp_path):
    monitor, logged = make(tmp_path, [], hosts=())
    assert monitor.run("p") == [] and logged == []
