"""Repozitář milníků: kritéria jako JSON, aktivace nahradí aktivní milník oblasti, zamítnutí jen návrhu,
a značky spouštěčů „už jsem budil“."""
import sqlite3

from database.repositories.heart_triggers import HeartTriggers
from database.repositories.intake_milestones import IntakeMilestones
from database.schema.intake_schema import SCHEMA

CRITERIA = [{"id": "c1", "text": "Hledání vrací jen dokumenty organizace", "cards": ["n1", "n2"]}]


def store():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    return db


def milestone(ms, area="a1", at="t1", workspace="w"):
    return {"id": ms, "workspaceId": workspace, "areaId": area, "title": ms, "criteria": CRITERIA,
            "status": "proposed", "createdAt": at}


def test_activation_supersedes_the_active_milestone_of_the_area_and_keeps_history():
    milestones = IntakeMilestones(store())
    for row in (milestone("ms_1"), milestone("ms_2", at="t2"), milestone("ms_3", area="a2", at="t3")):
        milestones.insert(row)
    assert milestones.get("ms_1")["criteria"] == CRITERIA
    assert milestones.activate("ms_1") == (True, None)
    assert milestones.activate("ms_3") == (True, None)  # jiná oblast se nedotkne
    assert milestones.activate("ms_2") == (True, "ms_1")
    assert milestones.active("w", "a1")["id"] == "ms_2" and milestones.get("ms_1")["status"] == "superseded"
    assert milestones.activate("ms_1") == (False, None) and milestones.activate("ms_x") == (False, None)
    assert [item["id"] for item in milestones.list("w", ("active",))] == ["ms_2", "ms_3"]
    assert len(milestones.list()) == 3


def test_reject_changes_only_a_proposal():
    milestones = IntakeMilestones(store())
    milestones.insert(milestone("ms_1"))
    milestones.insert(milestone("ms_2", at="t2"))
    milestones.activate("ms_2")
    assert milestones.reject("ms_1") and milestones.get("ms_1")["status"] == "superseded"
    assert not milestones.reject("ms_2") and milestones.get("ms_2")["status"] == "active"


def test_trigger_fires_once_per_key():
    triggers = HeartTriggers(store())
    assert triggers.fire("trigger:milestone:ms_1:done", "w", "t1")
    assert not triggers.fire("trigger:milestone:ms_1:done", "w", "t2")
    assert triggers.fired("trigger:milestone:ms_1:done") and not triggers.fired("trigger:milestone:ms_2:done")
