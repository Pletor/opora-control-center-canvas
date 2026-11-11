"""Spouštěče karet a ruční změny plánu (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): pevná tabulka nad měřákem,
mediány z hotových karet, probuzení jednou na stav (`heart_triggers`)."""
import json

import pytest

from backend.brain_opora.determinism import triggers
from backend.canvas.canvas_service import CanvasService


def card(**extra):
    return {"nodeId": "n1", "title": "Přihlášení", "workspace": "w1", "status": "ready", "label": "S",
            "evidence": "ok", "points": 5.0, "effort": "medium", "failures": 0, "failedRun": None, "runId": None,
            "age": None, "sinceStep": None, "costUsd": None, **extra}


def done(label="S", count=5, seconds=600, cost=None):
    return [{"label": label, "seconds": seconds, "costUsd": cost} for _ in range(count)]


def kinds(found):
    return [hit["kind"] for hit in found]


def test_too_big_only_for_a_ready_xl_card_with_evidence():
    hit = triggers.too_big(card(label="XL", points=17.5))
    assert hit["detail"] == "XL (17.5 b.), nepředávat, rozděl"
    assert triggers.card_key(hit) == "trigger:card:n1:too_big:XL17.5@w1"
    assert triggers.too_big(card(label="?", evidence="thin", points=20)) is None  # chudé podklady nepouští
    assert triggers.too_big(card(label="XL", status="running")) is None
    assert triggers.too_big(card(label="L")) is None


def test_retry_after_second_failure_recommends_one_effort_higher_and_new_failure_is_a_new_state():
    assert triggers.retry(card(failures=1, failedRun="e1")) is None
    hit = triggers.retry(card(failures=2, failedRun="e2"))
    assert hit["detail"] == "2× selhal, doporučeno effort high"
    assert triggers.card_key(hit) == "trigger:card:n1:retry:e2"
    assert triggers.card_key(triggers.retry(card(failures=3, failedRun="e3"))) == "trigger:card:n1:retry:e3"
    assert triggers.retry(card(failures=2, failedRun="e2", effort="max"))["detail"].endswith("effort max")
    assert triggers.retry(card(failures=2, failedRun="e2", effort=None, label="XL"))["detail"].endswith("rozděl kartu")


def broken(run="e5", pulled=False, notes="migrace 0042 je obsazena (poslední 0048)"):
    return card(status="reported", stepFailed={"runId": run, "stepId": "s1", "notes": notes, "pulled": pulled})


def test_step_failed_wakes_on_a_delivered_run_with_a_failed_step_and_without_a_pull_request():
    hit = triggers.step_failed(broken())
    assert triggers.card_key(hit) == "trigger:card:n1:step_failed:e5"
    assert hit["detail"].startswith("krok s1 selhal (běh e5): migrace 0042 je obsazena (poslední 0048) — zadání koliduje")
    assert "fields.steps" in hit["detail"] and "poslední na main + 1" in hit["detail"]
    assert triggers.step_failed(broken(pulled=True)) is None  # běh s PR čeká na review PR
    assert triggers.step_failed(card(status="reported")) is None  # žádný krok nehlásil failed
    long = triggers.step_failed(broken(notes="x " * 500))["detail"]
    assert "x " * 199 + "x…" in long and "x " * 201 not in long  # poznámka zkrácená na 400 znaků
    assert triggers.retry(card(status="reported", failures=2, failedRun="e2")) is None  # výsledek odevzdán


def test_stalled_needs_history_of_five_done_cards_with_the_same_label():
    slow = card(status="running", runId="e7", age=2000, sinceStep=None)
    assert triggers.evaluate([slow], done(count=4)) == []  # bez historie neběží
    assert triggers.evaluate([slow], done(label="M")) == []  # jiný štítek
    [hit] = triggers.evaluate([slow], done())
    assert (hit["kind"], hit["state"]) == ("card.stalled", "e7")
    assert hit["detail"] == "běží 33 min (medián S 10 min), bez kroku"
    assert triggers.evaluate([card(status="running", runId="e7", age=1700)], done()) == []  # pod 3× medián
    assert triggers.evaluate([{**slow, "sinceStep": 300}], done()) == []  # krok se pohnul


def test_over_budget_waits_for_the_price():
    expensive = card(status="running", runId="e7", age=10, costUsd=None)
    assert triggers.evaluate([expensive], done(cost=None)) == []  # cena zatím chybí (null)
    assert triggers.evaluate([{**expensive, "costUsd": 2.5}], done(cost=None)) == []  # chybí medián ceny
    [hit] = triggers.evaluate([{**expensive, "costUsd": 2.5}], done(cost=1.0))
    assert (hit["kind"], hit["detail"]) == ("card.over_budget", "2.50 USD, medián 1.00 USD")
    assert triggers.evaluate([{**expensive, "costUsd": 2.0}], done(cost=1.0)) == []


