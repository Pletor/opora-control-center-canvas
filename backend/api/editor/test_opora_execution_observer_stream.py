"""The observer router independently bounds chunked ASGI bodies without middleware."""
import asyncio

from fastapi import FastAPI

from backend.api.editor import opora_execution_observer_routes as routes


def test_route_stops_stream_at_first_oversize_chunk_before_authentication(monkeypatch):
    def unexpected(*_):
        raise AssertionError("Authentication must not see an oversized body.")
    monkeypatch.setattr(routes, "authenticate", unexpected)
    app = FastAPI()
    app.include_router(routes.create_execution_observer_router(object()))
    received, sent = [], []
    chunks = [b"x" * 65536, b"x" * 65536, b"x"]

    async def receive():
        index = len(received)
        assert index < len(chunks), "The route consumed data after crossing its bound."
        received.append(index)
        return {"type": "http.request", "body": chunks[index], "more_body": True}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
             "scheme": "http", "path": "/api/oporahub/execution-observers/intents", "raw_path": b"/api/oporahub/execution-observers/intents",
             "query_string": b"", "root_path": "", "headers": [(b"content-type", b"application/json")],
             "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 8740)}
    asyncio.run(app(scope, receive, send))
    assert received == [0, 1, 2]
    assert sent[0]["status"] == 413
