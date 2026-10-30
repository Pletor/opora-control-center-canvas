"""Výslech ve Schránce, řez 1 (docs/navrhy/2026-10-31-vyslech-ve-schrance.md): kořen požadavku, části syntézy,
předpoklady a otázky jako fragmenty Schránky, bez nového vstupu brány a bez zastavení výslechu."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import brief
from backend.brain_opora.determinism import brief_vault_link as vault_link
from backend.brain_opora.determinism.test_brief import CLEAR, SESSION, add
from backend.canvas.test_canvas_plan import ORIGIN, seed
from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.brief_vault.brief_vault_details import latest_details
from backend.editor.brief_vault.brief_vault_model import latest_rows
from database.repositories.intake_briefs import IntakeBriefs
from database.repositories.intake_entries import IntakeEntries

BODY = {"project": "draft", "workspace": "draft"}


@pytest.fixture
def service(tmp_path):
    application = create_app(tmp_path)
    with TestClient(application, base_url=ORIGIN) as client:
        seed(client)
        yield application.state.service


def rows(service):
    return latest_rows(service.db_for("draft"), "draft", "draft")


def entries(service):
    return service.db_for("draft").execute("SELECT COUNT(*) FROM intake_entries").fetchone()[0]


def situation(service, rq):
    return IntakeBriefs(service.db_for("draft")).get(rq)["situation"]


def test_start_creates_one_verbatim_root_without_a_new_intake_entry(service):
    with service.db_for("draft"):
        add(service.db_for("draft"), "rq_s", ["fix_for_milestone"])
    before = entries(service)
    brief.start(service, {**BODY, "requirement": "rq_s"}, "t1")
    root = situation(service, "rq_s")["fragmentId"]
    found = rows(service)[root]
    assert (found["kind"], found["text"], found["parent_id"], found["scope_node_id"], found["discipline"]) == (
        "brief", "Chci metriky 0.", None, "", vault_link.ROOT_DISCIPLINE)
    assert entries(service) == before  # zrcadlo nezaloží vstup brány, jinak by vznikl další požadavek
    assert vault_link.ensure_root(service, "draft", "draft", "rq_s") == root  # idempotence
    brief.save_synthesis(service, SESSION, "rq_s", {"goal": "x"}, "t2")  # obnova spisu kořen neztratí
    assert situation(service, "rq_s")["fragmentId"] == root and len(rows(service)) == 1
    view = brief.view(IntakeBriefs(service.db_for("draft")).get("rq_s"))
    assert (view["fragmentId"], view["fragmentScope"]) == (root, "")


def test_a_requirement_born_in_the_vault_keeps_its_fragment_as_root(service):
    created = BriefVault(service).apply({**BODY, "op": "create", "title": "Metriky", "text": "Chci metriky ze Schránky.",
                                         "scopeNodeId": "", "discipline": "be"}, actor="human")
    fragment = created["fragment"]["id"]
    db = service.db_for("draft")
    entry = IntakeEntries(db).by_source("brief_fragment", fragment)
    assert entry is not None  # běžná cesta Schránky vstup brány dál zakládá
    with db:
        add(db, "rq_v", [])
        IntakeEntries(db).set_requirement(entry["id"], "rq_v")
    brief.start(service, {**BODY, "requirement": "rq_v"}, "t1")
    assert situation(service, "rq_v")["fragmentId"] == fragment and len(rows(service)) == 1


def test_synthesis_parts_revise_in_place_and_assumptions_become_questions_once(service):
    with service.db_for("draft"):
        add(service.db_for("draft"), "rq_p", ["fix_for_milestone"])
    before = entries(service)
    synthesis = {**CLEAR, "assumptions": ["logování už existuje"]}
    brief.save_synthesis(service, SESSION, "rq_p", synthesis, "t1")
    linked = situation(service, "rq_p")
    parts = linked["partFragments"]
    found = rows(service)
    assert [found[item]["text"] for item in parts] == ["cena dávky", "chybovost dávek"]
    assert all(found[item]["parent_id"] == linked["fragmentId"] for item in parts)
    assert "původ: research · zdroj: https://sre.google/sre-book/" in found[parts[1]]["note"]
    question = found[linked["assumptionFragments"]["logování už existuje"]]
    assert (question["kind"], question["title"]) == ("question", "Platí, že logování už existuje?")
    changed = {**synthesis, "parts": [{**CLEAR["parts"][0], "text": "cena dávky v USD"}, CLEAR["parts"][1]]}
    brief.save_synthesis(service, SESSION, "rq_p", changed, "t2")
    again = rows(service)
    assert situation(service, "rq_p")["partFragments"] == parts and len(again) == len(found)  # nic se nezdvojilo
    assert (again[parts[0]]["revision"], again[parts[0]]["text"]) == (2, "cena dávky v USD")
    assert again[parts[1]]["revision"] == 1
    assert entries(service) == before


def test_ask_and_human_answer_mirror_into_questions_to_clarify(service):
    with service.db_for("draft"):
        add(service.db_for("draft"), "rq_q", ["fix_for_milestone"])
    brief.save_synthesis(service, SESSION, "rq_q", CLEAR, "t1")
    brief.ask(service, SESSION, "rq_q", "Stačí denní trend?", "Ano, denní.", "Hodinový je drahý.", "t2")
    fragment = situation(service, "rq_q")["questionFragments"]["q1"]
    details = latest_details(service.db_for("draft"), "draft", "draft", [fragment])[fragment]["fields"]["question"]
    assert (details["askedFor"], details["proposal"], details["answer"]) == ("human", "Ano, denní.", "")
    brief.answer(service, {**BODY, "requirement": "rq_q", "question": "q1", "accept": True}, "t3")
    details = latest_details(service.db_for("draft"), "draft", "draft", [fragment])[fragment]["fields"]["question"]
    assert (details["answer"], details["answeredBy"]) == ("Ano, denní.", "human")
    assert rows(service)[fragment]["stage"] == "ready"


def test_a_vault_failure_is_logged_and_the_brief_goes_on(service, monkeypatch, caplog):
    with service.db_for("draft"):
        add(service.db_for("draft"), "rq_f", ["fix_for_milestone"])

    def broken(*args, **kwargs):
        raise ValueError("Schránka zadání: porucha")

    monkeypatch.setattr(vault_link, "_op", broken)
    assert brief.save_synthesis(service, SESSION, "rq_f", CLEAR, "t1")["status"] == "clear"
    assert "fragmentId" not in situation(service, "rq_f") and "Výslech ve Schránce" in caplog.text
