"""Registr pojistek: výchozí režim, přednost projektu, mezipaměť, tři režimy `check` a zápis do deníku."""
import sqlite3

import pytest

from backend.app import error_log, errors, guards
from database.schema.project_schema import REGISTRY_SCHEMA

HUMAN = ("human", None)


@pytest.fixture
def registry(tmp_path):
    db = sqlite3.connect(tmp_path / "registry.sqlite")
    db.executescript(REGISTRY_SCHEMA)
    db.close()
    errors.configure(tmp_path)
    guards.configure(tmp_path)
    yield tmp_path
    error_log.drain()
    guards.configure(None)
    errors.configure(None)


def journal():
    error_log.drain()
    return {(r["kind"], r["severity"], r["message"]): r for r in errors.read()}


def test_default_mode_without_registry_or_rows(registry):
    guards.configure(None)
    assert guards.mode("content_manifest", "p") == "enforce"
    guards.configure(registry)
    assert {row["id"]: row["mode"] for row in guards.read()}["budget"] == "enforce"
    assert all(row["origin"] == "default" for row in guards.read("p"))


def test_project_overrides_app_and_cache_is_invalidated(registry):
    assert guards.mode("content_manifest", "p") == "enforce"
    guards.set_mode("content_manifest", "", "warn", HUMAN, "celá aplikace")
    assert guards.mode("content_manifest", "p") == "warn" and guards.mode("content_manifest") == "warn"
    guards.set_mode("content_manifest", "p", "off", ("agent", "dev"), "jen projekt p")
    assert guards.mode("content_manifest", "p") == "off" and guards.mode("content_manifest", "q") == "warn"
    row = sqlite3.connect(registry / "registry.sqlite").execute(
        "SELECT scope, changed_by, reason FROM opora_guards WHERE project='p'").fetchone()
    assert row == ("project", "agent:dev", "jen projekt p")
    assert [r["origin"] for r in guards.read("p") if r["id"] == "content_manifest"] == ["project"]
    assert any(kind == "guard" and "content_manifest → off" in message for kind, _, message in journal())


def test_mode_reads_registry_once(registry, monkeypatch):
    guards.mode("budget", "p")
    monkeypatch.setattr(guards.sqlite3, "connect", lambda *a, **k: pytest.fail("mode nesmí znovu číst registry"))
    assert guards.mode("budget", "p") == guards.mode("confirmed_reopen", "q") == "enforce"


def test_check_in_three_modes(registry):
    assert guards.check("content_manifest", "p", blocked=False, message="nic") is False
    assert guards.check("content_manifest", "p", blocked=True, message="obsah se liší", subject="card") is True
    guards.set_mode("content_manifest", "p", "warn", HUMAN, "zkouška")
    assert guards.check("content_manifest", "p", blocked=True, message="obsah se liší", subject="card") is False
    guards.set_mode("content_manifest", "p", "off", HUMAN, "zkouška")
    assert guards.check("content_manifest", "p", blocked=True, message="vypnuto mlčí", subject="card") is False
    found = journal()
    blocked = found[("blocked", "warn", "obsah se liší")]
    assert blocked["project"] == "p" and blocked["subject"] == "card" and blocked["lever"] and blocked["source"] == "card"
    assert ("blocked", "warn", "pojistka content_manifest ve warn: by blokovala: obsah se liší") in found
    assert not any("vypnuto mlčí" in message for _, _, message in found)


def test_set_mode_refuses_invalid_and_linked(registry):
    with pytest.raises(ValueError, match="enforce, warn nebo off"):
        guards.set_mode("budget", "", "loud", HUMAN, "")
    with pytest.raises(ValueError, match="heart/caps"):
        guards.set_mode("heart_hour_cap", "", "off", HUMAN, "")
    with pytest.raises(ValueError, match="není napojená"):
        guards.set_mode("sql_context_pin", "", "off", HUMAN, "")
    with pytest.raises(ValueError, match="nejde"):
        guards.set_mode("neznama", "", "off", HUMAN, "")
    assert not guards.CATALOG["budget"]["agent_may_toggle"] and not guards.CATALOG["sql_context_pin"]["agent_may_toggle"]
