"""Požadavky vstupní brány (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5): srdce při potvrzení stanoviska
založí požadavek (`new`) nebo vstup připojí k existujícímu (`rq_…`); rozšíření je odložené s podmínkou otevření."""
import pytest

from backend.brain_opora.determinism import intake
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService
from database.repositories.intake_entries import IntakeEntries
from database.repositories.intake_milestones import IntakeMilestones
from database.repositories.intake_requirements import IntakeRequirements

SESSION = {"project_id": "draft", "workspace_id": "draft"}


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    db = canvas.db_for("draft")
    with db:
        IntakeMilestones(db).insert({"id": "ms_1", "workspaceId": "draft", "areaId": "a1", "title": "Hledání",
                                     "criteria": [], "status": "proposed", "createdAt": "t0"})
        IntakeMilestones(db).activate("ms_1")
    yield canvas
    canvas.close()


def entry(service, text, area="a1", workspace="draft"):
    db = service.db_for("draft")
    with db:
        made = intake.record(db, workspace, "heart_message", None, text, "2026-10-30T10:00:00Z")
        if area:
            db.execute("UPDATE intake_entries SET area_id=? WHERE id=?", (area, made["id"]))
    return made["id"]


def confirm(service, entry_id, verdict, **options):
    return intake.confirm(service, SESSION, entry_id, verdict, "", options.get("requirement"), options.get("title"),
                          options.get("open_condition"))


def stored(service, rq):
    return IntakeRequirements(service.db_for("draft")).get(rq)


def test_extension_is_deferred_until_the_active_milestone_and_more_entries_merge_into_it(service):
    first = entry(service, "Přidej hybridní hledání.")
    result = confirm(service, first, "later_extension", requirement="new", title="Hybridní hledání")
    rq = result["requirementId"]
    assert rq.startswith("rq_")
    assert {key: stored(service, rq)[key] for key in ("status", "openCondition", "areaId", "milestoneId")} == {
        "status": "deferred", "openCondition": "ms_1", "areaId": "a1", "milestoneId": None}
    second = entry(service, "A k tomu sémantické vyhledávání.")
    assert confirm(service, second, "later_extension", requirement=rq)["requirementId"] == rq  # žádné nové zadání
    assert len(IntakeRequirements(service.db_for("draft")).list("draft")) == 1
    assert IntakeEntries(service.db_for("draft")).get(second)["requirementId"] == rq


def test_fix_is_open_in_the_active_milestone_and_explicit_condition_wins(service):
    fix = confirm(service, entry(service, "Vrací cizí dokument."), "fix_for_milestone", requirement="new",
                  title="Jen dokumenty organizace")
    assert {key: stored(service, fix["requirementId"])[key] for key in ("status", "milestoneId", "openCondition")} == {
        "status": "open", "milestoneId": "ms_1", "openCondition": None}
    later = confirm(service, entry(service, "Export do PDF."), "later_extension", requirement="new", title="Export",
                    open_condition="ms_2")
    assert stored(service, later["requirementId"])["openCondition"] == "ms_2"


def test_bad_requirement_options_are_refused_and_nothing_is_written(service):
    plain = entry(service, "Věta bez oblasti.", area=None)
    other = entry(service, "Jiná věta.", workspace="main")
    db = service.db_for("draft")
    with db:
        IntakeRequirements(db).insert({"id": "rq_main", "workspaceId": "main", "title": "Cizí", "status": "open",
                                       "createdAt": "t"})
    cases = ((plain, "later_extension", {"requirement": "new", "title": "X"}, "invalid_payload"),  # bez podmínky
             (plain, "done", {"requirement": "new"}, "invalid_payload"),  # chybí název
             (plain, "done", {"requirement": "new", "title": "X", "open_condition": "ms_1"}, "invalid_payload"),
             (plain, "done", {"requirement": "rq_1", "title": "X"}, "invalid_payload"),
             (plain, "done", {"title": "X"}, "invalid_payload"),
             (plain, "done", {"requirement": "x"}, "invalid_payload"),
             (plain, "done", {"requirement": "rq_main"}, "intake_requirement_not_found"),
             (other, "done", {"requirement": "new", "title": "X"}, "intake_entry_not_found"))
    for entry_id, verdict, options, code in cases:
        with pytest.raises(GateError) as caught:
            confirm(service, entry_id, verdict, **options)
        assert caught.value.code == code, options
    assert IntakeRequirements(db).list("draft") == []
    assert IntakeEntries(db).get(plain)["verdict"] == "pending"  # odmítnutí vrátí i stanovisko
