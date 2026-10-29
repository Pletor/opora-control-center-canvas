"""Routa `/api/rlm/rank` nad falešným Jev: ok, bez klíče, porucha (backend/brain_opora/decision/README.md)."""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.editor.rlm_routes import create_rlm_router
from backend.app.factory import create_app

PAYLOAD = {"project": "p1", "workspace": "draft", "query": "platby",
           "candidates": [{"id": "a", "text": "Přihlášení"}, {"id": "b", "text": "Platby"}], "top": 5}


def client_for(*, key, answer=None, error=None):
    calls = []

    def evaluate(state, questions, *, key):
        calls.append({"state": state, "questions": questions, "key": key})
        if error:
            raise error
        return answer if key else None

    app = FastAPI()

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    app.include_router(create_rlm_router(key_source=lambda: key, evaluate=evaluate))
    return TestClient(app), calls


def test_ok_ranks_known_ids_with_the_app_key():
    client, calls = client_for(key="tajny", answer={"rank": {"type": "choice", "choice": "b", "confidence": 0.7,
                                                             "probabilities": {"b": 0.7, "a": 0.3, "x": 0.9}}})
    answer = client.post("/api/rlm/rank", json=PAYLOAD)
    assert answer.status_code == 200
    assert answer.json() == {"status": "ok", "ranked": [{"id": "b", "p": 0.7}, {"id": "a", "p": 0.3}]}
    assert calls[0]["key"] == "tajny" and "tajny" not in answer.text
    assert calls[0]["state"] == {"query": "platby"}


def test_without_key_is_unavailable():
    client, _ = client_for(key=None, answer={"rank": {"probabilities": {"a": 1.0}}})
    assert client.post("/api/rlm/rank", json=PAYLOAD).json() == {"status": "unavailable"}


def test_jev_failure_is_unavailable():
    client, _ = client_for(key="k", error=RuntimeError("529"))
    assert client.post("/api/rlm/rank", json=PAYLOAD).json() == {"status": "unavailable"}


@pytest.mark.parametrize("change", [{"extra": 1}, {"project": ""}, {"top": 0}, {"candidates": []}])
def test_invalid_payload_is_409(change):
    client, calls = client_for(key="k")
    assert client.post("/api/rlm/rank", json={**PAYLOAD, **change}).status_code == 409
    assert calls == []


def test_factory_registers_rank_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8740") as client:
        answer = client.post("/api/rlm/rank", json=PAYLOAD, headers={"origin": "http://127.0.0.1:8740"})
    assert answer.status_code == 200 and answer.json() == {"status": "unavailable"}
