"""Paměť rolí nad OpenVikingem: pravdivý stav, klíč na roli, žádný vymyšlený výsledek."""

import copy
import sqlite3
import threading

import pytest

from backend.integrations.openviking_client import OpenVikingUnavailable
from backend.memory import roles
from backend.memory.memory_service import AppSettings, MemoryService

SELF_URI = "viking://user/role-backend/memories"
PEER_URI = "viking://user/role-backend/peers/p1"
ADMIN_KEY = "admin-key"


def hit(uri, score, abstract="text", context_type="memory"):
    return {"uri": uri, "context_type": context_type, "level": 0, "abstract": abstract,
            "overview": None, "category": "experiences", "score": score, "match_reason": ""}


class FakeOpenVikingClient:
    """Chová se jako klient; nic nepředstírá, když má být nedostupný.

    `with_api_key` vrací sourozence se stejnými seznamy hovorů — test tak u každého volání
    vidí, **kterým klíčem** proběhlo (`keys[i]` patří ke `calls[i]`).
    """

    base_url = "http://127.0.0.1:1933"
    account = "default"

    def __init__(self, *, healthy=True, results=None, fail=(), api_key=ADMIN_KEY, users=()):
        self.healthy = healthy
        self.results = results or {}
        self.fail = set(fail)
        self.api_key = api_key
        self.users = list(users)
        self.calls = []
        self.keys = []
        self.sessions = []

    # ---- identita ---------------------------------------------------------------------

    @property
    def has_api_key(self):
        return bool(self.api_key)

    def with_api_key(self, api_key):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Klíč OpenVikingu musí být neprázdný text.")
        sibling = copy.copy(self)
        sibling.api_key = api_key
        return sibling

    def _note(self, call):
        self.calls.append(call)
        self.keys.append(self.api_key)

    def _guard(self, name):
        self._note(name)
        if name in self.fail:
            raise OpenVikingUnavailable(f"{name} selhalo")

    # ---- data -------------------------------------------------------------------------

    def health(self):
        self._guard("health")
        if not self.healthy:
            raise OpenVikingUnavailable("není zdravý")
        return {"healthy": True, "version": "0.1.9"}

    def search(self, user, query, *, mode, target_uri=None, peer=None, peer_scope="actor", limit=20):
        self._note(("search", user, query, mode, target_uri, peer, limit))
        if "search" in self.fail:
            raise OpenVikingUnavailable("search selhalo")
        found = self.results.get(target_uri, [])
        return {"memories": found, "resources": [], "skills": [], "total": len(found)}

    def write(self, user, uri, text, tags=None):
        self._note(("write", user, uri, text, tuple(tags or ())))
        if "write" in self.fail:
            raise OpenVikingUnavailable("write selhalo")
        return {"uri": uri, "written_bytes": len(text), "tagsApplied": True}

    def session_create(self, user, peer=None):
        self._note(("session_create", user, peer))
        if "session_create" in self.fail:
            raise OpenVikingUnavailable("session selhala")
        return {"session_id": "s-1"}

    def session_add(self, user, session_id, role, content, peer=None):
        self._note(("session_add", user, session_id, role, content, peer))
        if "session_add" in self.fail:
            raise OpenVikingUnavailable("zpráva selhala")
        self.sessions.append(content)
        return {"message_count": len(self.sessions)}

    def session_commit(self, user, session_id):
        self._note(("session_commit", user, session_id))
        if "session_commit" in self.fail:
            raise OpenVikingUnavailable("commit selhal")
        return {"session_id": session_id, "status": "accepted", "task_id": "t-9"}

    def task(self, task_id, user=None):
        self._note(("task", task_id))
        return {"status": "completed"}

    # ---- správa uživatelů --------------------------------------------------------------

    def admin_list_users(self, account=None):
        self._note(("admin_list_users", account))
        if "admin_list_users" in self.fail:
            raise OpenVikingUnavailable("seznam uživatelů selhal")
        return [{"user_id": user_id, "role": "user"} for user_id in self.users]

    def admin_register_user(self, account, user_id, role="user"):
        self._note(("admin_register_user", account, user_id, role))
        if user_id in self.fail:
            raise OpenVikingUnavailable(f"{user_id} nelze založit")
        self.users.append(user_id)
        return f"new-{user_id}"

    def admin_regenerate_key(self, account, user_id):
        self._note(("admin_regenerate_key", account, user_id))
        if user_id in self.fail:
            raise OpenVikingUnavailable(f"{user_id} nelze obnovit")
        return f"regen-{user_id}"


