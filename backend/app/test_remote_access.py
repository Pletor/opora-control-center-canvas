import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.remote_access import (
    COOKIE_NAME,
    RemoteAccess,
    bearer_token,
    host_matches,
    hostname_of,
    is_loopback_only,
    parse_hosts,
    requires_token,
    scheme_from,
    token_is_strong,
    tokens_equal,
)

TOKEN = "z" * 32
PUBLIC = "abc-def.trycloudflare.com"


@pytest.fixture
def remote_app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_PUBLIC_HOSTS", "*.trycloudflare.com")
    monkeypatch.setenv("OPORA_ACCESS_TOKEN", TOKEN)
    return create_app(tmp_path)


def test_parse_hosts_and_matching():
    assert parse_hosts(" a.example , *.trycloudflare.com ,") == ("a.example", "*.trycloudflare.com")
    assert parse_hosts("") == () and parse_hosts(None) == ()
    assert hostname_of("Abc.Example:443") == "abc.example"
    assert hostname_of("[::1]:8740") == "::1"
    patterns = parse_hosts("a.example,*.trycloudflare.com")
    assert host_matches(patterns, "A.Example")
    assert host_matches(patterns, PUBLIC)
    assert host_matches(patterns, PUBLIC + ":443")
    # Samotná doména bez jména tunelu nestačí a cizí host se nepodobá ničemu.
    assert not host_matches(patterns, "trycloudflare.com")
    assert not host_matches(patterns, "evil-trycloudflare.com")
    assert not host_matches(patterns, "")


def test_token_rules_and_paths():
    assert token_is_strong(TOKEN) and not token_is_strong("krátký")
    assert tokens_equal(TOKEN, TOKEN) and not tokens_equal(TOKEN, TOKEN[:-1] + "y")
    assert not tokens_equal(TOKEN, None) and not tokens_equal("", "")
    assert bearer_token("Bearer " + TOKEN) == TOKEN
    assert bearer_token(TOKEN) is None and bearer_token("Bearer   ") is None
    assert is_loopback_only("/api/agent-hooks/event") and is_loopback_only("/api/agent-hooks/ack")
    assert not is_loopback_only("/api/agent-hooks/events")
    assert requires_token("/api/view") and not requires_token("/api/access/status")
    assert not requires_token("/assets/index.js") and not requires_token("/")
    assert scheme_from(None) == "https" and scheme_from("http") == "http"
    assert scheme_from("https, http") == "https" and scheme_from("gopher") == "https"


def test_remote_mode_needs_both_env_values():
    assert not RemoteAccess.from_env({}).active
    assert not RemoteAccess.from_env({"OPORA_PUBLIC_HOSTS": "*.trycloudflare.com"}).active
    assert not RemoteAccess.from_env({"OPORA_ACCESS_TOKEN": TOKEN}).active
    assert not RemoteAccess.from_env({"OPORA_PUBLIC_HOSTS": "*.trycloudflare.com", "OPORA_ACCESS_TOKEN": "short"}).active
    live = RemoteAccess.from_env({"OPORA_PUBLIC_HOSTS": "*.trycloudflare.com", "OPORA_ACCESS_TOKEN": TOKEN})
    assert live.active and live.is_public_host(PUBLIC)
    assert live.origin_for(PUBLIC) == "https://" + PUBLIC
    assert live.origin_for(PUBLIC, "http") == "http://" + PUBLIC
    assert live.authorized("Bearer " + TOKEN) and live.authorized(None, TOKEN)
    assert not live.authorized(None, None) and not live.authorized("Bearer nope")


def test_public_host_is_refused_when_remote_mode_is_off(tmp_path, monkeypatch):
    monkeypatch.delenv("OPORA_PUBLIC_HOSTS", raising=False)
    monkeypatch.delenv("OPORA_ACCESS_TOKEN", raising=False)
    app = create_app(tmp_path)
    with TestClient(app, base_url="https://" + PUBLIC) as client:
        assert client.get("/api/bootstrap").status_code == 403
        assert client.get("/api/access/status").status_code == 403


def test_loopback_keeps_todays_rules_in_remote_mode(remote_app):
    with TestClient(remote_app, base_url="http://127.0.0.1:8740") as client:
        assert client.get("/api/bootstrap").status_code == 200
        assert client.get("/api/access/status").json() == {
            "remote": False, "authenticated": True, "host": "127.0.0.1:8740"
        }
        # Hook control je doma pořád dostupný; zamítnutí přijde z jeho vlastní validace, ne z hranice.
        answer = client.post("/api/agent-hooks/ack", json={"bindingId": "x"},
                             headers={"origin": "http://127.0.0.1:8740"})
        assert answer.json().get("error") != "Hook control běží jen na tomto počítači."


