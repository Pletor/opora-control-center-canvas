"""Deník chyb: zápis, deduplikace otiskem, znovuotevření, redakce, zkrácení, odolnost a retence."""
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from backend.app import errors
from database.schema.project_schema import REGISTRY_SCHEMA


@pytest.fixture
def registry(tmp_path):
    path = tmp_path / "registry.sqlite"
    db = sqlite3.connect(path)
    db.executescript(REGISTRY_SCHEMA)
    db.execute("PRAGMA journal_mode=WAL")
    db.close()
    errors.configure(tmp_path)
    yield path
    errors.configure(None)


def rows(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in db.execute("SELECT * FROM opora_errors ORDER BY id")]
    finally:
        db.close()


def test_same_error_counts_and_reopens(registry):
    for n in (1, 2, 3):
        errors.record("flow", "exception", f"Uzel {n} spadl na běhu 3f2a9c81d0", project="p", subject="run")
    [row] = rows(registry)
    assert row["count"] == 3 and row["resolved_at"] is None and row["message"] == "Uzel 3 spadl na běhu 3f2a9c81d0"
    assert errors.resolve(row["fingerprint"]) == 1 and rows(registry)[0]["resolved_at"]
    errors.record("flow", "exception", "Uzel 9 spadl na běhu 77aa00bb11", project="p", subject="run")
    [row] = rows(registry)
    assert row["count"] == 4 and row["resolved_at"] is None


def test_fingerprint_ignores_numbers_hex_and_uuid():
    a = errors.fingerprint("heart", "timeout", "dávka 12 b1c2d3e4-0000-4000-8000-123456789abc po 60 s")
    b = errors.fingerprint("heart", "timeout", "dávka 7 00000000-1111-4222-8333-444444444444 po 61 s")
    assert a == b and a != errors.fingerprint("heart", "timeout", "jiná zpráva")


def test_redaction_and_truncation(registry):
    errors.record("server", "log", "token=abc " + "x" * 400, cause="y" * 3000 + "\nAuthorization: Bearer tajne",
                  data={"blob": "z" * 5000}, lever="Velín → Srdce", actor=("agent", "dev"))
    [row] = rows(registry)
    assert row["message"].startswith("token=***") and len(row["message"]) == errors.MESSAGE
    assert row["cause"].endswith("Authorization: ***") and len(row["cause"]) == errors.CAUSE
    assert len(row["data"]) <= errors.DATA and "truncated" in json.loads(row["data"])
    assert (row["actor_kind"], row["actor_name"], row["lever"]) == ("agent", "dev", "Velín → Srdce")


def test_unconfigured_missing_or_locked_never_raises(registry, tmp_path):
    errors.configure(None)
    errors.record("server", "log", "nic")
    errors.configure(tmp_path / "nikde")
    errors.record("server", "log", "nic")
    assert not (tmp_path / "nikde" / "registry.sqlite").exists()
    errors.configure(tmp_path)
    holder = sqlite3.connect(registry, timeout=0)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        errors.record("server", "log", "zamčeno")  # čeká nejvýš timeout a tiše se vzdá
    finally:
        holder.rollback()
        holder.close()
    assert rows(registry) == []


def test_read_text_counts_and_prune(registry):
    errors.record("heart", "timeout", "brief vypršel", project="p", severity="critical", lever="průhled srdce")
    errors.record("flow", "log", "pomalé", project="p", severity="warn")
    errors.record("card", "refusal", "jiný projekt", project="q")
    assert [r["kind"] for r in errors.read(project="p")] == ["timeout", "log"]
    assert errors.counts("p") == {"open": 2, "heart": 1}
    first = errors.text(errors.read(project="p")).splitlines()[0]
    assert first.startswith("[critical] heart/timeout · p · 1× od ") and first.endswith("→ průhled srdce")
    errors.resolve(source="card")
    db = sqlite3.connect(registry)
    db.execute("UPDATE opora_errors SET resolved_at='2000-01-01T00:00:00+00:00' WHERE source='card'")
    db.commit()
    db.close()
    errors.prune(datetime.now(UTC) + timedelta(days=1))
    assert {r["source"] for r in rows(registry)} == {"heart", "flow"}