class Toggle:
    """Přepínač i úložiště klíčů rolí v paměti; výchozí stav je „každá role má klíč“."""

    def __init__(self, value=True, keys=None):
        self.value = value
        self.keys = ({role_id: f"key-{role_id}" for role_id in roles.role_ids()}
                     if keys is None else dict(keys))

    def enabled(self):
        return self.value

    def set_enabled(self, value):
        self.value = bool(value)
        return self.value

    def role_keys(self):
        return dict(self.keys)

    def set_role_keys(self, mapping):
        self.keys = dict(mapping)
        return sorted(self.keys)


def service(client=None, enabled=True, keys=None):
    fake = client or FakeOpenVikingClient()
    return MemoryService(lambda: fake, Toggle(enabled, keys)), fake


# ---- stav -------------------------------------------------------------------------


def test_status_is_configured_only_when_health_answers():
    memory, fake = service()
    assert memory.status() == {
        "status": "configured", "reason": "OpenViking odpovídá na loopbacku.",
        "url": "http://127.0.0.1:1933",
    }
    assert fake.calls == ["health"]


def test_status_is_disabled_when_the_toggle_is_off_and_never_touches_the_network():
    memory, fake = service(enabled=False)
    assert memory.status()["status"] == "disabled"
    assert fake.calls == []


def test_status_is_unavailable_when_health_fails():
    memory, _ = service(FakeOpenVikingClient(healthy=False))
    result = memory.status()
    assert result["status"] == "unavailable" and result["reason"]


def test_status_needs_provisioning_when_a_role_has_no_key():
    memory, _ = service(keys={"role-backend": "key-role-backend"})
    result = memory.status()
    assert result["status"] == "needs_provisioning"
    assert "role-backend" not in result["missingRoles"]
    assert "role-frontend" in result["missingRoles"] and "role-db" in result["missingRoles"]
    assert "role-frontend" in result["reason"]


def test_status_needs_provisioning_without_the_admin_key():
    memory, _ = service(FakeOpenVikingClient(api_key=None))
    result = memory.status()
    assert result["status"] == "needs_provisioning" and result["missingRoles"] == []
    assert "OPORA_OPENVIKING_ADMIN_API_KEY" in result["reason"]


def test_bootstrap_status_never_calls_the_network():
    memory, fake = service()
    assert memory.bootstrap_status() == {"enabled": True, "status": "unknown"}
    memory.settings.set_enabled(False)
    assert memory.bootstrap_status() == {"enabled": False, "status": "disabled"}
    assert fake.calls == []


# ---- vybavení ---------------------------------------------------------------------


def test_recall_reads_the_role_and_the_project_scope_and_labels_the_origin():
    fake = FakeOpenVikingClient(results={
        SELF_URI: [hit("viking://user/role-backend/memories/experiences/a.md", 0.9)],
        PEER_URI: [hit("viking://user/role-backend/peers/p1/resources/cards/n1/log.md", 0.5, "karta")],
    })
    memory, _ = service(fake)
    result = memory.recall("role-backend", "p1", "n1", "jak psát router")
    assert result["status"] == "configured" and result["role"] == "role-backend"
    assert [(item["origin"], item["score"]) for item in result["items"]] == [("self", 0.9), ("project", 0.5)]
    assert "experiences/a.md" in result["rendered"] and "karta" in result["rendered"]
    searches = [call for call in fake.calls if call[0] == "search"]
    assert [call[3] for call in searches] == ["list", "list"]
    assert [call[4] for call in searches] == [SELF_URI, PEER_URI]
    assert searches[1][5] == "p1"


def test_recall_without_a_project_reads_only_the_role_memory():
    fake = FakeOpenVikingClient(results={SELF_URI: [hit("viking://user/role-backend/memories/x.md", 0.4)]})
    memory, _ = service(fake)
    result = memory.recall("role-backend", None, None, "cokoli")
    assert [call[4] for call in fake.calls if call[0] == "search"] == [SELF_URI]
    assert [item["origin"] for item in result["items"]] == ["self"]


