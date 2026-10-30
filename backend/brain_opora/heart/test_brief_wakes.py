"""Probuzení výslechu srdce (docs/navrhy/2026-10-30-vyslech-srdce.md §2, §8): `inputs.brief_wakes` a `card_wakes`
jednou na stav, vypnutý výslech nebudí. Přesunuto z `determinism/test_brief.py` (determinismus nesmí importovat
`heart`, `test_layer_boundaries.py`); pomocné funkce a fixture `app` jsou odtamtud."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import brief, triggers
from backend.brain_opora.determinism.test_brief import (  # noqa: F401 - fixture skutečné aplikace
    NOW,
    add,
    app,
    card,
)
from backend.brain_opora.heart import inputs
from backend.canvas.test_canvas_plan import ORIGIN
from database.repositories.intake_briefs import IntakeBriefs
from database.repositories.intake_entries import IntakeEntries


def test_thin_ready_card_wakes_a_short_brief_once(tmp_path, monkeypatch):
    assert brief.card_hit(card()) == ("trigger:brief:card:n1:thin@w1", {
        "type": "brief", "nodeId": "n1", "title": "Měřák", "reason": "thin", "detail": brief.card_gauge.THIN_REASON})
    assert brief.card_hit(card(status="running")) is None and brief.card_hit(card(evidence="ok", label="S")) is None
    cards = [card(nodeId=f"n{number}") for number in range(7)]
    monkeypatch.setattr(triggers, "facts", lambda *args: (cards, []))
    app = create_app(tmp_path)  # noqa: F811 - vlastní aplikace, ne fixture
    with TestClient(app, base_url=ORIGIN):
        service = app.state.service
        first = inputs.card_wakes(service, "draft", {"w1"}, "t1", 0)
        assert [item["nodeId"] for _, item in first] == ["n0", "n1", "n2", "n3", "n4"]  # strop EXTRA na průchod
        assert [item["nodeId"] for _, item in inputs.card_wakes(service, "draft", {"w1"}, "t2", 0)] == ["n5", "n6"]
        assert inputs.card_wakes(service, "draft", {"w1"}, "t3", 0) == []
        assert triggers.wakes(service, "draft", {"w1"}, "t4", 0) == []  # bez `extra` tenké karty nebudí


def test_requirement_wakes_once_per_state_with_a_draft_brief_and_its_situation(app):  # noqa: F811
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


def test_disabled_brief_never_wakes(app):  # noqa: F811
    """Řez 2 (§8): `brain.brief.enabled = false` → `needs_brief` nic, požadavky ani tenké karty nebudí."""
    from backend.brain_opora.determinism import brief_setting

    assert brief.needs_brief(status="open", verdicts=["fix_for_milestone"], enabled=False) is None
    assert brief.needs_brief(status="ready", evidence="thin", enabled=False) is None
    assert brief.card_hit(card(), enabled=False) is None
    service = app.state.service
    db = service.db_for("draft")
    with db:
        add(db, "rq_off", ["fix_for_milestone"])
    brief_setting.write(service, {"project": "draft", "enabled": False})
    assert inputs.brief_wakes(service, "draft", "t1", NOW) == []
    assert brief.requirement_wakes(db, "2026-10-29T12:00:00Z", enabled=False) == []
    brief_setting.write(service, {"project": "draft", "enabled": True})
    assert [item["requirementId"] for _, item in inputs.brief_wakes(service, "draft", "t2", NOW)] == ["rq_off"]


def test_human_answer_and_start_wake_the_heart_once_each(app):  # noqa: F811
    """Řez 3: odpověď na otázku výslechu a „Vyslechni mě k tomu“ budí srdce jednou, i s vypnutým výslechem
    (přímá akce člověka); srdce v dávce vidí otázku a odpověď."""
    from backend.brain_opora.determinism import brief_setting
    from backend.brain_opora.determinism.test_brief import CLEAR, SESSION
    from backend.brain_opora.heart.batch import _input_line

    service = app.state.service
    db = service.db_for("draft")
    with db:
        add(db, "rq_a", ["needs_info"])
        add(db, "rq_s", ["needs_info"], at="2026-10-01T10:00:00Z")
    brief.save_synthesis(service, SESSION, "rq_a", CLEAR, "t1")
    brief.ask(service, SESSION, "rq_a", "Stačí denní trend?", "Ano, denní.", "Hodinový je drahý.", "t2")
    assert inputs.brief_wakes(service, "draft", "t3", NOW) == []  # otázka bez odpovědi nebudí
    scope = {"project": "draft", "workspace": "draft"}
    brief.start(service, {**scope, "requirement": "rq_s"}, "t4")
    brief.answer(service, {**scope, "requirement": "rq_a", "question": "q1", "accept": True}, "t5")
    brief_setting.write(service, {"project": "draft", "enabled": False})
    woke = inputs.brief_wakes(service, "draft", "t6", NOW)
    assert [(space, item["requirementId"], item["reason"]) for space, item in woke] == [
        ("draft", "rq_a", "answer"), ("draft", "rq_s", "asked")]
    answer_line = _input_line(woke[0][1])
    assert answer_line.startswith("- VÝSLECH: rq_a „Metriky srdce“ (odpověď člověka na výslech")
    assert "otázka q1 „Stačí denní trend?“ → člověk potvrdil doporučení „Ano, denní.“" in answer_line
    assert woke[1][1]["detail"].startswith("„Chci metriky 0.“")
    assert inputs.brief_wakes(service, "draft", "t7", NOW) == []  # jednou na odpověď a žádost
    keys = {row[0] for row in db.execute("SELECT key FROM heart_triggers")}
    assert {"trigger:brief:rq_a:answer:q1", "trigger:brief:rq_s:asked"} <= keys
