"""Dry run never writes; --write appends exactly one truthful generation and restores the pin."""
import sqlite3

from database.repositories.opora_context_events import enroll
from database.schema.project_initialization import initialize_project_schema
from tools.schema_adopt import main


def test_dry_run_then_write(tmp_path, capsys):
    path = tmp_path / "project.sqlite"
    db = sqlite3.connect(path)
    initialize_project_schema(db)
    db.execute("BEGIN IMMEDIATE")
    enroll(db, "p")
    db.commit()
    pin = db.execute("SELECT schema_version FROM opora_context_coverage").fetchone()[0]
    db.execute("CREATE TABLE foreign_table(x)")
    now = db.execute("PRAGMA schema_version").fetchone()[0]
    rows = db.execute("SELECT count(*) FROM opora_schema_generations").fetchone()[0]
    db.close()
    assert main(["--db", str(path)]) == 1
    status = capsys.readouterr().out
    assert f"pin na verzi {pin}" in status and f"nedosvědčený článek {pin}→{pin + 1}" in status
    assert f"--from {pin} --to {now}" in status and "initialize_project_schema: PROJECT_SCHEMA" in status
    args = ["--db", str(path), "--from", str(pin), "--to", str(now), "--author", "tester", "--reason", "reviewed"]
    assert main(["--db", str(path), "--from", str(pin), "--to", str(now), "--author", " ", "--reason", "x"]) == 2
    assert main(["--db", str(path), "--from", str(pin), "--to", str(now + 1), "--author", "t", "--reason", "r"]) == 2
    assert main(args) == 0
    assert "pokrytí projektu p: checkpoint projde" in capsys.readouterr().out
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM opora_schema_generations").fetchone()[0] == rows
    db.close()
    assert main([*args, "--write"]) == 0
    db = sqlite3.connect(path)
    assert db.execute("SELECT author,reason FROM opora_schema_generations WHERE from_version=?", (pin,)).fetchone() == ("tester", "reviewed")
    db.close()
    assert main([*args, "--write"]) == 2
