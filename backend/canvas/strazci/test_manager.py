"""Worker strážců: interval, přeskočení, izolace chyb a stav v paměti; vše s falešným časem."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.strazci.manager import GuardianManager, interval
from backend.canvas.strazci.registry import Guard, default_guards, validate_registry

NOW = 1_800_000_000.0


@pytest.fixture
def service(tmp_path):
    instance = CanvasService(tmp_path / "data")
    yield instance
    instance.close()


def finding(key, severity="warn"):
    return {"key": key, "rule": "test.rule", "severity": severity, "message": "Nález"}


def test_guard_runs_only_after_its_interval(service):
    calls = []
    guard = Guard("g", "G", 60, lambda ctx: calls.append(ctx.now) or [])
    manager = GuardianManager(service, guards=[guard])
    manager.run_once(NOW)
    manager.run_once(NOW + 30)
    manager.run_once(NOW + 60)
    assert calls == [NOW, NOW + 60]


def test_failing_guard_records_last_error_and_others_keep_running(service):
    def broken(ctx):
        raise RuntimeError("rozbitý vstup")

    manager = GuardianManager(service, guards=[Guard("zly", "Zlý", 10, broken),
                                               Guard("dobry", "Dobrý", 10, lambda ctx: [finding("k1", "block")])])
    results = manager.run_once(NOW)
    assert {(item["guard"], item["outcome"] if isinstance(item["outcome"], str) else "ok") for item in results} == {
        ("zly", "error"), ("dobry", "ok")}
    status = manager.status("draft")
    bad, good = status["guards"]
    assert bad["lastError"] == "RuntimeError: rozbitý vstup" and bad["lastOkAt"] is None and bad["lastRunAt"]
    assert "lastError" not in good and good["lastOkAt"] == good["lastRunAt"] and good["open"]["block"] == 1
    assert status["open"] == {"block": 1, "warn": 0, "info": 0}


def test_invalid_output_counts_as_guard_error(service):
    manager = GuardianManager(service, guards=[Guard("g", "G", 10, lambda ctx: [{"key": "k"}])])
    manager.run_once(NOW)
    assert manager.status("draft")["guards"][0]["lastError"].startswith("ValueError")


def test_error_clears_after_a_good_run(service):
    outputs = iter([RuntimeError("jednou"), []])

    def flaky(ctx):
        value = next(outputs)
        if isinstance(value, Exception):
            raise value
        return value

    manager = GuardianManager(service, guards=[Guard("g", "G", 10, flaky)])
    manager.run_once(NOW)
    manager.run_once(NOW + 10)
    assert "lastError" not in manager.status("draft")["guards"][0]


def test_skip_updates_only_last_run_and_memo_survives_only_success(service):
    seen = []

    def remembering(ctx):
        seen.append(dict(ctx.memo))
        if ctx.memo.get("head") == "h":
            return None
        ctx.memo["head"] = "h"
        return []

    manager = GuardianManager(service, guards=[Guard("g", "G", 10, remembering)])
    manager.run_once(NOW)
    manager.run_once(NOW + 10)
    state = manager.status("draft")["guards"][0]
    assert seen == [{}, {"head": "h"}]
    assert state["lastRunAt"] != state["lastOkAt"]


def test_memo_is_not_kept_when_writing_fails(service):
    seen = []

    def guard(ctx):
        seen.append(dict(ctx.memo))
        ctx.memo["head"] = "h"
        return [{"key": "k", "rule": "r", "severity": "wrong", "message": "m"}]

    manager = GuardianManager(service, guards=[Guard("g", "G", 10, guard)])
    manager.run_once(NOW)
    manager.run_once(NOW + 10)
    assert seen == [{}, {}]


def test_worker_is_off_in_tests_and_interval_reads_environment(service, monkeypatch):
    manager = GuardianManager(service, guards=[])
    manager.start()
    assert manager.thread is None
    manager.close()
    monkeypatch.setenv("OPORA_GUARDS_SECONDS", "5")
    assert interval() == 5.0
    monkeypatch.setenv("OPORA_GUARDS_SECONDS", "nic")
    assert interval() == 30.0


def test_worker_loop_survives_a_failing_pass(service, monkeypatch):
    monkeypatch.setenv("OPORA_GUARDS_WORKER", "1")
    passes = []
    manager = GuardianManager(service, guards=[], tick=0.01)

    def run_once(now=None):
        passes.append(now)
        if len(passes) == 1:
            raise RuntimeError("průchod")
        manager.stop.set()

    manager.run_once = run_once
    manager.start()
    manager.thread.join(timeout=2)
    assert len(passes) == 2


def test_registry_has_mapa_and_prace_and_refuses_duplicates():
    assert [guard.id for guard in default_guards()] == ["mapa", "prace"]
    with pytest.raises(ValueError):
        validate_registry([Guard("g", "G", 1, list), Guard("g", "H", 1, list)])
    with pytest.raises(ValueError):
        validate_registry([Guard("g", "G", 0, list)])
