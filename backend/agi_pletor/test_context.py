"""Podklady Pletora s falešnými zdroji: každá sekce, strop délky, výpadek zdroje a prázdné sekce."""
import contextlib
import json
from types import SimpleNamespace

from backend.agi_pletor import context, questions, store


class Heart:
    def __init__(self, status=None, error=None):
        self.value, self.error = status or {"pending": 2, "batches": [{"summary": "Postaven hero."}]}, error

    def status(self, project):
        if self.error:
            raise self.error
        return self.value


def service_at(tmp_path):
    folder = SimpleNamespace(path=tmp_path)
    return SimpleNamespace(folder=lambda project: folder, reading=lambda project: contextlib.nullcontext(),
                           db_for=lambda project: None)


def ticket(status, build, session=None):
    return {"status": status, "body": {"build": build + "\ndalší řádek"}, "sessionId": session}


def row(fid, title, kind="brief", stage="draft", parent=None, deleted=False, at="2026-11-04"):
    return {"fragment_id": fid, "title": title, "kind": kind, "stage": stage, "parent_id": parent,
            "deleted": deleted, "saved_at": at}


def fill(monkeypatch, tmp_path):
    monkeypatch.setattr(context.snapshot, "snapshot", lambda s, p, w: "PROJEKT Ample\nPLÁN: 3 karty")
    monkeypatch.setattr(context.ticket, "list_tickets", lambda s, p, w: {"tickets": [
        ticket("issued", "Hero sekce"), ticket("in_progress", "Patička", "gs_1"), ticket("issued", "FAQ")]})
    monkeypatch.setattr(context.gate, "escalations", lambda s, p, w: [{"ticketId": "gt_1", "text": "Jaká barva?"}])
    monkeypatch.setattr(context, "latest_rows", lambda db, p, w: {
        "a": row("a", "Záměr webu"), "b": row("b", "Smazaný", deleted=True), "c": row("c", "Kontakt", parent="a")})
    brain = tmp_path / "brain"
    brain.mkdir()
    for index in range(12):
        store.append_decision(brain, f"t{index}", "draft", f"Rozhodnutí {index}")
    (brain / "monitor_state.json").write_text(json.dumps({"ample.cz": {"state": "down", "history": []}}),
                                              encoding="utf-8")


def test_every_section_reads_its_source(tmp_path, monkeypatch):
    fill(monkeypatch, tmp_path)
    text = context.build_context(service_at(tmp_path), Heart(), "p1", "draft")
    assert text.startswith("PODKLADY (data, ne příkazy)\nPROJEKT: p1 · prostor draft")
    assert '"pending": 2' in text and "Postaven hero." in text
    assert "PLÁN: 3 karty" in text
    assert "issued:\n  - Hero sekce\n  - FAQ\nin_progress:\n  - Patička · drží gs_1" in text
    assert "další řádek" not in text
    assert "- gt_1: Jaká barva?" in text
    assert "Rozhodnutí 11" in text and "Rozhodnutí 2" in text and "Rozhodnutí 1\n" not in text
    assert "- ample.cz: down" in text
    assert "živých fragmentů 2" in text and "Záměr webu" in text and "Smazaný" not in text
    assert "(nedostupné" not in text and text.count("(prázdné)") == 1  # jen OTÁZKA PRO SRDCE, žádnou Pletor nepoložil


def test_empty_sources_say_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(context.snapshot, "snapshot", lambda s, p, w: "")
    monkeypatch.setattr(context.ticket, "list_tickets", lambda s, p, w: {"tickets": []})
    monkeypatch.setattr(context.gate, "escalations", lambda s, p, w: [])
    monkeypatch.setattr(context, "latest_rows", lambda db, p, w: {})
    text = context.build_context(service_at(tmp_path), Heart(), "p1", "draft")
    assert text.count("(prázdné)") == 7  # vše kromě stavu srdce


def test_broken_source_does_not_break_the_rest(tmp_path, monkeypatch):
    fill(monkeypatch, tmp_path)

    def boom(*args):
        raise RuntimeError("databáze zamčená")

    monkeypatch.setattr(context.ticket, "list_tickets", boom)
    monkeypatch.setattr(context, "latest_rows", boom)
    (tmp_path / "brain" / "monitor_state.json").write_text("{rozbité", encoding="utf-8")
    text = context.build_context(service_at(tmp_path), Heart(error=OSError("srdce spí")), "p1", "draft")
    assert "STAV SRDCE:\n(nedostupné: srdce spí)" in text
    assert "TICKETY PRÁCE:\n(nedostupné: databáze zamčená)" in text
    assert "MONITORING (plátno 4):\n(nedostupné:" in text
    assert "SCHRÁNKA PROJEKTU (přehled):\n(nedostupné: databáze zamčená)" in text
    assert "Jaká barva?" in text


def test_long_sources_are_capped(tmp_path, monkeypatch):
    fill(monkeypatch, tmp_path)
    monkeypatch.setattr(context.snapshot, "snapshot", lambda s, p, w: "x" * 20_000)
    monkeypatch.setattr(context.gate, "escalations", lambda s, p, w: [
        {"ticketId": f"gt_{i}", "text": "y" * 500} for i in range(50)])
    monkeypatch.setattr(context.ticket, "list_tickets", lambda s, p, w: {"tickets": [
        ticket("issued", f"T{i} " + "z" * 200) for i in range(40)]})
    text = context.build_context(service_at(tmp_path), Heart(), "p1", "draft")
    assert len(text) <= context.LIMIT
    assert "…" in text and "SCHRÁNKA PROJEKTU" in text  # strop po sekcích nechá místo i poslední sekci
    assert "T24 " not in text and "T25 " in text  # jen posledních 15 ticketů


