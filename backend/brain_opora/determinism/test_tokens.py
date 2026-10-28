"""Tokeny brány: ukládá se jen otisk, pracovník platí 8 h, zneplatnění a restart procesu."""
from datetime import UTC, datetime, timedelta

import pytest

from backend.brain_opora.determinism import tokens
from backend.canvas.canvas_service import CanvasService

NOW = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def test_worker_token_is_stored_only_as_hash_and_lives_8_hours(service):
    issued = tokens.issue_worker(service, "draft", "draft", {"name": "dev", "office": "o1"}, now=NOW)
    assert len(issued["token"]) >= 40 and issued["expiresAt"] == "2026-10-28T18:00:00Z"
    stored = service.db_for("draft").execute("SELECT token_hash FROM gate_sessions").fetchone()
    assert stored[0] == tokens.hash_token(issued["token"]) and issued["token"] not in stored[0]
    assert tokens.verify(service, issued["token"], now=NOW)["id"] == issued["sessionId"]
    assert tokens.verify(service, issued["token"], now=NOW + timedelta(hours=8)) is None


def test_unknown_or_malformed_tokens_are_invalid(service):
    assert tokens.verify(service, "x" * 43) is None
    assert tokens.verify(service, None) is None and tokens.verify(service, "short") is None


def test_revoked_token_is_invalid(service):
    issued = tokens.issue_worker(service, "draft", "draft", {"name": "dev"})
    assert tokens.revoke(service, "draft", issued["sessionId"]) is True
    assert tokens.verify(service, issued["token"]) is None


def test_heart_token_has_no_expiry_and_is_found_after_restart(service, monkeypatch):
    session_id, token = tokens.issue_heart(service, "draft", "draft", now=NOW)
    monkeypatch.setattr(tokens, "_WHERE", {})  # proces po restartu nic nepamatuje
    session = tokens.verify(service, token, now=NOW + timedelta(days=30))
    assert session["id"] == session_id and session["role"] == "heart" and session["expires_at"] is None
