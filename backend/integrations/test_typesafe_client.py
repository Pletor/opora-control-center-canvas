import json
import logging
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from backend.integrations import typesafe_client
from backend.integrations.typesafe_client import (
    CELERIS_ENDPOINT,
    CELERIS_MODEL,
    ENDPOINT,
    MODEL,
    _post,
    build_opener,
    configured_provider,
    evaluate,
    provider_from,
)

QUESTIONS = {"urgent": {"type": "noul", "instructions": "Je to naléhavé?"}}


def fake(status=200, payload=None, raw=None, error=None):
    calls = []

    def post(url, body, headers, timeout):
        calls.append({"url": url, "body": json.loads(body), "headers": headers, "timeout": timeout})
        if error:
            raise error
        return status, raw if raw is not None else json.dumps(payload or {}).encode()

    return post, calls


def test_without_key_does_not_call():
    post, calls = fake()
    assert evaluate("x", QUESTIONS, key=None, post=post) is None
    assert evaluate("x", QUESTIONS, key="", post=post) is None
    assert calls == []


def test_sends_contract_request_and_returns_answers():
    answers = {"urgent": {"type": "noul", "noul": 0.9}}
    post, calls = fake(payload={"model": "jev-1.13.0", "answers": answers})
    assert evaluate({"request": "x"}, QUESTIONS, key="k1", timeout=2.0, post=post) == answers
    call = calls[0]
    assert call["url"] == ENDPOINT
    assert call["body"] == {"state": {"request": "x"}, "model": MODEL, "questions": QUESTIONS}
    assert call["headers"]["Authorization"] == "Bearer k1"
    assert call["timeout"] == 2.0


def test_celeris_provider_uses_its_endpoint_and_model():
    post, calls = fake(payload={"answers": {"urgent": {"type": "noul", "noul": 0.2}}})
    assert evaluate("x", QUESTIONS, key="c1", provider="celeris", post=post) is not None
    assert calls[0]["url"] == CELERIS_ENDPOINT == "https://inference.celeris.ai/celeris-1-decision/v1/systemone"
    assert calls[0]["body"]["model"] == CELERIS_MODEL == "celeris-1-decision"
    assert calls[0]["headers"]["Authorization"] == "Bearer c1"
    assert "c1" not in json.dumps(calls[0]["body"])


def test_unknown_provider_sends_nothing():
    post, calls = fake()
    assert evaluate("x", QUESTIONS, key="k", provider="https://evil.example", post=post) is None
    assert calls == []


def test_provider_from_config_and_env(caplog):
    assert provider_from(None) == "typesafe" and provider_from("") == "typesafe"
    assert provider_from(" Celeris ") == "celeris"
    with caplog.at_level(logging.WARNING, logger=typesafe_client.__name__):
        assert provider_from("openai") == "typesafe"
        assert provider_from(["celeris"]) == "typesafe"
    assert "openai" in caplog.text
    assert configured_provider({"OPORA_JEV_PROVIDER": "celeris"}) == "celeris"
    assert configured_provider({}) == "typesafe"


def test_default_post_rejects_endpoint_outside_allowlist():
    with pytest.raises(ValueError):
        _post("http://127.0.0.1:1/v1/systemone", b"{}", {}, 1.0)
    # evaluate poruchu přenosu spolkne
    assert evaluate("x", QUESTIONS, key="k", post=lambda *a: _post("https://evil.example/", b"", {}, 1.0)) is None


def test_opener_has_no_default_redirect_handler():
    handlers = build_opener().handlers
    redirects = [h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
    assert len(redirects) == 1 and type(redirects[0]) is typesafe_client._NoRedirect


def test_opener_does_not_follow_redirect():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            hits.append(self.path)
            if self.path == "/start":
                self.send_response(307)
                self.send_header("Location", "/elsewhere")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/start"
        request = urllib.request.Request(url, data=b"{}", headers={"Authorization": "Bearer secret"}, method="POST")
        with pytest.raises(urllib.error.HTTPError) as caught:
            build_opener().open(request, timeout=5)
        assert caught.value.code == 307
        assert hits == ["/start"]
    finally:
        server.shutdown()
        server.server_close()


def test_failures_return_none():
    for status in (301, 302, 401, 422, 429, 529):
        post, _ = fake(status=status, payload={"answers": {}})
        assert evaluate("x", QUESTIONS, key="k", post=post) is None
    for post, _ in (fake(raw=b"not json"), fake(payload={"answers": []}), fake(error=TimeoutError()),
                    fake(error=OSError("down"))):
        assert evaluate("x", QUESTIONS, key="k", post=post) is None
