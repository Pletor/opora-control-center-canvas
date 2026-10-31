"""Milník vstupní brány (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4, §5): návrh srdcem, rozhodnutí člověka,
splnění kritérií z `done.confirmed` na plátně, postup v %, spouštěč `milestone.done` jednou a pohled po oblastech."""
import json

import pytest

from backend.brain_opora.determinism import milestones
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService
from database.repositories.intake_milestones import IntakeMilestones
from database.repositories.intake_requirements import IntakeRequirements

SESSION = {"project_id": "draft", "workspace_id": "draft"}
CRITERIA = [{"text": "Jen dokumenty organizace", "cards": ["n1", "n2"]}, {"text": "Rychlé", "cards": ["n3"]}]


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    view = canvas.view("draft", "draft")
    nodes = [{"id": "a1", "parentId": None, "kind": "area", "name": "Hledání", "purpose": "", "x": 0, "y": 0,
              "size": {"w": 400, "h": 300}}]
    nodes += [{"id": f"n{number}", "parentId": None, "kind": "node", "name": f"Karta {number}", "purpose": "",
               "x": 10 * number, "y": 10} for number in (1, 2, 3)]
    canvas.save_graph("draft", "draft", {"nodes": nodes, "edges": []}, view["digest"])
    yield canvas
    canvas.close()


def close(service, *cards):
    """Karty `cards` uzavřené na plátně (`done.confirmed`), ostatní otevřené."""
    state = {"nodes": {card: {"done": {"confirmed": True}} for card in cards}}
    db = service.db_for("draft")
    with db:
        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES('draft','draft',1,?,'t')", (json.dumps(state),))


def proposed(service, title="Spolehlivé hledání", criteria=CRITERIA):
    return milestones.propose(service, SESSION, "a1", title, criteria, "2026-10-30T10:00:00Z")


def decide(service, milestone_id, action="activate"):
    return milestones.decide(service, {"project": "draft", "workspace": "draft", "milestoneId": milestone_id,
                                       "action": action})


def refused(call, *args):
    with pytest.raises(GateError) as caught:
        call(*args)
    return caught.value.code


def test_heart_proposes_only_for_an_area_and_existing_cards(service):
    made = proposed(service)
    assert made["status"] == "proposed" and made["id"].startswith("ms_")
    assert [item["id"] for item in made["criteria"]] == ["c1", "c2"] and made["criteria"][0]["cards"] == ["n1", "n2"]
    assert refused(milestones.propose, service, SESSION, "n1", "T", CRITERIA, "t") == "area_not_found"
    assert refused(milestones.propose, service, SESSION, "a1", "T", [{"text": "x", "cards": ["n9"]}], "t"
                   ) == "card_not_found"
    for criteria in ([], [{"text": "x", "cards": []}], [{"text": " ", "cards": ["n1"]}], [{"text": "x"}]):
        assert refused(milestones.propose, service, SESSION, "a1", "T", criteria, "t") == "invalid_payload"
    assert refused(milestones.propose, service, SESSION, "a1", "", CRITERIA, "t") == "invalid_payload"


def test_human_activation_supersedes_the_active_milestone_and_reject_keeps_history(service):
    first, second, third = proposed(service, "První"), proposed(service, "Druhý"), proposed(service, "Třetí")
    assert decide(service, first["id"]) == {"id": first["id"], "status": "active", "superseded": None}
    assert decide(service, second["id"]) == {"id": second["id"], "status": "active", "superseded": first["id"]}
    assert decide(service, third["id"], "reject") == {"id": third["id"], "status": "superseded", "superseded": None}
    stored = IntakeMilestones(service.db_for("draft"))
    assert stored.get(first["id"])["status"] == "superseded" and stored.active("draft", "a1")["id"] == second["id"]
    assert refused(decide, service, first["id"]) == "milestone_not_proposed"
    assert refused(decide, service, "ms_neni") == "milestone_not_found"
    assert refused(decide, service, second["id"], "pause") == "invalid_payload"
    assert refused(milestones.decide, service, {"project": "draft"}) == "invalid_payload"