def test_public_host_needs_a_token(remote_app):
    with TestClient(remote_app, base_url="https://" + PUBLIC) as client:
        denied = client.get("/api/bootstrap")
        assert denied.status_code == 401 and denied.json() == {"error": "Přístup vyžaduje token."}
        assert client.get("/api/bootstrap", headers={"authorization": "Bearer nope"}).status_code == 401
        assert client.get("/api/bootstrap", headers={"authorization": "Bearer " + TOKEN}).status_code == 200
        client.cookies.set(COOKIE_NAME, TOKEN)
        assert client.get("/api/bootstrap").status_code == 200
        client.cookies.clear()
        # Stav se ptá i bez tokenu, jinak by přihlašovací obrazovka nevěděla, co ukázat.
        status = client.get("/api/access/status")
        assert status.status_code == 200
        assert status.json() == {"remote": True, "authenticated": False, "host": PUBLIC}


def test_login_sets_the_cookie_and_logout_clears_it(remote_app):
    with TestClient(remote_app, base_url="https://" + PUBLIC) as client:
        origin = {"origin": "https://" + PUBLIC}
        wrong = client.post("/api/access/login", json={"token": "nope"}, headers=origin)
        assert wrong.status_code == 401 and wrong.json() == {"error": "Přístup vyžaduje token."}
        ok = client.post("/api/access/login", json={"token": TOKEN}, headers=origin)
        assert ok.status_code == 200 and ok.json() == {"ok": True}
        cookie = ok.headers["set-cookie"]
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie.replace("samesite", "SameSite")
        assert client.get("/api/access/status").json()["authenticated"] is True
        assert client.get("/api/bootstrap").status_code == 200
        assert client.post("/api/access/logout", json={}, headers=origin).status_code == 200
        assert client.get("/api/bootstrap").status_code == 401


def test_hook_control_stays_on_this_computer(remote_app):
    with TestClient(remote_app, base_url="https://" + PUBLIC) as client:
        headers = {"authorization": "Bearer " + TOKEN, "origin": "https://" + PUBLIC}
        for route in ("/api/agent-hooks/event", "/api/agent-hooks/ack"):
            answer = client.post(route, json={"bindingId": "x"}, headers=headers)
            assert answer.status_code == 403
            assert answer.json() == {"error": "Hook control běží jen na tomto počítači."}
        # Čtení událostí zůstává běžnou routou pod tokenem.
        assert client.get("/api/agent-hooks/events?bindingId=x", headers=headers).status_code != 403


def test_assistant_is_loopback_only():
    assert is_loopback_only("/api/assistant") and is_loopback_only("/api/assistant/status")
    assert is_loopback_only("/api/assistant/sessions/abc/events")
    assert not is_loopback_only("/api/assistantx") and not is_loopback_only("/api/assistants/status")


def test_assistant_refused_through_tunnel_even_with_token(remote_app):
    with TestClient(remote_app, base_url="https://" + PUBLIC) as client:
        headers = {"authorization": "Bearer " + TOKEN, "origin": "https://" + PUBLIC}
        assert client.get("/api/assistant/status", headers=headers).status_code == 403
        assert client.get("/api/assistant/sessions?project=p1", headers=headers).status_code == 403
        assert client.post("/api/assistant/sessions", json={"project": "p1"}, headers=headers).status_code == 403


def test_rlm_is_loopback_only():
    assert is_loopback_only("/api/rlm") and is_loopback_only("/api/rlm/rank")
    assert not is_loopback_only("/api/rlmx/rank")


def test_rlm_rank_refused_through_tunnel_even_with_token(remote_app):
    payload = {"project": "p1", "workspace": "draft", "query": "q", "candidates": [{"id": "a", "text": "A"}], "top": 1}
    with TestClient(remote_app, base_url="https://" + PUBLIC) as client:
        headers = {"authorization": "Bearer " + TOKEN, "origin": "https://" + PUBLIC}
        assert client.post("/api/rlm/rank", json=payload, headers=headers).status_code == 403


def test_https_origin_and_forwarded_proto(remote_app):
    with TestClient(remote_app, base_url="https://" + PUBLIC) as client:
        bearer = {"authorization": "Bearer " + TOKEN}
        assert client.get("/api/bootstrap", headers={**bearer, "origin": "https://" + PUBLIC}).status_code == 200
        assert client.get("/api/bootstrap", headers={**bearer, "origin": "http://" + PUBLIC}).status_code == 403
        forwarded = {**bearer, "origin": "http://" + PUBLIC, "x-forwarded-proto": "http"}
        assert client.get("/api/bootstrap", headers=forwarded).status_code == 200
        assert client.get("/api/bootstrap", headers={**bearer, "origin": "https://evil.test"}).status_code == 403
        # Zápis přes tunel chce stejný https Origin a JSON; jinak 403 jako doma.
        write = client.post("/api/connect", json={"url": "https://github.com/x/y", "approved": False},
                            headers={**bearer, "origin": "https://" + PUBLIC})
        assert write.status_code == 409
        assert client.post("/api/connect", json={}, headers=bearer).status_code == 403


def test_static_files_load_without_a_token(remote_app, monkeypatch):
    # Bez tokenu musí projít všechno mimo /api, jinak by se přihlašovací obrazovka nenačetla.
    with TestClient(remote_app, base_url="https://" + PUBLIC) as client:
        assert client.get("/nic-takoveho.js").status_code != 401
