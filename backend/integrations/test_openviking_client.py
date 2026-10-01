"""Klient OpenViking: loopback, bez proxy a přesměrování, pravdivá nedostupnost."""

import json

import pytest

from backend.integrations.openviking_client import (
    DEFAULT_OPENVIKING_URL,
    MAX_RESPONSE_BYTES,
    OpenVikingClient,
    OpenVikingUnavailable,
    client_from_env,
)


class FakeResponse:
    def __init__(self, body, status=200):
        self._raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.status = status

    def read(self, size=None):
        return self._raw[:size] if size is not None else self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUrlopen:
    """Zaznamenává požadavky a vrací připravené odpovědi podle cesty."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, request, timeout=None):
        path = request.full_url.split("1933", 1)[-1] if "1933" in request.full_url else request.full_url
        body = request.data and json.loads(request.data.decode("utf-8"))
        self.calls.append({
            "url": request.full_url, "path": path, "method": request.get_method(),
            "headers": {key.lower(): value for key, value in request.header_items()},
            "body": body, "timeout": timeout,
        })
        for key, response in self.responses.items():
            if key in path:
                return FakeResponse(response() if callable(response) else response)
        raise AssertionError("Neočekávaná cesta: " + path)


def envelope(result):
    return {"status": "ok", "result": result, "time": 0.01}


def build(responses, **kwargs):
    fake = FakeUrlopen(responses)
    client = OpenVikingClient(api_key="k", urlopen=fake, **kwargs)
    return client, fake


def test_default_url_is_loopback_and_remote_url_is_refused():
    assert DEFAULT_OPENVIKING_URL == "http://127.0.0.1:1933"
    with pytest.raises(ValueError):
        OpenVikingClient(base_url="http://10.0.0.5:1933", urlopen=FakeUrlopen({}))
    with pytest.raises(ValueError):
        OpenVikingClient(base_url="https://127.0.0.1:1933", urlopen=FakeUrlopen({}))
    with pytest.raises(ValueError):
        OpenVikingClient(base_url="http://user:pass@127.0.0.1:1933", urlopen=FakeUrlopen({}))


def test_health_reads_the_plain_health_body_not_an_envelope():
    client, fake = build({"/health": {"status": "ok", "healthy": True, "version": "0.1.9"}})
    assert client.health() == {"healthy": True, "version": "0.1.9"}
    call = fake.calls[0]
    assert call["method"] == "GET" and call["path"] == "/health"
    assert call["timeout"] == 5.0


def test_data_calls_use_the_longer_data_timeout_health_and_admin_stay_at_five_seconds():
    """Zavektorování prvního dotazu v Ollamě trvá ~20 s; data proto dostanou vlastní strop 30 s,
    zatímco zdraví a správa rolí zůstávají u rychlých 5 s (docs/pamet-agentu.md)."""
    client, fake = build({
        "/sessions/abc123/messages": envelope({"message_count": 1}),
        "/sessions/abc123/commit": envelope({"session_id": "abc123", "task_id": "t-1"}),
        "/sessions": envelope({"session_id": "abc123"}),
        "/tasks/t-1": envelope({"status": "completed"}),
        "/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0}),
        "/content/write": envelope({"uri": "viking://user/role-frontend/resources/a.md"}),
        "/content/set_tags": envelope({"tags_updated": True}),
        "/health": {"status": "ok", "healthy": True, "version": "1"},
        "/admin/accounts/default/users": envelope([{"user_id": "role-backend"}]),
    })
    client.search("role-db", "index", mode="list")
    client.write("role-frontend", "viking://user/role-frontend/resources/a.md", "text", tags=["opora=1"])
    client.session_create("role-tests")
    client.session_add("role-tests", "abc123", "user", "text")
    client.session_commit("role-tests", "abc123")
    client.task("t-1")
    client.health()
    client.admin_list_users("default")

    by_path = {call["path"]: call["timeout"] for call in fake.calls}
    assert by_path["/api/v1/search/search"] == 30.0
    assert by_path["/api/v1/content/write"] == 30.0
    assert by_path["/api/v1/content/set_tags"] == 30.0
    assert by_path["/api/v1/sessions"] == 30.0
    assert by_path["/api/v1/sessions/abc123/messages"] == 30.0
    assert by_path["/api/v1/sessions/abc123/commit"] == 30.0
    assert by_path["/api/v1/tasks/t-1"] == 30.0
    assert by_path["/health"] == 5.0
    assert by_path["/api/v1/admin/accounts/default/users"] == 5.0


def test_constructor_timeouts_are_overridable_and_carried_by_with_api_key():
    fake = FakeUrlopen({
        "/health": {"status": "ok", "healthy": True, "version": "1"},
        "/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0}),
    })
    client = OpenVikingClient(api_key="k", urlopen=fake, timeout=9.0, data_timeout=41.0)
    role_client = client.with_api_key("role-key")
    role_client.health()
    role_client.search("role-db", "index", mode="list")
    assert fake.calls[0]["timeout"] == 9.0
    assert fake.calls[1]["timeout"] == 41.0


def test_client_from_env_reads_timeout_and_data_timeout(monkeypatch):
    monkeypatch.setenv("OPORA_OPENVIKING_TIMEOUT", "9.5")
    monkeypatch.setenv("OPORA_OPENVIKING_DATA_TIMEOUT", "41")
    fake = FakeUrlopen({
        "/health": {"status": "ok", "healthy": True, "version": "1"},
        "/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0}),
    })
    client = client_from_env(urlopen=fake)
    client.health()
    client.search("role-db", "index", mode="list")
    assert fake.calls[0]["timeout"] == 9.5
    assert fake.calls[1]["timeout"] == 41.0
    monkeypatch.delenv("OPORA_OPENVIKING_TIMEOUT")
    monkeypatch.delenv("OPORA_OPENVIKING_DATA_TIMEOUT")
    assert client_from_env(urlopen=FakeUrlopen({}))._timeout == 5.0
    assert client_from_env(urlopen=FakeUrlopen({}))._data_timeout == 30.0


def test_unhealthy_body_and_error_envelope_raise_unavailable():
    client, _ = build({"/health": {"status": "ok", "healthy": False}})
    with pytest.raises(OpenVikingUnavailable):
        client.health()
    client, _ = build({"/search/search": {"status": "error", "error": {"code": "UNAVAILABLE", "message": "down"}}})
    with pytest.raises(OpenVikingUnavailable) as failure:
        client.search("role-frontend", "co", mode="list")
    assert "UNAVAILABLE" in str(failure.value)


def test_oversized_response_is_refused():
    huge = b"x" * (MAX_RESPONSE_BYTES + 10)
    client, _ = build({"/health": huge})
    with pytest.raises(OpenVikingUnavailable):
        client.health()


def test_transport_failure_becomes_unavailable():
    def boom(request, timeout=None):
        raise TimeoutError("no answer")

    client = OpenVikingClient(api_key="k", urlopen=boom)
    with pytest.raises(OpenVikingUnavailable):
        client.health()


def test_api_key_mode_sends_only_the_key_never_identity_headers():
    """V režimu `api_key` server odvozuje identitu z klíče; hlavičky identity odmítá (403)."""
    client, fake = build(
        {"/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0})},
        account="opora",
    )
    client.search("role-backend", "router", mode="list",
                  target_uri="viking://user/role-backend/peers/p1", peer="p1")
    headers = fake.calls[0]["headers"]
    assert headers["x-api-key"] == "k"
    assert "x-openviking-account" not in headers
    assert "x-openviking-user" not in headers
    assert "x-openviking-actor-peer" not in headers
    assert fake.calls[0]["body"]["target_uri"] == "viking://user/role-backend/peers/p1"


def test_trusted_identity_is_opt_in_and_then_carries_account_user_and_peer():
    client, fake = build(
        {"/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0})},
        account="opora", trusted_identity=True,
    )
    client.search("role-backend", "router", mode="list",
                  target_uri="viking://user/role-backend/peers/p1", peer="p1")
    headers = fake.calls[0]["headers"]
    assert headers["x-openviking-account"] == "opora"
    assert headers["x-openviking-user"] == "role-backend"
    assert headers["x-openviking-actor-peer"] == "p1"


def test_with_api_key_makes_a_sibling_client_for_another_role():
    client, fake = build({"/health": {"status": "ok", "healthy": True, "version": "1"}}, account="opora")
    role_client = client.with_api_key("role-key")
    assert role_client.base_url == client.base_url and role_client.account == "opora"
    assert client.has_api_key is True and role_client.has_api_key is True
    role_client.health()
    assert fake.calls[0]["headers"]["x-api-key"] == "role-key"
    client.health()
    assert fake.calls[1]["headers"]["x-api-key"] == "k"
    with pytest.raises(ValueError):
        client.with_api_key("  ")
    assert OpenVikingClient(urlopen=FakeUrlopen({})).has_api_key is False


def test_admin_list_users_reads_a_list_result():
    client, fake = build({"/admin/accounts/default/users": envelope(
        [{"user_id": "admin", "role": "admin"}, {"user_id": "role-backend", "role": "user"}]
    )})
    listed = client.admin_list_users("default")
    assert [item["user_id"] for item in listed] == ["admin", "role-backend"]
    assert fake.calls[0]["method"] == "GET"
    assert fake.calls[0]["path"] == "/api/v1/admin/accounts/default/users"
    assert "x-openviking-account" not in fake.calls[0]["headers"]


def test_admin_register_user_returns_the_user_key_and_defaults_to_role_user():
    client, fake = build({"/admin/accounts/default/users": envelope(
        {"account_id": "default", "user_id": "role-backend", "user_key": "ov-role-key"}
    )})
    assert client.admin_register_user("default", "role-backend") == "ov-role-key"
    assert fake.calls[0]["method"] == "POST"
    assert fake.calls[0]["body"] == {"user_id": "role-backend", "role": "user"}
    with pytest.raises(ValueError):
        client.admin_register_user("default", "role-backend", role="root")
    with pytest.raises(ValueError):
        client.admin_register_user("default", "role backend")


def test_admin_regenerate_key_posts_to_the_key_endpoint():
    client, fake = build({"/users/role-backend/key": envelope({"user_key": "ov-new-key"})})
    assert client.admin_regenerate_key("default", "role-backend") == "ov-new-key"
    assert fake.calls[0]["path"] == "/api/v1/admin/accounts/default/users/role-backend/key"
    assert fake.calls[0]["body"] == {}


def test_admin_calls_refuse_a_result_without_a_key_or_a_list():
    client, _ = build({"/admin/accounts/default/users": envelope({"user_id": "role-backend"})})
    with pytest.raises(OpenVikingUnavailable):
        client.admin_register_user("default", "role-backend")
    client, _ = build({"/admin/accounts/default/users": envelope({"users": []})})
    with pytest.raises(OpenVikingUnavailable):
        client.admin_list_users("default")


def test_list_mode_never_sends_context_only_parameters():
    client, fake = build({"/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0})})
    client.search("role-db", "index", mode="list", peer_scope="actor", limit=7)
    body = fake.calls[0]["body"]
    assert body == {"query": "index", "mode": "list", "limit": 7}


def test_context_mode_sends_peer_scope_and_refuses_target_uri():
    client, fake = build({"/search/search": envelope({"entries": [], "rendered": "", "stats": {}})})
    client.search("role-db", "index", mode="context", peer_scope="actor", limit=5)
    assert fake.calls[0]["body"]["peer_scope"] == "actor"
    with pytest.raises(ValueError):
        client.search("role-db", "index", mode="context", target_uri="viking://user/role-db/memories")
    with pytest.raises(ValueError):
        client.search("role-db", "index", mode="nonsense")


def test_peer_with_a_separator_is_refused_before_any_request():
    client, fake = build({"/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0})})
    with pytest.raises(ValueError):
        client.search("role-db", "index", mode="list", peer="a/b")
    assert fake.calls == []


def test_write_sends_content_and_applies_tags_best_effort():
    client, fake = build({
        "/content/write": envelope({"uri": "viking://user/role-frontend/resources/a.md", "written_bytes": 5}),
        "/content/set_tags": envelope({"tags_updated": True}),
    })
    written = client.write("role-frontend", "viking://user/role-frontend/resources/a.md", "text",
                           tags=["opora=1", "role=role-frontend"])
    assert written["tagsApplied"] is True
    assert fake.calls[0]["body"] == {
        "uri": "viking://user/role-frontend/resources/a.md", "content": "text", "mode": "replace", "wait": False,
    }
    assert fake.calls[1]["body"]["tags"] == ["opora=1", "role=role-frontend"]


def test_failed_tags_do_not_undo_a_successful_write():
    client, _ = build({
        "/content/write": envelope({"uri": "viking://user/role-frontend/resources/a.md"}),
        "/content/set_tags": {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "bad tag"}},
    })
    written = client.write("role-frontend", "viking://user/role-frontend/resources/a.md", "text", tags=["opora=1"])
    assert written["tagsApplied"] is False
    assert written["uri"] == "viking://user/role-frontend/resources/a.md"
    with pytest.raises(ValueError):
        client.write("role-frontend", "viking://user/role-frontend/resources/a.md", "text", tags=["nope"])


def test_write_refuses_a_non_viking_uri_and_a_nul_byte():
    client, fake = build({"/content/write": envelope({})})
    with pytest.raises(ValueError):
        client.write("role-frontend", "http://example.com/a.md", "text")
    with pytest.raises(ValueError):
        client.write("role-frontend", "viking://user/role-frontend/resources/a.md", "te\0xt")
    assert fake.calls == []


def test_session_create_add_commit_and_task():
    client, fake = build({
        "/sessions/abc123/messages": envelope({"message_count": 1}),
        "/sessions/abc123/commit": envelope({"session_id": "abc123", "status": "accepted", "task_id": "t-1"}),
        "/sessions": envelope({"session_id": "abc123", "uri": "viking://user/role-tests/sessions/abc123"}),
        "/tasks/t-1": envelope({"status": "completed"}),
    })
    created = client.session_create("role-tests", "p1")
    assert created["session_id"] == "abc123"
    assert "x-openviking-actor-peer" not in fake.calls[0]["headers"]
    client.session_add("role-tests", "abc123", "user", "co jsem udělal")
    assert fake.calls[1]["body"] == {"role": "user", "content": "co jsem udělal"}
    # Projekt (peer) nese tělo zprávy, protože hlavička identity v režimu api_key neplatí.
    client.session_add("role-tests", "abc123", "user", "další krok", peer="p1")
    assert fake.calls[2]["body"]["peer_id"] == "p1"
    assert client.session_commit("role-tests", "abc123")["task_id"] == "t-1"
    assert client.task("t-1")["status"] == "completed"
    assert fake.calls[4]["method"] == "GET"


def test_session_identifiers_and_message_roles_are_validated():
    client, fake = build({"/sessions": envelope({"session_id": "abc"})})
    with pytest.raises(ValueError):
        client.session_add("role-tests", "../escape", "user", "x")
    with pytest.raises(ValueError):
        client.session_add("role-tests", "abc123", "wizard", "x")
    with pytest.raises(ValueError):
        client.task("../etc")
    assert fake.calls == []


def test_user_must_be_a_bounded_identifier():
    client, fake = build({"/search/search": envelope({"memories": [], "resources": [], "skills": [], "total": 0})})
    with pytest.raises(ValueError):
        client.search("role frontend", "co", mode="list")
    with pytest.raises(ValueError):
        client.search("", "co", mode="list")
    assert fake.calls == []


def test_client_from_env_reads_url_key_and_account(monkeypatch):
    monkeypatch.setenv("OPORA_OPENVIKING_URL", "http://localhost:1933")
    monkeypatch.setenv("OPORA_OPENVIKING_API_KEY", "secret")
    monkeypatch.setenv("OPORA_OPENVIKING_ACCOUNT", "opora")
    client = client_from_env(urlopen=FakeUrlopen({}))
    assert client.base_url == "http://localhost:1933"
    assert client.account == "opora"
    monkeypatch.delenv("OPORA_OPENVIKING_URL")
    monkeypatch.delenv("OPORA_OPENVIKING_ACCOUNT")
    assert client_from_env(urlopen=FakeUrlopen({})).base_url == DEFAULT_OPENVIKING_URL
    assert client_from_env(urlopen=FakeUrlopen({})).account == "default"


def test_api_key_never_appears_in_the_url():
    client, fake = build({"/health": {"status": "ok", "healthy": True, "version": "1"}})
    client.health()
    assert "k" not in fake.calls[0]["url"].replace("127.0.0.1", "").replace("health", "")