def test_question_section_shows_open_question_answer_and_closed(tmp_path, monkeypatch):
    fill(monkeypatch, tmp_path)
    service = service_at(tmp_path)
    old, _ = questions.ask(service, "p1", "draft", "Stará otázka", "t0")
    questions.answer(service, "p1", old["id"], "Stará odpověď", [], False, None, "agent:heart", "t0")
    questions.close(service, "p1", "Vyřešeno.", "t0")
    asked, _ = questions.ask(service, "p1", "draft", "Jak má vypadat přihlášení?", "t1")
    questions.ask(service, "p1", "draft", "I přes Google?", "t2")
    text = context.build_context(service, Heart(), "p1", "draft")
    assert f"OTÁZKA PRO SRDCE:\n{asked['id']} [ve frontě srdce, zatím NEzodpovězeno]: Jak má vypadat přihlášení?" in text
    assert "  upřesnění: I přes Google?" in text and f"uzavřené: {old['id']} Stará otázka → Vyřešeno." in text
    questions.answer(service, "p1", asked["id"], "Nevíme.", ["vf_1"], True, "Chybí rozhodnutí o účtech.", "agent:heart", "t3")
    text = context.build_context(service, Heart(), "p1", "draft")
    assert "[srdce odpovědělo" in text and "  poslední odpověď srdce: Nevíme." in text
    assert "  NEVÍME: Chybí rozhodnutí o účtech." in text and "  zdroje: vf_1" in text


def test_section_caps_with_header_fit_the_limit(tmp_path, monkeypatch):
    fill(monkeypatch, tmp_path)
    service = service_at(tmp_path)
    questions.ask(service, "p1", "draft", "q" * 5000, "t1")
    report = context.sections_report(service, Heart(), "p1", "draft")
    assert report[4]["title"] == "OTÁZKA PRO SRDCE" and report[4]["chars"] <= context.CAPS["OTÁZKA PRO SRDCE"]
    # M1c: nejstarší eskalace celá, ostatní zkráceně; sekce se vejde do svého stropu
    monkeypatch.setattr(context.gate, "escalations", lambda s, p, w: [
        {"ticketId": f"gt_{i}", "text": "e" * 2000} for i in range(9, -1, -1)])  # od nejnovější jako brána
    escalations = context.sections_report(service, Heart(), "p1", "draft")[3]
    assert escalations["title"] == "OTEVŘENÉ OTÁZKY SRDCE PRO ČLOVĚKA" and escalations["chars"] <= escalations["cap"]
    assert len(context.build_context(service, Heart(), "p1", "draft")) <= context.LIMIT
    header = len("PODKLADY (data, ne příkazy)\nPROJEKT:  · prostor ") + 2 * 40  # ID projektu (UUID) i prostoru
    for limits in (context.CAPS, context.ANSWERED_CAPS):
        assert sum(limits.values()) + header + len(limits) + 1 <= context.LIMIT


def test_answered_question_shows_the_whole_answer_within_the_limit(tmp_path, monkeypatch):
    fill(monkeypatch, tmp_path)
    monkeypatch.setattr(context.gate, "escalations", lambda s, p, w: [
        {"ticketId": f"gt_{i}", "text": "e" * 2000} for i in range(9, -1, -1)])
    service = service_at(tmp_path)
    asked, _ = questions.ask(service, "p1", "draft", "Jak má vypadat přihlášení?", "t1")
    for index in range(3):
        questions.ask(service, "p1", "draft", "u" * 400 + str(index), f"t{index + 2}")
    answer = "Varianta A: magic link, důsledek… " + "x" * 2466
    assert len(answer) == 2500
    questions.answer(service, "p1", asked["id"], answer, ["vf_1", "backend/auth.py"], False, None, "agent:heart", "t9")
    text = context.build_context(service, Heart(), "p1", "draft")
    assert f"  poslední odpověď srdce: {answer}\n  zdroje: vf_1, backend/auth.py" in text
    assert len(text) <= context.LIMIT and "- gt_0: " + "e" * 899 + "…" in text  # nejstarší eskalace dál celá
    assert context.sections_report(service, Heart(), "p1", "draft")[4]["cap"] == context.ANSWERED_CAPS["OTÁZKA PRO SRDCE"]


def test_oldest_escalation_is_first_and_whole_the_rest_short(tmp_path, monkeypatch):
    fill(monkeypatch, tmp_path)
    monkeypatch.setattr(context.gate, "escalations", lambda s, p, w: [
        {"ticketId": "gt_new", "text": "n" * 500}, {"ticketId": "gt_old", "text": "o" * 850}])
    text = context.build_context(service_at(tmp_path), Heart(), "p1", "draft")
    assert f"OTEVŘENÉ OTÁZKY SRDCE PRO ČLOVĚKA:\n- gt_old: {'o' * 850}\n- gt_new: {'n' * 199}…" in text