def use(identifier, action=None, target=None, state="progress", name="Edit"):
    """`tool.use` karty, jak ho čte `facts` (`opora_events.tool_uses`)."""
    tool = {"name": name, **({"action": action} if action else {}), **({"target": target} if target else {})}
    return {"id": identifier, "state": state, "tool": tool}


def test_failing_from_the_office_streak_or_three_same_failures_in_a_row():
    """Kancelář hlásí sérii `action: failing` (její failStreak); jinak 3× stejný nástroj a cíl `fail` v řadě."""
    office = card(tools=[use(9, "edit", "src/a.ts"), use(8, "failing", state="fail", name="tests"), use(7, "test")])
    hit = triggers.failing(office)
    assert triggers.card_key(hit) == "trigger:card:n1:failing:8" and hit["detail"].startswith("tests opakovaně")
    three = [use(index, "test", "npm test", "fail", "Bash") for index in (5, 4, 3)]
    assert triggers.card_key(triggers.failing(card(tools=three))) == "trigger:card:n1:failing:5"
    assert triggers.failing(card(tools=three[:2] + [use(2, "test", "npm run build", "fail", "Bash")])) is None
    assert triggers.failing(card(tools=[use(1, "test", "npm test", "progress", "Bash")])) is None
    assert triggers.failing(card()) is None


def test_drift_is_an_edit_outside_the_card_files_and_a_card_without_files_has_none():
    expected = ["backend/canvas/", "backend/canvas//", "docs/a.md", "docs/a.md/"]
    inside = [use(1, "edit", r"C:\wt\backend\canvas\x.py"), use(2, "edit", "docs/a.md"), use(3, "read", "frontend/x.ts")]
    assert triggers.drift(card(tools=inside, expected=expected)) is None
    away = card(tools=[*inside, use(4, "edit", "frontend/app.tsx"), use(5, "edit", "/home/w/wt/frontend/app.tsx")],
                expected=expected)
    hit = triggers.drift(away)
    assert hit["kind"] == "card.drift" and "frontend/app.tsx" in hit["detail"]
    assert triggers.card_key(hit) == triggers.card_key(triggers.drift(away))  # stejné soubory = stejný stav
    more = card(tools=[*away["tools"], use(6, "edit", "README.md")], expected=expected)
    assert triggers.card_key(triggers.drift(more)) != triggers.card_key(hit)  # nový soubor mimo budí znovu
    assert triggers.drift(card(tools=away["tools"], expected=[])) is None  # karta bez očekávání drift nemá
    assert triggers.drift(card(tools=[use(7, "edit", "C:/Users/Admin/AppData/Local/very/long/clipped/pat…")],
                               expected=expected)) is None  # zkrácený cíl se nehodnotí


def test_collision_on_conflict_or_impact_on_a_card_with_open_work():
    """F4: konflikt sloučení, nebo dopad na kartu s vlastní otevřenou prací nad stejnými soubory; stejná kolize =
    stejný stav. Propojená karta s otevřenou prací bez společných souborů dopad ani překryv nemá, takže nic."""
    clean = {"verdict": "warning", "works": [{"conflicts": [], "impacts": [{"nodeId": "n2"}], "overlaps": []}]}
    assert triggers.collision(card()) is None and triggers.collision(card(future=clean)) is None
    other = {"verdict": "warning", "works": [{"conflicts": [], "impacts": [{"nodeId": "n2"}],
                                              "overlaps": [{"nodeId": "n3", "paths": ["a.py"]}]}]}
    assert triggers.collision(card(future=other)) is None  # překryv s nezasaženou kartou kolize není
    blocked = card(future={"verdict": "blocked", "works": [{"conflicts": ["a.py"], "impacts": [], "overlaps": []}]})
    hit = triggers.collision(blocked)
    assert hit["kind"] == "card.collision" and "konfliktem v a.py" in hit["detail"]
    assert triggers.card_key(hit) == triggers.card_key(triggers.collision(blocked))
    shared = {"verdict": "warning", "works": [{"conflicts": [], "impacts": [{"nodeId": "n2"}],
                                               "overlaps": [{"nodeId": "n2", "paths": ["a.py"]}]}]}
    touched = triggers.collision(card(future=shared))
    assert "n2" in touched["detail"] and triggers.card_key(touched) != triggers.card_key(hit)
    assert "card.collision" in triggers.WATCH


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.db_for("draft")
    yield canvas
    canvas.close()