def test_recall_is_ordered_by_score_then_uri_and_deduplicates():
    same = "viking://user/role-backend/memories/b.md"
    fake = FakeOpenVikingClient(results={SELF_URI: [
        hit("viking://user/role-backend/memories/c.md", 0.5),
        hit(same, 0.8),
        hit("viking://user/role-backend/memories/a.md", 0.5),
        hit(same, 0.8),
    ]})
    memory, _ = service(fake)
    uris = [item["uri"] for item in memory.recall("role-backend", None, None, "x")["items"]]
    assert uris == [same,
                    "viking://user/role-backend/memories/a.md",
                    "viking://user/role-backend/memories/c.md"]


def test_recall_respects_the_token_budget_and_says_it_truncated():
    long_text = "a" * 400
    fake = FakeOpenVikingClient(results={SELF_URI: [
        hit("viking://user/role-backend/memories/a.md", 0.9, long_text),
        hit("viking://user/role-backend/memories/b.md", 0.8, long_text),
    ]})
    memory, _ = service(fake)
    result = memory.recall("role-backend", None, None, "x", max_tokens=100)
    assert result["truncated"] is True
    assert sum(len(item["text"]) for item in result["items"]) <= 400
    whole = memory.recall("role-backend", None, None, "x", max_tokens=600)
    assert whole["truncated"] is False


def test_recall_is_disabled_or_unavailable_instead_of_raising():
    memory, _ = service(enabled=False)
    off = memory.recall("role-backend", "p1", "n1", "x")
    assert off == {"status": "disabled", "reason": off["reason"], "role": "role-backend",
                   "items": [], "rendered": "", "truncated": False}
    memory, _ = service(FakeOpenVikingClient(fail={"search"}))
    down = memory.recall("role-backend", "p1", "n1", "x")
    assert down["status"] == "unavailable" and down["items"] == [] and down["reason"]


def test_recall_refuses_an_unknown_role_and_an_empty_query():
    memory, _ = service()
    with pytest.raises(ValueError):
        memory.recall("role-nikdo", None, None, "x")
    with pytest.raises(ValueError):
        memory.recall("role-backend", None, None, "  ")
    with pytest.raises(ValueError):
        memory.recall("role-backend", "ne platný", None, "x")


# ---- zapamatování -----------------------------------------------------------------


def test_remember_writes_a_card_resource_with_tags():
    memory, fake = service()
    result = memory.remember("role-backend", "p1", "n1", "lesson", "CAS konflikt řeš revizí.")
    assert result["status"] == "configured"
    written = next(call for call in fake.calls if call[0] == "write")
    assert written[2].startswith("viking://user/role-backend/peers/p1/resources/cards/n1/lesson-")
    assert written[2].endswith(".md") and written[2] == result["uri"]
    assert set(written[4]) >= {"opora=1", "role=role-backend", "project=p1", "node=n1", "kind=lesson"}


def test_remember_without_a_project_writes_into_the_role_resources():
    memory, fake = service()
    result = memory.remember("role-backend", None, None, "note", "Poznámka.")
    assert result["uri"].startswith("viking://user/role-backend/resources/opora/note-")


def test_remember_refuses_an_unknown_kind_oversized_text_and_a_nul_byte():
    memory, _ = service()
    with pytest.raises(ValueError):
        memory.remember("role-backend", None, None, "rant", "x")
    with pytest.raises(ValueError):
        memory.remember("role-backend", None, None, "note", "x" * 12001)
    with pytest.raises(ValueError):
        memory.remember("role-backend", None, None, "note", "a\0b")


def test_remember_reports_unavailable_instead_of_raising():
    memory, _ = service(FakeOpenVikingClient(fail={"write"}))
    assert memory.remember("role-backend", None, None, "note", "x")["status"] == "unavailable"


# ---- půjčení ----------------------------------------------------------------------


def test_lend_reads_another_role_and_labels_every_item():
    fake = FakeOpenVikingClient(results={
        "viking://user/role-db/memories": [hit("viking://user/role-db/memories/index.md", 0.7)],
    })
    memory, _ = service(fake)
    result = memory.lend("role-db", "role-backend", "jak indexovat", 600)
    assert result["role"] == "role-backend" and result["fromRole"] == "role-db"
    assert [item["origin"] for item in result["items"]] == ["lent:role-db"]
    assert [call[1] for call in fake.calls if call[0] == "search"] == ["role-db"]


