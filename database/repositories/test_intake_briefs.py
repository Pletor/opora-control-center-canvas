"""Repozitář spisů výslechu: uložení a přepis, JSON sloupce, výpis prostoru a vstupy požadavku."""
import sqlite3

from database.repositories.intake_briefs import IntakeBriefs
from database.repositories.intake_entries import IntakeEntries
from database.schema.intake_schema import SCHEMA


def store():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    return db


def test_save_reads_json_back_and_overwrites_the_same_requirement():
    briefs = IntakeBriefs(store())
    briefs.save({"requirementId": "rq_1", "workspaceId": "w", "status": "draft",
                 "situation": {"requirement": {"id": "rq_1"}}, "updatedAt": "t1"})
    first = briefs.get("rq_1")
    assert (first["status"], first["situation"], first["synthesis"], first["questions"], first["rounds"]) == (
        "draft", {"requirement": {"id": "rq_1"}}, None, [], 0)
    briefs.save({**first, "status": "grilling", "synthesis": {"goal": "Cíl"}, "rounds": 1,
                 "questions": [{"id": "q1", "text": "Kdo?", "answer": None}], "updatedAt": "t2"})
    second = briefs.get("rq_1")
    assert (second["status"], second["synthesis"], second["questions"][0]["id"], second["rounds"]) == (
        "grilling", {"goal": "Cíl"}, "q1", 1)
    briefs.save({"requirementId": "rq_2", "workspaceId": "jiny", "status": "draft", "updatedAt": "t3"})
    assert list(briefs.of_workspace("w")) == ["rq_1"] and briefs.get("rq_x") is None


def test_status_outside_the_four_states_is_refused():
    briefs = IntakeBriefs(store())
    try:
        briefs.save({"requirementId": "rq_1", "workspaceId": "w", "status": "done", "updatedAt": "t"})
    except sqlite3.IntegrityError:
        return
    raise AssertionError("CHECK stavu chybí")


def test_entries_of_lists_linked_entries_from_the_oldest():
    db = store()
    entries = IntakeEntries(db)
    for number, verdict in ((1, "fix_for_milestone"), (2, "changes_intent")):
        entries.insert({"id": f"ie_{number}", "workspaceId": "w", "source": "heart_message", "text": f"věta {number}",
                        "fingerprint": str(number), "createdAt": f"t{number}", "verdict": verdict,
                        "layer": "heart", "jevCalls": 0})
        entries.set_requirement(f"ie_{number}", "rq_1")
    assert [(item["id"], item["verdict"]) for item in IntakeBriefs(db).entries_of("rq_1")] == [
        ("ie_1", "fix_for_milestone"), ("ie_2", "changes_intent")]
    assert IntakeBriefs(db).entries_of("rq_x") == []
