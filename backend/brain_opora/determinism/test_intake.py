"""Vstupní brána, determinismus: normalizace a otisk, duplicita v prostoru, kandidáti z FTS5, bezpečný zápis
a pohled `overview` (docs/navrhy/2026-10-30-vstupni-brana.md §4, řez 1)."""
import pytest

from backend.brain_opora.determinism import intake
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService
from database.repositories.intake_entries import IntakeEntries


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.db_for("draft")
    yield canvas
    canvas.close()


def write(service, text, workspace="draft", at="2026-10-30T10:00:00Z", source="heart_message", ref=None):
    db = service.db_for("draft")
    with db:
        return intake.record(db, workspace, source, ref, text, at)


def test_normalization_ignores_case_diacritics_punctuation_and_spaces():
    same = ["Přidej hybridní vyhledávání!", "pridej   HYBRIDNI vyhledavani", "  Přidej, hybridní — vyhledávání.  "]
    assert {intake.normalize(text) for text in same} == {"pridej hybridni vyhledavani"}
    assert len({intake.fingerprint(text) for text in same}) == 1
    assert intake.fingerprint("Přidej hybridní vyhledávání") != intake.fingerprint("Přidej hybridní filtr")
    assert intake.query("Ať je to: rychlé, rychlé a k věci") == '"at" OR "je" OR "to" OR "rychle" OR "veci"'


def test_first_sentence_is_pending_and_the_same_one_is_duplicate_in_the_same_workspace(service):
    first = write(service, "Přidej hybridní vyhledávání.")
    assert first["id"].startswith("ie_") and first["verdict"] == "pending" and first["layer"] == "determinism"
    assert first["candidates"] == [] and first["costUsd"] == 0.0 and first["jevCalls"] == 0
    again = write(service, "přidej HYBRIDNÍ vyhledávání", at="2026-10-30T10:05:00Z", source="gate_change", ref="gt_1")
    assert again["verdict"] == "duplicate" and again["reason"] == f"shodná věta jako {first['id']}"
    assert again["candidates"] == [first["id"]]  # kandidát je dřívější vstup, ne vstup samotný
    elsewhere = write(service, "Přidej hybridní vyhledávání.", workspace="main")
    assert elsewhere["verdict"] == "pending"  # duplicita platí jen ve stejném pracovním prostoru
    stored = IntakeEntries(service.db_for("draft")).get(again["id"])
    assert stored["sourceRef"] == "gt_1" and "candidates" not in stored  # kandidáti se neukládají


def test_duplicate_copies_requirement_area_and_milestone_of_the_earlier_entry(service):
    first = write(service, "Vyhledávání vrací cizí dokument.")
    db = service.db_for("draft")
    with db:
        db.execute("UPDATE intake_entries SET requirement_id='rq_1', area_id='a1', milestone_id='ms_1' WHERE id=?",
                   (first["id"],))
    again = write(service, "vyhledavani vraci cizi dokument", at="2026-10-30T11:00:00Z")
    assert (again["requirementId"], again["areaId"], again["milestoneId"]) == ("rq_1", "a1", "ms_1")


def test_candidates_are_nearest_earlier_entries_by_bm25(service):
    search = write(service, "Vyhledávání dokumentů podle organizace", at="2026-10-30T09:00:00Z")
    write(service, "Barva tlačítka na úvodní stránce", at="2026-10-30T09:01:00Z")
    other = write(service, "Vyhledávání je pomalé", at="2026-10-30T09:02:00Z")
    entry = write(service, "Vyhledávání vrací dokumenty cizí organizace", at="2026-10-30T09:03:00Z")
    assert entry["verdict"] == "pending" and entry["candidates"][0] == search["id"]
    assert set(entry["candidates"]) == {search["id"], other["id"]} and entry["id"] not in entry["candidates"]
    later = write(service, "Úplně jiné téma", at="2026-10-30T09:04:00Z")
    assert later["candidates"] == []


def test_empty_text_after_normalization_is_not_recorded(service):
    assert write(service, " ?! … ") is None
    assert IntakeEntries(service.db_for("draft")).recent("draft", 10) == []


def test_safe_record_swallows_errors_and_keeps_the_outer_transaction(service, monkeypatch):
    db = service.db_for("draft")

    def broken(*args):
        raise RuntimeError("FTS je pryč")

    monkeypatch.setattr(intake, "candidates", broken)
    with db:
        db.execute("INSERT INTO guard_trend(project_id,at,metric,value) VALUES('draft','t','m',1)")  # původní tok
        assert intake.safe_record(db, "draft", "heart_message", None, "Věta", "2026-10-30T10:00:00Z") is None
    assert IntakeEntries(db).recent("draft", 10) == []  # savepoint vrátil i řádek vstupu
    assert db.execute("SELECT COUNT(*) FROM intake_entries_fts").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM guard_trend WHERE metric='m'").fetchone()[0] == 1  # původní zápis zůstal


def test_overview_lists_areas_entries_and_counts(service):
    view = service.view("draft", "draft")
    graph = {"nodes": [{"id": "a1", "parentId": None, "kind": "area", "name": "Vyhledání podkladů", "purpose": "",
                        "x": 0, "y": 0, "size": {"w": 400, "h": 300}},
                       {"id": "n1", "parentId": None, "kind": "node", "name": "Karta", "purpose": "", "x": 10, "y": 10}],
             "edges": []}
    service.save_graph("draft", "draft", graph, view["digest"])
    write(service, "Jedna věta")
    write(service, "jedna věta", at="2026-10-30T10:01:00Z")
    result = intake.overview(service, "draft", "draft")
    assert result["areas"] == [{"id": "a1", "name": "Vyhledání podkladů", "milestone": None, "requirements": []}]
    assert [entry["verdict"] for entry in result["entries"]] == ["duplicate", "pending"]  # nejnovější první
    assert (result["pending"], result["duplicates"]) == (1, 1)
    for project, workspace, code in (("nikde", "draft", "project_not_found"), ("draft", "", "invalid_payload"),
                                     ("draft", "w-neni", "workspace_not_found")):
        with pytest.raises(GateError) as caught:
            intake.overview(service, project, workspace)
        assert caught.value.code == code