def test_lend_refuses_an_unknown_role_on_either_side():
    memory, _ = service()
    with pytest.raises(ValueError):
        memory.lend("role-nikdo", "role-backend", "x", 600)
    with pytest.raises(ValueError):
        memory.lend("role-db", "role-nikdo", "x", 600)


# ---- zrcadlení a uzavření karty ---------------------------------------------------


SECTIONS = {"frame": "Rámec", "log": "Postup", "failures": "", "fixes": "Oprava", "handoff": ""}


def test_mirror_workspace_writes_one_resource_per_non_empty_section():
    memory, fake = service()
    result = memory.mirror_workspace("role-backend", "p1", "n1", SECTIONS)
    assert result["status"] == "configured" and result["errors"] == []
    assert result["mirrored"] == [
        "viking://user/role-backend/peers/p1/resources/cards/n1/frame.md",
        "viking://user/role-backend/peers/p1/resources/cards/n1/log.md",
        "viking://user/role-backend/peers/p1/resources/cards/n1/fixes.md",
    ]
    assert len([call for call in fake.calls if call[0] == "write"]) == 3


def test_mirror_workspace_never_raises_and_reports_every_failure():
    memory, _ = service(FakeOpenVikingClient(fail={"write"}))
    result = memory.mirror_workspace("role-backend", "p1", "n1", SECTIONS)
    assert result["status"] == "unavailable" and result["mirrored"] == []
    assert [item["section"] for item in result["errors"]] == ["frame", "log", "fixes"]
    memory, _ = service(enabled=False)
    assert memory.mirror_workspace("role-backend", "p1", "n1", SECTIONS)["status"] == "disabled"
    memory, _ = service()
    assert memory.mirror_workspace("role-nikdo", "p1", "n1", SECTIONS)["status"] == "skipped"
    assert memory.mirror_workspace("role-backend", "p1", "n1", {})["mirrored"] == []


def test_commit_card_opens_a_session_sends_sections_and_returns_the_task():
    memory, fake = service()
    result = memory.commit_card("role-backend", "p1", "n1", SECTIONS)
    assert result == {"status": "configured", "taskId": "t-9"}
    assert ("session_create", "role-backend", "p1") in fake.calls
    assert len([call for call in fake.calls if call[0] == "session_add"]) == 3
    assert ("session_commit", "role-backend", "s-1") in fake.calls


def test_commit_card_never_raises_and_says_what_failed():
    memory, _ = service(FakeOpenVikingClient(fail={"session_commit"}))
    broken = memory.commit_card("role-backend", "p1", "n1", SECTIONS)
    assert broken["status"] == "unavailable" and broken["error"]
    memory, _ = service(enabled=False)
    assert memory.commit_card("role-backend", "p1", "n1", SECTIONS)["status"] == "disabled"
    memory, fake = service()
    assert memory.commit_card("role-backend", "p1", "n1", {})["status"] == "skipped"
    assert fake.calls == []


# ---- klíč na roli -------------------------------------------------------------------


def test_every_data_call_goes_out_with_the_key_of_its_own_role():
    fake = FakeOpenVikingClient(results={
        SELF_URI: [hit("viking://user/role-backend/memories/a.md", 0.9)],
        "viking://user/role-db/memories": [hit("viking://user/role-db/memories/i.md", 0.7)],
    })
    memory, _ = service(fake)
    memory.recall("role-backend", "p1", "n1", "co vím")
    memory.remember("role-backend", None, None, "note", "Poznámka.")
    memory.lend("role-db", "role-backend", "index", 600)
    memory.commit_card("role-frontend", "p1", "n1", SECTIONS)
    used = {call[0]: key for call, key in zip(fake.calls, fake.keys, strict=True)}
    assert used["search"] in {"key-role-backend", "key-role-db"}
    assert used["write"] == "key-role-backend"
    assert used["session_create"] == "key-role-frontend"
    assert ADMIN_KEY not in fake.keys, "správcovský klíč nesmí sahat na data role"
    lent = [key for call, key in zip(fake.calls, fake.keys, strict=True)
            if call[0] == "search" and call[1] == "role-db"]
    assert lent == ["key-role-db"], "půjčka čte cizí paměť klíčem té role, ne žadatele"