def test_reject_ends_an_active_milestone_but_activate_stays_proposal_only(service):
    first = proposed(service, "První")
    decide(service, first["id"])
    assert refused(decide, service, first["id"]) == "milestone_not_proposed"
    assert decide(service, first["id"], "reject") == {"id": first["id"], "status": "superseded", "superseded": None}
    assert IntakeMilestones(service.db_for("draft")).active("draft", "a1") is None
    area = next(item for item in milestones.plan(service.db_for("draft"), "draft", "draft",
                                                  [{"id": "a1", "name": "Hledání"}])[0] if item["id"] == "a1")
    assert area["milestone"] is None
    assert refused(decide, service, first["id"], "reject") == "milestone_not_proposed"


def test_criterion_is_met_when_all_its_cards_are_closed_and_progress_averages_cards(service):
    milestone = IntakeMilestones(service.db_for("draft")).get(proposed(service)["id"])
    db = service.db_for("draft")
    result = milestones.evaluate(db, "draft", milestone)
    assert (result["done"], result["progress"]) == (False, 0)
    close(service, "n1", "n3")
    result = milestones.evaluate(db, "draft", milestone)
    assert [item["done"] for item in result["criteria"]] == [False, True]
    assert result["criteria"][0]["cards"] == [{"id": "n1", "done": True}, {"id": "n2", "done": False}]
    assert (result["done"], result["progress"]) == (False, 67)
    close(service, "n1", "n2", "n3")
    assert milestones.evaluate(db, "draft", milestone)["done"] is True


def test_reached_milestone_wakes_once_with_its_deferred_requirements(service):
    made = proposed(service)
    db = service.db_for("draft")
    with db:
        IntakeRequirements(db).insert({"id": "rq_1", "workspaceId": "draft", "areaId": "a1", "title": "Hybridní",
                                       "status": "deferred", "openCondition": made["id"], "createdAt": "t1"})
        IntakeRequirements(db).insert({"id": "rq_2", "workspaceId": "draft", "areaId": "a1", "title": "Jiné",
                                       "status": "deferred", "openCondition": "ms_jiny", "createdAt": "t2"})
    close(service, "n1", "n2", "n3")
    with db:
        assert milestones.wakes(db, "draft", None, "t") == []  # návrh se nepočítá, jen aktivní milník
    decide(service, made["id"])
    with db:
        assert milestones.wakes(db, "draft", {"main"}, "t") == []  # jiný prostor
        found = milestones.wakes(db, "draft", {"draft"}, "t")
        again = milestones.wakes(db, "draft", None, "t")
    assert found == [("draft", {"type": "milestoneDone", "milestoneId": made["id"], "title": "Spolehlivé hledání",
                                "areaId": "a1", "deferred": [{"id": "rq_1", "title": "Hybridní"}]})]
    assert again == []  # jednou na stav (klíč trigger:milestone:<id>:done)
    assert IntakeRequirements(db).get("rq_1")["status"] == "deferred"  # stav požadavku rozhodne srdce
    assert [item["milestone"]["id"] for item in milestones.reached(db, "draft", "draft")] == [made["id"]]


def test_plan_groups_milestones_and_requirements_by_area(service):
    active, waiting = proposed(service, "Aktivní"), proposed(service, "Návrh")
    decide(service, active["id"])
    db = service.db_for("draft")
    with db:
        for rq, status, area in (("rq_1", "open", "a1"), ("rq_2", "deferred", "a1"), ("rq_3", "open", None),
                                 ("rq_4", "done", "a1")):
            IntakeRequirements(db).insert({"id": rq, "workspaceId": "draft", "areaId": area, "title": rq,
                                           "status": status, "createdAt": rq})
    areas, unassigned = milestones.plan(db, "draft", "draft", [{"id": "a1", "name": "Hledání"}])
    area = areas[0]
    assert area["milestone"]["id"] == active["id"] and area["milestone"]["progress"] == 0
    assert [item["id"] for item in area["proposed"]] == [waiting["id"]]
    assert [item["id"] for item in area["requirements"]] == ["rq_1"]
    assert [item["id"] for item in area["deferred"]] == ["rq_2"]
    assert [item["id"] for item in unassigned] == ["rq_3"]
