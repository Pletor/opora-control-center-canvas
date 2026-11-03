"""Registr Brainu: ID a pin artefaktu, právě jedna aktivní verze, vazby a výpis s verzemi."""
import sqlite3

import pytest

from backend.brain import registry
from database.schema.project_schema import REGISTRY_SCHEMA

SHA1, SHA2 = "a" * 40, "b" * 40


def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(REGISTRY_SCHEMA)
    return connection


def test_ids_and_pins():
    assert registry.artifact_id("skill", "heart") == "opora:brain:skill:heart"
    assert registry.pin("opora:brain:skill:heart", SHA1) == "opora:brain:skill:heart@aaaaaaaaaaaa"
    with pytest.raises(ValueError):
        registry.artifact_id("prompt", "x")


def test_exactly_one_active_version():
    conn = db()
    aid = registry.ensure_artifact(conn, "skill", "opora-heart", "heart")
    assert registry.ensure_artifact(conn, "skill", "opora-heart", "heart") == aid
    assert registry.active(conn, aid) is None
    first = registry.add_version(conn, aid, SHA1, "skills/heart/SKILL.md")
    assert registry.add_version(conn, aid, SHA1, "skills/heart/SKILL.md") == first  # stejné SHA = stejná verze
    registry.activate(conn, first)
    second = registry.add_version(conn, aid, SHA2, "skills/heart/SKILL.md", baseline_version_id=first)
    assert registry.active(conn, aid)["version"] == SHA1  # kandidát aktivní verzi nemění
    registry.activate(conn, second)
    active = registry.active(conn, aid)
    assert active == {"artifact_id": aid, "plugin": "opora-heart", "name": "heart", "version": SHA2,
                      "content_ref": "skills/heart/SKILL.md", "pin": "opora:brain:skill:heart@bbbbbbbbbbbb"}
    statuses = dict(conn.execute("SELECT version, status FROM brain_artifact_versions").fetchall())
    assert statuses == {SHA1: "retired", SHA2: "active"}
    with pytest.raises(sqlite3.IntegrityError):  # druhou aktivní verzi nepustí ani schéma
        conn.execute("UPDATE brain_artifact_versions SET status='active' WHERE id=?", (first,))


def test_list_and_detail_with_links():
    conn = db()
    aid = registry.ensure_artifact(conn, "skill", "ponytail", "ponytail", ["web"])
    vid = registry.add_version(conn, aid, SHA1, "skills/ponytail/SKILL.md")
    registry.activate(conn, vid)
    registry.link(conn, vid, "eval_run", "ev_1")
    with pytest.raises(ValueError):
        registry.link(conn, vid, "jinde", "x")
    [listed] = registry.list_artifacts(conn)
    assert listed["id"] == aid and listed["project_types"] == ["web"]
    assert listed["active"]["pin"] == "opora:brain:skill:ponytail@aaaaaaaaaaaa" and listed["active"]["status"] == "active"
    detail = registry.get_artifact(conn, aid)
    assert [link["target_ref"] for link in detail["versions"][0]["links"]] == ["ev_1"]
    assert registry.get_artifact(conn, "opora:brain:skill:nic") is None