def test_wakes_once_per_state_and_a_new_failure_wakes_again(service, monkeypatch):
    state = {"cards": [card(failures=2, failedRun="e2"), card(nodeId="n2", label="XL", points=16)]}
    monkeypatch.setattr(triggers, "facts", lambda *args: (state["cards"], []))
    first = triggers.wakes(service, "draft", {"w1"}, "t1", 0)
    assert [item["kind"] for _, item in first] == ["card.retry", "card.too_big"]
    assert first[0] == ("w1", {"type": "cardTrigger", "kind": "card.retry", "nodeId": "n1", "title": "Přihlášení",
                               "detail": "2× selhal, doporučeno effort high"})
    assert triggers.wakes(service, "draft", {"w1"}, "t2", 0) == []  # stejný stav nebudí
    state["cards"] = [card(failures=3, failedRun="e3")]
    assert [item["detail"] for _, item in triggers.wakes(service, "draft", {"w1"}, "t3", 0)] == [
        "3× selhal, doporučeno effort high"]


def test_fired_signal_lands_in_the_card_log_with_its_actor(service, monkeypatch):
    """Vystřelený spouštěč zapíše `card.signal`: hlídač u failing/drift/stalled, trigger u ostatních; jednou na stav."""
    from database.repositories import opora_events

    cards = [card(tools=[use(8, "failing", state="fail", name="tests")]), card(nodeId="n2", label="XL", points=16)]
    monkeypatch.setattr(triggers, "facts", lambda *args: (cards, []))
    assert [item["kind"] for _, item in triggers.wakes(service, "draft", {"draft"}, "t1", 0)] == [
        "card.failing", "card.too_big"]
    triggers.wakes(service, "draft", {"draft"}, "t2", 0)
    events, _, _ = opora_events.page(service.db_for("draft"), "draft", "draft", 0, 50)
    assert [(event["kind"], event["nodeId"], event["actor"]["name"], event["data"]["signal"]) for event in events] == [
        ("card.signal", "n1", "hlídač", "card.failing"), ("card.signal", "n2", "trigger", "card.too_big")]
    assert events[0]["title"].startswith("card.failing: tests opakovaně selhává")


def test_step_failed_wakes_once_per_run_and_a_new_failed_run_wakes_again(service, monkeypatch):
    state = {"cards": [broken("e5")]}
    monkeypatch.setattr(triggers, "facts", lambda *args: (state["cards"], []))
    [(space, item)] = triggers.wakes(service, "draft", {"w1"}, "t1", 0)
    assert (space, item["kind"], item["nodeId"]) == ("w1", "card.step_failed", "n1")
    assert triggers.wakes(service, "draft", {"w1"}, "t2", 0) == []  # stejný běh podruhé nebudí
    state["cards"] = [broken("e6")]
    assert [item["detail"][:22] for _, item in triggers.wakes(service, "draft", {"w1"}, "t3", 0)] == [
        "krok s1 selhal (běh e6"]
    state["cards"] = [broken("e7", pulled=True), card(status="reported")]
    assert triggers.wakes(service, "draft", {"w1"}, "t4", 0) == []  # s PR ani bez failed nebudí


def test_wakes_without_an_accepted_plan_reads_nothing(service):
    assert triggers.wakes(service, "draft", None, "t", 0) == []


def revision(db, identifier, kind, created):
    record = {"id": identifier, "by": {"kind": kind, "name": "x"}, "createdAt": created, "subject": "Plán"}
    db.execute("INSERT INTO opora_spec_revisions VALUES('draft','draft',?,NULL,?,?,?)",
               (identifier, "p" + identifier, created, json.dumps(record)))


def test_human_change_wakes_once_per_revision_accepted_by_a_human_only(service):
    db = service.db_for("draft")
    with db:
        revision(db, "r1", "agent", "2026-10-30T10:00:00Z")
        revision(db, "r2", "human", "2026-10-30T11:00:00Z")
        assert triggers.human_change(db, "draft", "draft", "r1", "t") is None  # přijetí srdcem nebudí
        assert triggers.human_change(db, "draft", "draft", "r2", "t") == {
            "type": "humanChange", "kind": "graph.human_change", "revision": 2, "revisionId": "r2", "subject": "Plán"}
        assert triggers.human_change(db, "draft", "draft", "r2", "t") is None  # jednou na revizi
        assert triggers.human_change(db, "draft", "draft", "missing", "t") is None
