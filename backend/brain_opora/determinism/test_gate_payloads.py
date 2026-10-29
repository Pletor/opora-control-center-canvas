"""Těla brány: každá chyba nese code a hint, velké tělo je 413, tělo druhu má přesně dané klíče."""
import pytest

from backend.brain_opora.determinism.gate_payloads import (
    GateError,
    inbox_body,
    inbox_query,
    parse_body,
    session_payload,
    shaped,
)


def refused(call, *args):
    with pytest.raises(GateError) as caught:
        call(*args)
    return caught.value


def test_session_payload_shape():
    assert session_payload({"project": "draft", "workspace": "draft", "worker": {"name": " dev ", "floor": "2"}}) == (
        "draft", "draft", {"name": "dev", "floor": "2"})
    for bad in ({}, {"project": "../x", "workspace": "main", "worker": {"name": "a"}},
                {"project": "draft", "workspace": "draft", "worker": {"office": "o"}},
                {"project": "draft", "workspace": "draft", "worker": {"name": ""}}):
        error = refused(session_payload, bad)
        assert error.status == 422 and error.code == "invalid_payload" and error.hint


def test_shaped_body_has_exact_keys_texts_and_ids():
    assert shaped(None, (), ("after",), hint="h") == {}
    assert shaped({"question": "Smím?", "taskId": "ht_1"}, ("question",), ("taskId",), texts=("question",),
                  ids=("taskId",), hint="h") == {"question": "Smím?", "taskId": "ht_1"}
    for bad in ({}, {"question": " "}, {"question": "x", "taskId": "../x"}, {"question": "x", "q": 1}, "x"):
        error = refused(lambda body: shaped(body, ("question",), ("taskId",), texts=("question",), ids=("taskId",),
                                            hint="h"), bad)
        assert error.status == 422 and error.code == "invalid_payload" and error.hint == "h"


def test_body_over_64_kb_is_413():
    assert parse_body(b'{"a": 1}') == {"a": 1}
    error = refused(parse_body, b"x" * (64 * 1024 + 1))
    assert error.status == 413 and error.body()["code"] == "body_too_large"
    assert refused(parse_body, b"{nope").status == 422


def test_inbox_query_bounds():
    assert inbox_query(None, None) == (0, 0) and inbox_query("5", "30") == (5, 30)
    for after, wait in (("-1", "0"), ("0", "31"), ("x", "0")):
        assert refused(inbox_query, after, wait).status == 422
    assert inbox_body(None) == (0, 0) and inbox_body({"after": 3, "wait": 30}) == (3, 30)
    for bad in ({"after": "1"}, {"wait": 31}, {"after": True}, {"cursor": 1}):
        assert refused(inbox_body, bad).status == 422
