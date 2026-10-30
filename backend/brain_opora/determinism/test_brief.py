"""Výslech srdce, řez 1 (docs/navrhy/2026-10-30-vyslech-srdce.md): tabulka spouštěče §2, kritéria jasna §4,
spis §3.1, `brief` a `ask` §7 a probuzení jednou na stav (`heart_triggers`)."""
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import brief
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.test_canvas_plan import ORIGIN, seed
from database.repositories.intake_briefs import IntakeBriefs
from database.repositories.intake_entries import IntakeEntries
from database.repositories.intake_requirements import IntakeRequirements

NOW = datetime(2026, 10, 30, 12, tzinfo=UTC).timestamp()
SESSION = {"project_id": "draft", "workspace_id": "draft"}
CLEAR = {"goal": "Provozní metriky srdce pro člověka ve Velínu.", "users": "člověk, který řídí projekt",
         "parts": [{"text": "cena dávky", "origin": "human", "source": "zadání"},
                   {"text": "chybovost dávek", "origin": "research", "source": "https://sre.google/sre-book/"}],
         "acceptance": [{"text": "test_metrics projde", "check": "test"},
                        {"text": "cena dávky do 1 s po konci", "check": "measure"},
                        {"text": "Velín ukáže trend", "check": "observe"}],
         "outOfScope": ["export do Grafany"], "dependencies": [{"ref": "a0", "text": "oblast Provoz"}],
         "questions": [{"text": "Stačí denní trend?", "impact": "high", "answer": "ano, doporučeno"}]}


def test_needs_brief_follows_the_trigger_table():
    assert brief.needs_brief(status="open", verdicts=["fix_for_milestone"]) == "new"
    assert brief.needs_brief(status="open", verdicts=["later_extension"]) == "opened"
    assert brief.needs_brief(status="deferred", verdicts=["later_extension"]) is None  # ještě odložený
    assert brief.needs_brief(status="open", verdicts=["fix_for_milestone", "changes_intent"],
                             brief_status="clear") == "changes_intent"  # dopady i po jasnu
    assert brief.needs_brief(status="open", verdicts=["fix_for_milestone"], brief_status="clear") is None
    for verdict in ("duplicate", "done", "extends_in_progress", "needs_info"):
        assert brief.needs_brief(status="open", verdicts=[verdict]) is None
    assert brief.needs_brief(status="open", verdicts=[]) is None
    assert brief.needs_brief(status="ready", evidence="thin") == "thin"
    assert brief.needs_brief(status="running", evidence="thin") is None
    assert brief.needs_brief(status="ready", evidence="ok") is None


def test_clarity_lists_what_is_missing_and_a_full_synthesis_is_clear():
    assert brief.clarity(CLEAR) == []
    assert [item.split(":")[0] for item in brief.clarity(None)] == [
        "goal", "users", "acceptance", "outOfScope", "parts", "dependencies"]
    only_human = {**CLEAR, "parts": [{"text": "cena", "origin": "human"}, {"text": "x", "origin": "research"}]}
    assert brief.clarity(only_human) == [brief.MISSING["parts.origin"]]  # rešerše bez zdroje se nepočítá
    two = {**CLEAR, "acceptance": CLEAR["acceptance"][:2]}
    assert brief.clarity(two) == [brief.MISSING["acceptance"]]
    open_high = {**CLEAR, "questions": [{"text": "Kdo?", "impact": "high"}]}
    assert brief.clarity(open_high) == [brief.MISSING["questions.high"]]
    assert brief.clarity({**CLEAR, "questions": [{"text": "Kdo?", "impact": "low"}]}) == []
    assert brief.clarity(CLEAR, [{"id": "q1", "answer": None}]) == [brief.MISSING["questions.open"]]


def test_check_synthesis_refuses_unknown_keys_and_wrong_enums():
    assert brief.check_synthesis(CLEAR) is CLEAR
    for bad in ({}, [], {"goal": "x", "extra": 1}, {"goal": 3}, {"outOfScope": "x"},
                {"parts": [{"text": "x", "origin": "rešerše"}]}, {"acceptance": [{"text": "x", "check": "pocit"}]},
                {"dependencies": [{"ref": "a0"}]}):
        with pytest.raises(GateError) as refused:
            brief.check_synthesis(bad)
        assert refused.value.code == "invalid_payload" and "tvar" in refused.value.hint


def test_situation_and_summary_keep_the_human_sentence_verbatim():
    requirement = {"id": "rq_1", "title": "Metriky", "status": "open", "areaId": "a0"}
    entries = [{"id": "ie_1", "text": "Chci metriky A, B, C.", "verdict": "fix_for_milestone"}]
    spis = brief.situation(requirement, entries, [{"id": "ie_0", "text": "metriky dávek"}], "Klidný provoz",
                           {"id": "a0", "name": "Provoz"},
                           {"id": "ms_1", "title": "Provoz běží", "status": "active",
                            "criteria": [{"text": "Dávky měřené", "cards": ["n1"]}]},
                           [{"id": "n1", "name": "Měřák", "label": "?", "evidence": "thin", "steps": 1}],
                           ["Česky"], ["Bez Grafany"])
    assert spis["inputs"][0]["text"] == "Chci metriky A, B, C." and spis["milestone"]["criteria"] == ["Dávky měřené"]
    assert (spis["intent"], spis["rules"], spis["similar"][0]["id"]) == ("Klidný provoz", ["Česky"], "ie_0")
    assert brief.summary(spis) == ("„Chci metriky A, B, C.“ · oblast a0 „Provoz“ · milník ms_1 „Provoz běží“"
                                   " · karty: n1 [?]")


