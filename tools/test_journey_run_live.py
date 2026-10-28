"""Hlášení „cesta právě běží“ runneru (`docs/brana-cesty.md` §3a) bez prohlížeče: `_http` je podvržené."""
from tools import journey_run

PLAN = {"applicationId": "web", "journeyId": "kampan"}
SEGMENT = {"from": "s1", "to": "s2", "open": "/"}


def make(monkeypatch, answers):
    calls, warnings = [], []

    def fake(method, url, server, body=None, timeout=30):
        calls.append((method, url, body, timeout))
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(journey_run, "_http", fake)
    return journey_run.LiveRun("http://s", "p1", PLAN, warnings.append), calls, warnings


def test_start_and_progress_are_reported(monkeypatch):
    live, calls, warnings = make(monkeypatch, [(200, {"runId": "r1", "startedAt": "x"}), (204, None), (204, None)])
    live.start()
    live.progress(SEGMENT)
    live.progress(SEGMENT, False)
    assert calls == [
        ("POST", "http://s/api/project-architecture/journey-runs/start",
         {"project": "p1", "journeyId": "kampan", "applicationId": "web"}, journey_run.LIVE_TIMEOUT_S),
        ("POST", "http://s/api/project-architecture/journey-runs/r1/progress", {"segment": {"from": "s1", "to": "s2"}}, 5),
        ("POST", "http://s/api/project-architecture/journey-runs/r1/progress",
         {"segment": {"from": "s1", "to": "s2"}, "ok": False}, 5)]
    assert warnings == []


def test_failed_start_only_warns_and_skips_progress(monkeypatch):
    live, calls, warnings = make(monkeypatch, [OSError("spojení odmítnuto")])
    live.start()
    live.progress(SEGMENT, True)
    assert len(calls) == 1 and live.run_id is None
    assert warnings == ["varování: start běhu se nepodařilo ohlásit (spojení odmítnuto); běh pokračuje"]


def test_failed_progress_warns_once_and_stops_reporting(monkeypatch):
    live, calls, warnings = make(monkeypatch, [(200, {"runId": "r1"}), (404, {"detail": "Běh r1 vypršel."})])
    live.start()
    live.progress(SEGMENT)
    live.progress(SEGMENT, True)
    assert len(calls) == 2
    assert warnings == ["varování: průběh běhu se nepodařilo ohlásit (HTTP 404: Běh r1 vypršel.); běh pokračuje"]
