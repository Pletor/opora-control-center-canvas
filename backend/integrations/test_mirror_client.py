"""Klient Zrcadla proti falešné službě na 127.0.0.1 (docs/zrcadlo.md): zapnuto, vypnuto, timeout, neplatná odpověď,
nelokální adresa, přesměrování. Klient nikdy nevyhodí a vrací None."""
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.integrations import mirror_client
from backend.integrations.mirror_client import MirrorClient, client_for, loopback_url, settings

PREDICTION = {"predictionId": "p1", "expected": {"tests": "pass", "criticRounds": 1}, "confidence": 0.4}
OBSERVATION = {"predictionError": 0.15, "accuracy": 1.0,
               "hormones": {"dopamin": 1.0, "serotonin": 1.02, "kortizol": 0.99, "oxytocin": 1.03}}


@contextmanager
def fake_service(routes, delay=0.0):
    """Falešná služba: `routes[(metoda, cesta)]` = (status, tělo dict|bytes, hlavičky). Zapisuje přijatá těla."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _answer(self, method):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            received.append({"method": method, "path": self.path, "body": body, "host": self.headers.get("Host")})
            time.sleep(delay)
            status, payload, headers = routes.get((method, self.path), (404, {"error": "x"}, {}))
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._answer("GET")

        def do_POST(self):
            self._answer("POST")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", received
    finally:
        server.shutdown()
        server.server_close()


def test_enabled_health_predict_observe_against_fake_service():
    routes = {("GET", "/health"): (200, {"ok": True, "model": "fake", "events": 2}, {}),
              ("POST", "/predict"): (200, PREDICTION, {}),
              ("POST", "/observe"): (200, OBSERVATION, {})}
    with fake_service(routes) as (url, received):
        client = MirrorClient(url)
        assert client.health() == {"ok": True, "model": "fake", "events": 2}
        assert client.predict(fragment_id="f1", discipline="be", title="T", text="x" * 9000, microstep="API: hotovo") == PREDICTION
        assert client.observe(prediction_id="p1", actual={"tests": "fail", "criticRounds": 3, "unexpected": True}) == OBSERVATION
    sent = received[1]["body"]
    assert sent["fragmentId"] == "f1" and sent["discipline"] == "be" and len(sent["text"]) == mirror_client.MAX_TEXT
    # Brána dovoluje 3 kola kritika, služba 0–2: skutečnost se ořízne.
    assert received[2]["body"] == {"predictionId": "p1", "actual": {"tests": "fail", "criticRounds": 2, "unexpected": True}}
    assert received[0]["host"].startswith("127.0.0.1:")


def test_disabled_settings_and_project_isolation(monkeypatch):
    assert client_for("p1", {}) is None
    assert client_for("p1", {"OPORA_MIRROR_URL": "", "OPORA_MIRROR_PROJECTS": "p1"}) is None
    assert client_for("p2", {"OPORA_MIRROR_URL": "http://127.0.0.1:8750", "OPORA_MIRROR_PROJECTS": "p1"}) is None
    found = client_for("p1", {"OPORA_MIRROR_URL": "http://localhost:8750/", "OPORA_MIRROR_PROJECTS": " p1 , p3"})
    assert found is not None and found.url == "http://localhost:8750"
    assert MirrorClient("").health() is None and MirrorClient(None).predict(
        fragment_id="f", discipline="be", title="", text="", microstep=None) is None


@pytest.mark.parametrize("url", ["http://10.0.0.5:8750", "https://127.0.0.1:8750", "http://example.com",
                                 "http://user:pw@127.0.0.1:8750", "http://127.0.0.1:8750/api", "http://127.0.0.1:99999",
                                 "http://127.0.0.1.evil.com:8750", "ftp://localhost"])
def test_non_loopback_url_is_disabled_with_warning(url, caplog):
    assert loopback_url(url) is None
    mirror_client._warned.discard(url)
    with caplog.at_level("WARNING"):
        assert settings({"OPORA_MIRROR_URL": url, "OPORA_MIRROR_PROJECTS": "p1"})["url"] is None
    assert "Zrcadlo je vypnuté" in caplog.text
    calls = []
    client = MirrorClient(url, transport=lambda *args: calls.append(args) or (200, b"{}"))
    assert client.health() is None and calls == []


def test_timeout_returns_none():
    with fake_service({("GET", "/health"): (200, {"ok": True, "model": "m", "events": 0}, {})}, delay=0.6) as (url, _):
        started = time.monotonic()
        assert MirrorClient(url, timeout=0.2).health() is None
        assert time.monotonic() - started < 0.55


@pytest.mark.parametrize("answer", [
    (200, b"not json", {}), (200, b"", {}), (500, {"error": "x"}, {}), (404, {"error": "unknown predictionId"}, {}),
    (200, {"predictionId": "", "expected": {"tests": "pass", "criticRounds": 1}, "confidence": 0.4}, {}),
    (200, {"predictionId": "p", "expected": {"tests": "maybe", "criticRounds": 1}, "confidence": 0.4}, {}),
    (200, {"predictionId": "p", "expected": {"tests": "pass", "criticRounds": 5}, "confidence": 0.4}, {}),
    (200, {"predictionId": "p", "expected": {"tests": "pass", "criticRounds": 1}, "confidence": 2}, {}),
    (200, b"x" * (mirror_client.MAX_RESPONSE_BYTES + 10), {}),
])
def test_invalid_answer_returns_none(answer):
    with fake_service({("POST", "/predict"): answer}) as (url, _):
        assert MirrorClient(url).predict(fragment_id="f", discipline="be", title="T", text="x", microstep=None) is None


def test_invalid_observation_returns_none():
    bad = {**OBSERVATION, "hormones": {"dopamin": 1.0}}
    with fake_service({("POST", "/observe"): (200, bad, {})}) as (url, _):
        assert MirrorClient(url).observe(prediction_id="p1", actual={"tests": "pass", "criticRounds": 0}) is None
    assert MirrorClient("http://127.0.0.1:1").observe(prediction_id="", actual={}) is None


def test_redirect_is_not_followed():
    with fake_service({("GET", "/target"): (200, {"ok": True, "model": "m", "events": 0}, {})}) as (target, received):
        routes = {("GET", "/health"): (302, b"", {"Location": target + "/target"})}
        with fake_service(routes) as (url, first):
            assert MirrorClient(url).health() is None
        assert [item["path"] for item in first] == ["/health"]
        assert received == []


def test_unreachable_service_and_transport_error_never_raise():
    assert MirrorClient("http://127.0.0.1:1", timeout=0.5).health() is None

    def broken(*args):
        raise OSError("síť")

    assert MirrorClient("http://127.0.0.1:8750", transport=broken).predict(
        fragment_id="f", discipline="be", title="T", text="x", microstep=None) is None


def test_observe_maps_untested_to_pass_fail_and_keeps_plan_fields():
    received = []

    def transport(method, url, data, timeout):
        received.append(json.loads(data))
        return 200, json.dumps(OBSERVATION).encode()

    client = MirrorClient("http://127.0.0.1:1", transport=transport)
    client.observe(prediction_id="p1", actual={"tests": "untested", "planApproved": True, "planScore": 8,
                                               "criticRounds": 1, "unexpected": False})
    client.observe(prediction_id="p1", actual={"tests": "untested", "planApproved": False, "criticRounds": 1,
                                               "unexpected": False})
    assert received[0]["actual"] == {"tests": "pass", "criticRounds": 1, "unexpected": False, "testsReported": "untested",
                                     "planApproved": True, "planScore": 8}
    assert received[1]["actual"]["tests"] == "fail" and received[1]["actual"]["planApproved"] is False