def card(**extra):
    return {"nodeId": "n1", "title": "Měřák", "workspace": "w1", "status": "ready", "label": "?", "evidence": "thin",
            "points": 1.0, "effort": None, "failures": 0, "failedRun": None, "runId": None, "age": None,
            "sinceStep": None, "costUsd": None, **extra}


def add(db, rq, verdicts, at="2026-10-30T10:00:00Z", status="open", area="a0"):
    IntakeRequirements(db).insert({"id": rq, "workspaceId": "draft", "areaId": area, "milestoneId": None,
                                   "title": "Metriky srdce", "status": status, "createdAt": at})
    store = IntakeEntries(db)
    for number, verdict in enumerate(verdicts):
        entry = f"ie_{rq}_{number}"
        store.insert({"id": entry, "workspaceId": "draft", "source": "heart_message", "text": f"Chci metriky {number}.",
                      "fingerprint": entry, "createdAt": at, "verdict": verdict, "layer": "heart", "jevCalls": 0})
        store.set_requirement(entry, rq)


@pytest.fixture
def app(tmp_path):
    application = create_app(tmp_path)
    with TestClient(application, base_url=ORIGIN) as client:
        seed(client)  # oblast a0, sektor s0, karta n0
        yield application


def test_brief_sets_clear_only_without_missing_and_ask_caps_questions_and_rounds(app):
    service = app.state.service
    db = service.db_for("draft")
    with db:
        add(db, "rq_1", ["fix_for_milestone"])
    with pytest.raises(GateError) as refused:
        brief.ask(service, SESSION, "rq_1", "Kdo?", "Člověk.", "Určí rozsah.", "t0")
    assert refused.value.code == "brief_missing"
    thin = {key: CLEAR[key] for key in ("goal", "users", "parts")}
    assert brief.save_synthesis(service, SESSION, "rq_1", thin, "t1") == {
        "requirement": "rq_1", "status": "draft",
        "missing": [brief.MISSING[key] for key in ("acceptance", "outOfScope", "dependencies")]}
    assert IntakeBriefs(db).get("rq_1")["situation"]["requirement"]["id"] == "rq_1"
    for number in range(3):
        asked = brief.ask(service, SESSION, "rq_1", f"Otázka {number}?", "Ano.", "Mění plán.", "t2")
    assert (asked["question"], asked["open"], asked["rounds"], asked["status"]) == ("q3", 3, 1, "grilling")
    with pytest.raises(GateError) as refused:
        brief.ask(service, SESSION, "rq_1", "Čtvrtá?", "Ano.", "Mění plán.", "t3")
    assert refused.value.code == "brief_questions_full"
    assert brief.save_synthesis(service, SESSION, "rq_1", CLEAR, "t4")["status"] == "grilling"  # čeká na člověka
    stored = IntakeBriefs(db).get("rq_1")
    answered = [{**item, "answer": "ano", "answered_at": "t5"} for item in stored["questions"]]
    with db:
        IntakeBriefs(db).save({**stored, "questions": answered, "rounds": brief.ROUNDS})
    assert brief.save_synthesis(service, SESSION, "rq_1", CLEAR, "t6") == {
        "requirement": "rq_1", "status": "clear", "missing": []}
    with pytest.raises(GateError) as refused:
        brief.ask(service, SESSION, "rq_1", "Další kolo?", "Ne.", "Strop.", "t7")
    assert refused.value.code == "brief_rounds_spent"
    with pytest.raises(GateError) as refused:
        brief.save_synthesis(service, {**SESSION, "workspace_id": "main"}, "rq_1", CLEAR, "t8")
    assert refused.value.code == "intake_requirement_not_found"


def test_research_cost_adds_up_to_the_cap_and_then_refuses(app):
    """Řez 2 (§8): strop rešerše na požadavek, cena se sčítá do `intake_briefs.cost_usd`."""
    from backend.brain_opora.determinism import brief_setting

    service = app.state.service
    db = service.db_for("draft")
    with db:
        add(db, "rq_r", ["fix_for_milestone"])
    assert brief.research_budget(service, SESSION, "rq_r") == {
        "requirement": "rq_r", "spentUsd": 0.0, "capUsd": 0.30, "leftUsd": 0.30}
    spent = brief.research_spend(service, SESSION, "rq_r", 0.12, "frag1", "feasible/plan: stačí",
                                 ["https://a.cz", "https://a.cz", 3], "t1")
    assert spent == {"requirement": "rq_r", "spentUsd": 0.12, "capUsd": 0.30, "leftUsd": 0.18}
    stored = IntakeBriefs(db).get("rq_r")
    assert (stored["status"], stored["costUsd"]) == ("research", 0.12)
    assert stored["research"] == [{"fragmentId": "frag1", "digest": "feasible/plan: stačí", "sources": ["https://a.cz"],
                                   "costUsd": 0.12, "at": "t1"}]
    assert brief.research_spend(service, SESSION, "rq_r", 0.2, now="t2")["leftUsd"] == 0
    with pytest.raises(GateError) as refused:
        brief.research_budget(service, SESSION, "rq_r")
    assert refused.value.code == "brief_research_spent" and refused.value.hint == brief.SPENT_HINT
    brief_setting.write(service, {"project": "draft", "enabled": True, "researchUsd": 1.0})  # člověk strop zvedne
    assert brief.research_budget(service, SESSION, "rq_r")["leftUsd"] == 0.68
    with pytest.raises(GateError) as refused:
        brief.research_spend(service, SESSION, "rq_r", -1, now="t3")
    assert refused.value.code == "invalid_payload"
    with pytest.raises(GateError) as refused:
        brief.research_budget(service, {**SESSION, "workspace_id": "main"}, "rq_r")
    assert refused.value.code == "intake_requirement_not_found"
