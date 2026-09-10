"""Archivované projekty se skryjí v UI, ale záloha je musí zachovat."""
import sqlite3

from scripts import production_snapshot


def test_visible_project_ids_match_bootstrap_without_deleting_archives():
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE projects(id TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE archived_projects(project_id TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO projects VALUES (?)", [("active",), ("archived",)])
        db.execute("INSERT INTO archived_projects VALUES ('archived')")
        before = production_snapshot.snapshot(db)
        assert production_snapshot.visible_project_ids(db) == ["active"]
        assert production_snapshot.snapshot(db) == before
        assert before["projects"]["rows"] == 2
        assert before["archived_projects"]["rows"] == 1


def test_visible_project_ids_are_sorted_when_no_projects_are_archived():
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE projects(id TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE archived_projects(project_id TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO projects VALUES (?)", [("z",), ("a",)])
        assert production_snapshot.visible_project_ids(db) == ["a", "z"]
