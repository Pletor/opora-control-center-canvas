import json
import socket

from backend.integrations.typesafe_client import ENDPOINT, MODEL, evaluate

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


def test_failures_return_none():
    for status in (401, 422, 429, 529):
        post, _ = fake(status=status, payload={"answers": {}})
        assert evaluate("x", QUESTIONS, key="k", post=post) is None
    for post, _ in (fake(raw=b"not json"), fake(payload={"answers": []}), fake(error=socket.timeout()),
                    fake(error=OSError("down"))):
        assert evaluate("x", QUESTIONS, key="k", post=post) is None
