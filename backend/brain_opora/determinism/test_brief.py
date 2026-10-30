"""Výslech srdce, řez 1 (docs/navrhy/2026-10-30-vyslech-srdce.md): tabulka spouštěče §2, kritéria jasna §4,
spis §3.1, `brief` a `ask` §7 a probuzení jednou na stav (`heart_triggers`)."""
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import brief, triggers
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.heart import inputs
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


def test_thin_ready_card_wakes_a_short_brief_once(tmp_path, monkeypatch):
    assert brief.card_hit(card()) == ("trigger:brief:card:n1:thin@w1", {
        "type": "brief", "nodeId": "n1", "title": "Měřák", "reason": "thin", "detail": brief.card_gauge.THIN_REASON})
    assert brief.card_hit(card(status="running")) is None and brief.card_hit(card(evidence="ok", label="S")) is None
    cards = [card(nodeId=f"n{number}") for number in range(7)]
    monkeypatch.setattr(triggers, "facts", lambda *args: (cards, []))
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN):
        service = app.state.service
        first = inputs.card_wakes(service, "draft", {"w1"}, "t1", 0)
        assert [item["nodeId"] for _, item in first] == ["n0", "n1", "n2", "n3", "n4"]  # strop EXTRA na průchod
        assert [item["nodeId"] for _, item in inputs.card_wakes(service, "draft", {"w1"}, "t2", 0)] == ["n5", "n6"]
        assert inputs.card_wakes(service, "draft", {"w1"}, "t3", 0) == []
        assert triggers.wakes(service, "draft", {"w1"}, "t4", 0) == []  # bez `extra` tenké karty nebudí


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


def test_requirement_wakes_once_per_state_with_a_draft_brief_and_its_situation(app):
    service = app.state.service
    db = service.db_for("draft")
    with db:
        add(db, "rq_new", ["fix_for_milestone"])
        add(db, "rq_old", ["fix_for_milestone"], at="2026-10-27T10:00:00Z")  # mimo okno 24 h
        add(db, "rq_dup", ["extends_in_progress"])
        add(db, "rq_later", ["later_extension"], status="deferred")
    [(space, item)] = inputs.brief_wakes(service, "draft", "t1", NOW)
    assert space == "draft" and (item["type"], item["requirementId"], item["reason"]) == ("brief", "rq_new", "new")
    assert item["detail"].startswith("„Chci metriky 0.“ · oblast a0 „Stará oblast“")
    saved = IntakeBriefs(db).get("rq_new")
    assert saved["status"] == "draft" and saved["situation"]["inputs"][0]["verdict"] == "fix_for_milestone"
    assert inputs.brief_wakes(service, "draft", "t2", NOW) == []  # stejný stav nebudí
    with db:
        IntakeEntries(db).insert({"id": "ie_x", "workspaceId": "draft", "source": "gate_change", "text": "Jinak.",
                                  "fingerprint": "x", "createdAt": "2026-10-30T11:00:00Z",
                                  "verdict": "changes_intent", "layer": "heart", "jevCalls": 0})
        IntakeEntries(db).set_requirement("ie_x", "rq_new")
    assert [item["reason"] for _, item in inputs.brief_wakes(service, "draft", "t3", NOW)] == ["changes_intent"]


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