def test_a_role_without_a_key_is_unavailable_and_never_touches_the_network():
    memory, fake = service(keys={"role-db": "key-role-db"})
    recalled = memory.recall("role-backend", "p1", "n1", "x")
    assert recalled["status"] == "unavailable" and "provisioning" in recalled["reason"]
    assert memory.remember("role-backend", None, None, "note", "x")["status"] == "unavailable"
    mirrored = memory.mirror_workspace("role-backend", "p1", "n1", SECTIONS)
    assert mirrored["status"] == "unavailable" and mirrored["mirrored"] == []
    assert [item["section"] for item in mirrored["errors"]] == ["frame", "log", "fixes"]
    committed = memory.commit_card("role-backend", "p1", "n1", SECTIONS)
    assert committed["status"] == "unavailable" and "provisioning" in committed["error"]
    assert fake.calls == []


# ---- rozdání klíčů rolím ------------------------------------------------------------


def test_provision_roles_registers_every_role_and_stores_its_key():
    memory, fake = service(FakeOpenVikingClient(users=["admin"]), keys={})
    result = memory.provision_roles()
    assert result["status"] == "configured" and result["errors"] == []
    assert result["provisioned"] == list(roles.role_ids()) and result["reused"] == []
    assert result["account"] == "default"
    registered = [call[2] for call in fake.calls if call[0] == "admin_register_user"]
    assert registered == list(roles.role_ids())
    assert set(fake.keys) == {ADMIN_KEY}, "klíče rozdává jen správcovský klíč"
    assert memory.missing_roles() == []
    assert memory.status()["status"] == "configured"


def test_provision_roles_regenerates_the_key_of_a_user_that_already_exists():
    fake = FakeOpenVikingClient(users=["admin", "role-backend"])
    memory, _ = service(fake, keys={})
    result = memory.provision_roles()
    assert result["status"] == "configured" and "role-backend" in result["provisioned"]
    assert [call[2] for call in fake.calls if call[0] == "admin_regenerate_key"] == ["role-backend"]
    assert "role-backend" not in [call[2] for call in fake.calls if call[0] == "admin_register_user"]


def test_provision_roles_keeps_a_key_it_already_has():
    fake = FakeOpenVikingClient(users=["admin"])
    memory, _ = service(fake, keys={"role-backend": "key-role-backend"})
    result = memory.provision_roles()
    assert result["reused"] == ["role-backend"] and "role-backend" not in result["provisioned"]
    assert memory.settings.role_keys()["role-backend"] == "key-role-backend"
    assert "role-backend" not in [call[2] for call in fake.calls
                                  if call[0] in {"admin_register_user", "admin_regenerate_key"}]


def test_provision_roles_without_an_admin_key_says_so_and_asks_nothing():
    memory, fake = service(FakeOpenVikingClient(api_key=None), keys={})
    result = memory.provision_roles()
    assert result["status"] == "needs_admin_key" and result["provisioned"] == []
    assert "OPORA_OPENVIKING_ADMIN_API_KEY" in result["reason"]
    assert fake.calls == []


def test_provision_roles_reports_one_failing_role_without_losing_the_others():
    fake = FakeOpenVikingClient(users=["admin"], fail={"role-db"})
    memory, _ = service(fake, keys={})
    result = memory.provision_roles()
    assert result["status"] == "partial"
    assert [item["role"] for item in result["errors"]] == ["role-db"]
    assert "role-db" not in result["provisioned"] and "role-frontend" in result["provisioned"]
    assert memory.missing_roles() == ["role-db"]
    assert memory.status()["missingRoles"] == ["role-db"]


def test_provision_roles_is_disabled_or_unavailable_instead_of_raising():
    memory, fake = service(enabled=False, keys={})
    assert memory.provision_roles()["status"] == "disabled" and fake.calls == []
    memory, _ = service(FakeOpenVikingClient(fail={"admin_list_users"}), keys={})
    down = memory.provision_roles()
    assert down["status"] == "unavailable" and down["provisioned"] == [] and down["reason"]


