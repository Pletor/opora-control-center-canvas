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
