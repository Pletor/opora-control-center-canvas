"""Repozitář požadavků brány: vložení, výpis podle stavu, odložené podle podmínky a izolace prostorů."""
import sqlite3

from database.repositories.intake_entries import IntakeEntries
from database.repositories.intake_requirements import IntakeRequirements
from database.schema.intake_schema import SCHEMA


def store():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    return db


def requirement(rq, status="open", condition=None, workspace="w", at="t1"):
    return {"id": rq, "workspaceId": workspace, "areaId": "a1", "milestoneId": None, "title": rq, "status": status,
            "openCondition": condition, "createdAt": at}


def test_list_filters_status_and_deferred_until_matches_the_condition():
    requirements = IntakeRequirements(store())
    requirements.insert(requirement("rq_1"))
    requirements.insert(requirement("rq_2", "deferred", "ms_1", at="t2"))
    requirements.insert(requirement("rq_3", "deferred", "ms_2", at="t3"))
    requirements.insert(requirement("rq_4", "deferred", "ms_1", workspace="jiny"))
    assert requirements.get("rq_2")["openCondition"] == "ms_1" and requirements.get("rq_x") is None
    assert [item["id"] for item in requirements.list("w")] == ["rq_1", "rq_2", "rq_3"]
    assert [item["id"] for item in requirements.list("w", ("deferred",))] == ["rq_2", "rq_3"]
    assert [item["id"] for item in requirements.deferred_until("w", "ms_1")] == ["rq_2"]


def test_entry_is_linked_to_a_requirement_and_keeps_its_milestone_when_none_given():
    db = store()
    entries = IntakeEntries(db)
    entries.insert({"id": "ie_1", "workspaceId": "w", "source": "gate_ask", "text": "věta", "fingerprint": "f",
                    "createdAt": "t1", "verdict": "pending", "layer": "determinism", "milestoneId": "ms_1",
                    "jevCalls": 0})
    assert entries.set_requirement("ie_1", "rq_1")
    assert (entries.get("ie_1")["requirementId"], entries.get("ie_1")["milestoneId"]) == ("rq_1", "ms_1")
    assert entries.set_requirement("ie_1", "rq_2", "ms_2") and entries.get("ie_1")["milestoneId"] == "ms_2"
    assert not entries.set_requirement("ie_x", "rq_1")
