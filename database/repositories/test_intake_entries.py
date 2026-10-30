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


def test_unclassified_prefers_batch_entries_and_skips_decided_asked_and_old_ones():
    entries = store()
    entries.insert(entry("ie_old", "a", "2026-10-29T10:00:00Z"))
    for number in range(1, 5):
        entries.insert(entry(f"ie_{number}", "a", f"2026-10-30T10:0{number}:00Z"))
    entries.insert(entry("ie_dup", "a", "2026-10-30T10:09:00Z", verdict="duplicate"))
    assert entries.set_verdict("ie_4", verdict="done", layer="heart", reason="srdce")
    assert entries.set_verdict("ie_3", verdict="pending", layer="jev", reason="nejistý", confidence=0.4, jev_calls=1)
    assert [row["id"] for row in entries.unclassified("w", 5, "2026-10-30")] == ["ie_2", "ie_1"]
    assert [row["id"] for row in entries.unclassified("w", 1, "2026-10-30", ["ie_1"])] == ["ie_1"]
    assert entries.unclassified("w", 0, "2026-10-30") == []
    assert entries.jev_calls_on("2026-10-30") == 1 and entries.jev_calls_on("2026-10-29") == 0


def test_set_verdict_only_pending_does_not_overwrite_the_heart_and_keeps_the_sentence():
    entries = store()
    entries.insert(entry("ie_1", "věta", "t1"))
    assert entries.set_verdict("ie_1", verdict="fix_for_milestone", layer="heart", reason="srdce")
    assert not entries.set_verdict("ie_1", verdict="done", layer="jev", reason="x", jev_calls=1, only_pending=True)
    stored = entries.get("ie_1")
    assert (stored["verdict"], stored["layer"], stored["text"], stored["jevCalls"]) == (
        "fix_for_milestone", "heart", "věta", 0)
    assert entries.recent("w", 5, layers=("determinism", "jev")) == []