def test_the_provisioning_result_never_carries_a_secret():
    memory, _ = service(FakeOpenVikingClient(users=["admin"]), keys={})
    result = memory.provision_roles()
    stored = memory.settings.role_keys()
    assert stored and all(value.startswith("new-") for value in stored.values())
    assert not any(value in repr(result) for value in stored.values())
    assert not any(value in repr(memory.status()) for value in stored.values())


def test_a_broken_client_factory_is_unavailable_not_a_crash():
    def broken():
        raise ValueError("Adresa OpenVikingu musí být http na loopbacku.")

    memory = MemoryService(broken, Toggle(True))
    assert memory.status()["status"] == "unavailable"
    assert memory.recall("role-backend", None, None, "x")["status"] == "unavailable"
    assert memory.mirror_workspace("role-backend", "p1", "n1", SECTIONS)["status"] == "unavailable"


# ---- nastavení pro celou aplikaci --------------------------------------------------


class FakeCanvas:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.commit()


def test_app_settings_persist_for_the_whole_application(tmp_path, monkeypatch):
    monkeypatch.delenv("OPORA_OPENVIKING_ENABLED", raising=False)
    canvas = FakeCanvas(tmp_path / "registry.sqlite")
    settings = AppSettings(canvas)
    assert settings.enabled() is False
    assert settings.set_enabled(True) is True
    assert AppSettings(canvas).enabled() is True
    assert settings.set_enabled(False) is False
    assert AppSettings(canvas).enabled() is False


def test_app_settings_default_comes_from_the_environment(tmp_path, monkeypatch):
    canvas = FakeCanvas(tmp_path / "registry.sqlite")
    monkeypatch.setenv("OPORA_OPENVIKING_ENABLED", "1")
    assert AppSettings(canvas).enabled() is True
    monkeypatch.setenv("OPORA_OPENVIKING_ENABLED", "off")
    assert AppSettings(canvas).enabled() is False
    monkeypatch.setenv("OPORA_OPENVIKING_ENABLED", "true")
    settings = AppSettings(canvas)
    settings.set_enabled(False)
    assert settings.enabled() is False, "uložená volba přebíjí výchozí hodnotu z prostředí"


def test_app_settings_refuse_a_non_boolean(tmp_path):
    settings = AppSettings(FakeCanvas(tmp_path / "registry.sqlite"))
    with pytest.raises(ValueError):
        settings.set_enabled("ano")


def test_role_keys_persist_in_the_application_settings(tmp_path):
    canvas = FakeCanvas(tmp_path / "registry.sqlite")
    settings = AppSettings(canvas)
    assert settings.role_keys() == {}
    assert settings.set_role_keys({"role-backend": "ov-1", "role-db": "ov-2"}) == ["role-backend", "role-db"]
    assert AppSettings(canvas).role_keys() == {"role-backend": "ov-1", "role-db": "ov-2"}
    stored = canvas.db.execute(
        "SELECT value FROM app_settings WHERE key='openviking.roleKeys'").fetchone()[0]
    assert "ov-1" in stored, "klíč žije jen v úložišti aplikace, ne v odpovědi"


def test_role_keys_refuse_a_broken_shape_and_survive_a_broken_row(tmp_path):
    canvas = FakeCanvas(tmp_path / "registry.sqlite")
    settings = AppSettings(canvas)
    for broken in ("ne objekt", {"role-backend": ""}, {"role backend": "ov-1"}, {"role-backend": 1}):
        with pytest.raises(ValueError):
            settings.set_role_keys(broken)
    canvas.db.execute("INSERT OR REPLACE INTO app_settings VALUES('openviking.roleKeys','{nejde')")
    canvas.db.commit()
    assert settings.role_keys() == {}


def test_typesafe_key_lives_in_application_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    canvas = FakeCanvas(tmp_path / "registry.sqlite")
    settings = AppSettings(canvas)
    assert settings.typesafe_key() is None
    monkeypatch.setenv("TYPESAFE_API_KEY", "env-key")
    assert settings.typesafe_key() == "env-key"
    assert settings.set_typesafe_key(" ts-1 ") is True
    assert AppSettings(canvas).typesafe_key() == "ts-1", "uložený klíč přebíjí prostředí"
    with pytest.raises(ValueError):
        settings.set_typesafe_key("a b")
    monkeypatch.delenv("TYPESAFE_API_KEY")
    assert settings.set_typesafe_key(None) is False
    assert settings.typesafe_key() is None
