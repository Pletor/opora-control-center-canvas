import pytest
from fastapi.testclient import TestClient

from backend.app.embed_origins import ENV_NAME, frame_policy, parse_embed_origins, validate_origin
from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"


def test_valid_origins_are_canonical_and_deduplicated():
    assert parse_embed_origins(["http://localhost:4600", "http://LOCALHOST:4600/", "https://127.0.0.1"]) == (
        "http://localhost:4600", "https://127.0.0.1")
    assert parse_embed_origins("http://localhost:4600  http://[::1]:4600") == (
        "http://localhost:4600", "http://[::1]:4600")
    assert parse_embed_origins([]) == parse_embed_origins("") == parse_embed_origins(None) == ()


@pytest.mark.parametrize("entry", [
    "*", "http://*.localhost", "null", "NULL", "", "  ", 4600, None,
    "localhost:4600", "ftp://localhost", "file:///c:/x", "javascript:alert(1)",
    "http://localhost:4600/office", "http://localhost:4600?x=1", "http://localhost:4600#a",
    "http://user:pw@localhost:4600", "http://localhost:99999", "http://localhost:abc",
    "http://localhost:4600 'unsafe-inline'", "http://a;script-src *", "http://",
])
def test_invalid_origin_fails_with_czech_message(entry):
    with pytest.raises(ValueError, match="Neplatný původ v \\[app\\] embed_origins"):
        validate_origin(entry)


def test_embed_origins_must_be_a_list():
    with pytest.raises(ValueError, match="musí být seznam"):
        parse_embed_origins({"a": 1})


def test_frame_policy_default_and_configured():
    assert frame_policy(()) == ("DENY", "frame-ancestors 'none'")
    assert frame_policy(("http://localhost:4600",)) == (None, "frame-ancestors 'self' http://localhost:4600")


def _headers(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        page = client.get("/api/bootstrap")
        blocked_host = client.get("/api/bootstrap", headers={"host": "evil.test"})
        foreign_write = client.post("/api/connect", json={"url": "https://github.com/x/y", "approved": True},
                                    headers={"origin": "http://localhost:4600"})
        return page, blocked_host, foreign_write


def test_default_keeps_frame_deny(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_NAME, raising=False)
    page, _, _ = _headers(tmp_path)
    assert page.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_configured_origins_allow_framing_and_keep_other_boundaries(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_NAME, "http://localhost:4600")
    page, blocked_host, foreign_write = _headers(tmp_path)
    assert "x-frame-options" not in page.headers
    csp = page.headers["content-security-policy"]
    assert csp == ("img-src 'self' data: blob: https:; object-src 'none'; base-uri 'self'; "
                   "frame-ancestors 'self' http://localhost:4600")
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["referrer-policy"] == "no-referrer"
    # Vložení nepovoluje cizí Host ani zápis z původu rámující aplikace.
    assert blocked_host.status_code == 403
    assert foreign_write.status_code == 403


def test_invalid_env_value_fails_startup(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_NAME, "http://localhost:4600/office")
    with pytest.raises(ValueError, match="embed_origins"):
        create_app(tmp_path / "data")
