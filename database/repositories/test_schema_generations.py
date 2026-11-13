"""Recorded application generations keep pins valid; foreign DDL and rewrites stay refused."""
import sqlite3

import pytest

from database.repositories import opora_context_bindings as bindings
from database.repositories.opora_context_events import checkpoint, enroll
from database.repositories.opora_context_events import install as install_events
from database.repositories.opora_context_events_sources import digest, schema_digest
from database.repositories.opora_context_events_triggers import verify_triggers
from database.repositories.schema_generations import TABLE, adopt, chain, gap, witness
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_SCHEMA, REGISTRY_SCHEMA


def version(db):
    return db.execute("PRAGMA schema_version").fetchone()[0]


@pytest.fixture
def project(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    initialize_project_schema(db)
    db.execute("BEGIN IMMEDIATE")
    enroll(db, "p")
    db.commit()
    yield db
    db.close()


@pytest.fixture
def registry(tmp_path):
    db = sqlite3.connect(tmp_path / "registry.sqlite")
    witness(db, "registry", lambda: (db.executescript(REGISTRY_SCHEMA), bindings.install(db)))
    db.execute("INSERT INTO builtin_project_metadata VALUES('draft','Draft')")
    db.commit()
    db.execute("BEGIN")
    bindings.enroll(db, "draft", "draft")
    db.commit()
    yield db
    db.close()


def test_first_install_records_itself_and_reopen_adds_nothing(project):
    assert chain(project, 0) is not None
    rows = project.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    initialize_project_schema(project)
    assert project.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == rows
    assert project.in_transaction is False


def test_witnessed_schema_addition_keeps_pin(project):
    witness(project, "new index", lambda: project.execute("CREATE INDEX extra_index ON opora_context_events(bytes)"))
    assert checkpoint(project, "p")["sequence"] == 0


def test_foreign_ddl_breaks_pin_with_readable_reason(project):
    pin = project.execute("SELECT schema_version FROM opora_context_coverage").fetchone()[0]
    project.execute("CREATE INDEX extra_index ON opora_context_events(bytes)")
    with pytest.raises(ValueError, match="SQL context schema generation changed.") as error:
        checkpoint(project, "p")
    message = str(error.value)
    assert f"verzi schématu {pin}" in message and f"chybí článek {pin} -> ?" in message
    assert f"--from {pin} --to {version(project)}" in message and "tools/schema_adopt.py" in message


def test_foreign_trigger_recreate_breaks_pin(project):
    sql = project.execute("SELECT sql FROM sqlite_master WHERE name='opora_context_event_counter'").fetchone()[0]
    project.execute("DROP TRIGGER opora_context_event_counter")
    project.execute(sql)
    with pytest.raises(ValueError, match="SQL context schema generation changed."):
        checkpoint(project, "p")


def test_generation_table_is_outside_fingerprints(tmp_path):
    project = sqlite3.connect(tmp_path / "plain.sqlite")
    project.executescript(PROJECT_SCHEMA)
    install_events(project)
    before = schema_digest(project), digest(verify_triggers(project))
    witness(project, "generation table", lambda: None)
    assert (schema_digest(project), digest(verify_triggers(project))) == before
    registry = sqlite3.connect(tmp_path / "registry.sqlite")
    registry.executescript(REGISTRY_SCHEMA)
    bindings.install(registry)
    before = bindings._schema(registry), bindings._digest(bindings.verify(registry))
    witness(registry, "generation table", lambda: None)
    assert (bindings._schema(registry), bindings._digest(bindings.verify(registry))) == before


def test_adopted_gap_restores_pin_but_never_rewrites(project):
    pin = project.execute("SELECT schema_version FROM opora_context_coverage").fetchone()[0]
    project.execute("CREATE TABLE foreign_table(x)")
    adopt(project, pin, version(project), "tester", "foreign table reviewed")
    project.commit()
    assert checkpoint(project, "p")["sequence"] == 0
    with pytest.raises(ValueError, match="already recorded"):
        adopt(project, pin, version(project) + 1, "tester", "again")
    with pytest.raises(ValueError, match="author"):
        adopt(project, version(project), version(project) + 1, " ", "no author")
    for statement in (f"UPDATE {TABLE} SET to_version=to_version+1",
                      f"DELETE FROM {TABLE}",
                      f"INSERT OR REPLACE INTO {TABLE} VALUES({pin},{pin + 1},'x','y','z')"):
        with pytest.raises(sqlite3.IntegrityError, match="Permanent schema generation"):
            project.execute(statement)


def test_registry_binding_witness_adopt_and_foreign(registry):
    witness(registry, "new index", lambda: registry.execute("CREATE INDEX extra_index ON jobs(kind)"))
    assert bindings.checkpoint(registry, "draft", "draft")["generation"] == 0
    start = version(registry)
    registry.execute("CREATE TABLE foreign_table(x)")
    registry.commit()
    with pytest.raises(ValueError, match="Registry source binding coverage unavailable."):
        bindings.checkpoint(registry, "draft", "draft")
    adopt(registry, start, version(registry), "tester", "foreign table reviewed")
    registry.commit()
    assert bindings.checkpoint(registry, "draft", "draft")["generation"] == 0


@pytest.fixture
def journal(monkeypatch):
    from backend.app import error_log
    from database.repositories import schema_generations

    monkeypatch.setattr(schema_generations, "_BROKEN", set())  # pin z jiného testu nesmí nic uzavírat
    calls = {"records": [], "resolved": []}
    monkeypatch.setattr(error_log, "submit", lambda source, kind, message, **kw: calls["records"].append(
        (source, kind, kw)))
    monkeypatch.setattr(error_log, "resolve", lambda **kw: calls["resolved"].append(kw))
    return calls


def test_broken_pin_is_integrity_with_adopt_command_and_resolves_once_it_passes(project, journal):
    pin = project.execute("SELECT schema_version FROM opora_context_coverage").fetchone()[0]
    checkpoint(project, "p")
    assert journal["resolved"] == []  # bez dřívějšího záznamu se nic neuzavírá
    project.execute("CREATE TABLE foreign_table(x)")
    for _ in range(2):  # druhé čtení rozbitého pinu nový záznam nedá
        with pytest.raises(ValueError):
            checkpoint(project, "p")
    [(source, kind, kw)] = journal["records"]
    assert (source, kind, kw["project"], kw["subject"]) == ("integrity", "integrity", "p", "sql-context")
    assert kw["lever"].startswith("python tools/schema_adopt.py") and f"--from {pin}" in kw["lever"]
    adopt(project, pin, version(project), "tester", "foreign table reviewed")
    project.commit()
    checkpoint(project, "p")
    assert journal["resolved"] == [{"source": "integrity", "project": "p", "subject": "sql-context"}]


def test_broken_registry_binding_pin_is_integrity(registry, journal):
    registry.execute("CREATE TABLE foreign_table(x)")
    registry.commit()
    with pytest.raises(ValueError):
        bindings.checkpoint(registry, "draft", "draft")
    [(source, kind, kw)] = journal["records"]
    assert (source, kind, kw["project"], kw["subject"]) == ("integrity", "integrity", "draft",
                                                            "registry-binding/draft")
    assert "schema_adopt.py" in kw["lever"]


def test_without_generation_table_pin_must_equal_pragma(tmp_path):
    db = sqlite3.connect(tmp_path / "old.sqlite")
    db.executescript(PROJECT_SCHEMA)
    install_events(db)
    db.execute("BEGIN IMMEDIATE")
    enroll(db, "p")
    db.commit()
    assert checkpoint(db, "p")["sequence"] == 0
    db.execute("CREATE TABLE foreign_table(x)")
    with pytest.raises(ValueError, match="SQL context schema generation changed."):
        checkpoint(db, "p")


def test_old_enrolled_project_upgrades_through_witness(tmp_path):
    db = sqlite3.connect(tmp_path / "old.sqlite")
    db.executescript(PROJECT_SCHEMA)
    install_events(db)
    db.execute("BEGIN IMMEDIATE")
    enroll(db, "p")
    db.commit()
    initialize_project_schema(db)
    assert checkpoint(db, "p")["sequence"] == 0
    witness(db, "new index", lambda: db.execute("CREATE INDEX extra_index ON opora_context_events(bytes)"))
    assert checkpoint(db, "p")["sequence"] == 0


def test_old_enrolled_registry_upgrades_through_witness(tmp_path):
    db = sqlite3.connect(tmp_path / "old-registry.sqlite")
    db.executescript(REGISTRY_SCHEMA)
    bindings.install(db)
    db.execute("INSERT INTO builtin_project_metadata VALUES('draft','Draft')")
    db.commit()
    db.execute("BEGIN")
    bindings.enroll(db, "draft", "draft")
    db.commit()
    witness(db, "registry schema", lambda: (db.executescript(REGISTRY_SCHEMA), bindings.install(db)))
    witness(db, "new index", lambda: db.execute("CREATE INDEX extra_index ON jobs(kind)"))
    assert bindings.checkpoint(db, "draft", "draft")["generation"] == 0


def test_gap_ends_where_the_app_witnessed_chain_starts():
    db = sqlite3.connect(":memory:")
    witness(db, "base", lambda: db.execute("CREATE TABLE a(x)"))
    pin = db.execute("PRAGMA schema_version").fetchone()[0]
    db.execute("CREATE INDEX foreign_ddl ON a(x)")  # cizí DDL: mezera
    witness(db, "app", lambda: db.execute("CREATE TABLE b(x)"))
    now = db.execute("PRAGMA schema_version").fetchone()[0]
    start, until = gap(db, pin)
    assert start == pin and pin < until < now  # uznat jen cizí krok, ne dosvědčený
    adopt(db, start, until, "test", "cizí index")
    assert gap(db, pin) is None and chain(db, pin) is not None
