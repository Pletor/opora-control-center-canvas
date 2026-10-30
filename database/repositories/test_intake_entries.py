"""Repozitář vstupů brány: vložení s řádkem FTS5, hledání podle zdroje a otisku, bm25 bez sebe a novějších,
izolace pracovních prostorů a počty stanovisek."""
import sqlite3

from database.repositories.intake_entries import IntakeEntries
from database.schema.intake_schema import SCHEMA


def store():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    return IntakeEntries(db)


def entry(entry_id, text, at, workspace="w", verdict="pending", fingerprint=None, ref=None):
    return {"id": entry_id, "workspaceId": workspace, "source": "gate_ask", "sourceRef": ref, "text": text,
            "fingerprint": fingerprint or entry_id, "createdAt": at, "verdict": verdict, "layer": "determinism",
            "jevCalls": 0}


def test_insert_get_by_source_and_first_with_fingerprint():
    entries = store()
    entries.insert(entry("ie_1", "první", "t1", fingerprint="f", ref="gt_1"))
    entries.insert(entry("ie_2", "první", "t2", fingerprint="f", verdict="duplicate"))
    assert entries.get("ie_1")["sourceRef"] == "gt_1" and entries.by_source("gate_ask", "gt_1")["id"] == "ie_1"
    assert entries.first_with("w", "f")["id"] == "ie_1" and entries.first_with("jiny", "f") is None
    assert entries.counts("w") == {"pending": 1, "duplicate": 1}
    assert [item["id"] for item in entries.recent("w", 5, ("duplicate",))] == ["ie_2"]


def test_similar_excludes_itself_later_entries_and_other_workspaces():
    entries = store()
    entries.insert(entry("ie_1", "vyhledavani dokumentu", "t1"))
    entries.insert(entry("ie_2", "vyhledavani dokumentu", "t2", workspace="jiny"))
    entries.insert(entry("ie_3", "vyhledavani", "t3"))
    entries.insert(entry("ie_4", "vyhledavani dokumentu znovu", "t4"))
    assert entries.similar("w", '"vyhledavani" OR "dokumentu"', "ie_3", "t3") == ["ie_1"]
    assert entries.similar("w", '"vyhledavani" OR "dokumentu"', "ie_4", "t4", limit=1) == ["ie_1"]
