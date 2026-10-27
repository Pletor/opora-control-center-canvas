"""Doklad přehrání cesty (`docs/brana-cesty.md` §3–§4): validace, odvozené `passed`, append-only zápis a `lastRun`."""

import copy
import sqlite3
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from backend.project.architecture.journey_plan import JourneyBroken, JourneyNotFound, journey_plan
from backend.project.architecture.journey_runs import (
    VERIFICATION,
    JourneyRunInvalid,
    last_run,
    last_runs,
    latest_journey_runs,
    project_journeys,
    record_journey_run,
    validate_run,
)
from database.schema.journey_run_schema import SCHEMA as JOURNEY_RUN_SCHEMA


def node(identifier, parent=None, kind="node", **extra):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier, "purpose": "", "x": 0, "y": 0,
            **extra}


def page(identifier, path):
    return node(identifier, "web", site={"kind": "page", "path": path})


JOURNEYS = [{"id": "kampan", "name": "Kampaň", "steps": [
                {"id": "s1", "page": "home"}, {"id": "s2", "page": "novinky", "via": {"do": "click", "text": "Novinky"}},
                {"id": "s3", "page": "pribeh"}]},
            {"id": "rozbita", "name": "Rozbitá", "steps": [{"id": "a", "page": "nav"}, {"id": "b", "page": "smazana"}]}]


def make_graph():
    return {"nodes": [node("web", kind="sector", site={"kind": "application", "journeys": copy.deepcopy(JOURNEYS),
                                                       "environments": [{"name": "Dev", "host": "localhost:3000"}]}),
                      page("home", "/"), page("novinky", "/novinky"), page("pribeh", "/pribeh")],
            "edges": []}


def make_service(graph):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(JOURNEY_RUN_SCHEMA)
    return SimpleNamespace(project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourceKind": "git"}}),
                           view=lambda project, wid: {"graph": graph}, db_for=lambda project: db,
                           reading=lambda project: nullcontext(), lock_for=lambda project: threading.RLock())


def run(digest, at="2026-10-27T21:40:00Z", s2=True, s3=True, **extra):
    return {"schema": "opora.journey-run/1", "applicationId": "web", "journeyId": "kampan", "planDigest": digest,
            "command": "uv run python tools/journey_run.py --journey kampan", "at": at,
            "segments": [{"from": "s1", "to": "s2", "ok": s2},
                         {"from": "s2", "to": "s3", "ok": s3, **({} if s3 else {"reason": "URL /novinky, čekáno /pribeh"})}],
            **extra}


@pytest.fixture
def plan():
    return journey_plan(make_graph(), "kampan")


def test_passed_is_derived_from_all_planned_segments_being_ok(plan):
    record, at_utc = validate_run(run(plan["digest"], logUrl="https://ci/1"), plan)
    assert record["passed"] is True and record["verification"] == VERIFICATION and record["logUrl"] == "https://ci/1"
    assert at_utc == "2026-10-27T21:40:00.000000+00:00"
    assert validate_run(run(plan["digest"], s3=False), plan)[0]["passed"] is False
    partial = run(plan["digest"])
    partial["segments"] = partial["segments"][:1]
    assert validate_run(partial, plan)[0]["passed"] is False
    sent_passed = run(plan["digest"], s3=False)
    sent_passed["passed"] = True
    with pytest.raises(JourneyRunInvalid, match="passed"):
        validate_run(sent_passed, plan)


@pytest.mark.parametrize("change", [
    {"schema": "opora.journey-run/2"}, {"planDigest": "sha256:abc"}, {"planDigest": "md5:" + "0" * 64},
    {"command": ""}, {"command": "x" * 501}, {"at": "včera"}, {"segments": []},
    {"segments": [{"from": "s1", "to": "s2", "ok": True}] * 31}, {"segments": [{"from": "s1", "to": "s2", "ok": "ano"}]},
    {"segments": [{"from": "s1", "to": "s3", "ok": True}]}, {"segments": [{"from": "s1", "to": "s2", "ok": True}] * 2},
    {"segments": [{"from": "s1", "to": "s2", "ok": False, "reason": "x" * 301}]},
    {"segments": [{"from": "s1", "to": "s2", "ok": True, "extra": 1}]}, {"logUrl": "x" * 501}, {"logUrl": 5},
    {"applicationId": None}])
def test_shape_errors_are_rejected(plan, change):
    with pytest.raises(JourneyRunInvalid):
        validate_run({**run(plan["digest"]), **change}, plan)


def test_last_run_counts_failures_names_the_first_and_marks_stale(plan):
    record, _ = validate_run(run(plan["digest"], s2=False, s3=False), plan)
    assert last_run(record, plan["digest"]) == {
        "at": "2026-10-27T21:40:00Z", "passed": False, "stale": False, "command": record["command"], "failed": 2,
        "firstFailure": {"from": "s1", "to": "s2"}}
    ok, _ = validate_run(run(plan["digest"]), plan)
    assert last_run(ok, "sha256:" + "0" * 64) == {"at": ok["at"], "passed": True, "stale": True,
                                                  "command": ok["command"], "failed": 0}


def test_record_is_append_only_and_latest_wins_by_at_then_by_insert_order(plan):
    graph = make_graph()
    service = make_service(graph)
    first = record_journey_run(service, "p1", run(plan["digest"], at="2026-10-27T22:00:00+01:00", s3=False))
    record_journey_run(service, "p1", run(plan["digest"], at="2026-10-27T20:00:00Z"))  # starší běh, uložený později
    assert first["recordedAt"] and first["passed"] is False
    latest = latest_journey_runs(service, "p1")
    assert list(latest) == [("web", "kampan")] and latest[("web", "kampan")]["segments"][1]["ok"] is False
    record_journey_run(service, "p1", run(plan["digest"], at="2026-10-27T21:00:00Z"))  # stejný čas, později uložený
    assert latest_journey_runs(service, "p1")[("web", "kampan")]["passed"] is True
    db = service.db_for("p1")
    assert db.execute("SELECT COUNT(*) FROM journey_runs").fetchone()[0] == 3
    with pytest.raises(sqlite3.DatabaseError, match="Immutable journey run"):
        db.execute("UPDATE journey_runs SET passed=1")
    with pytest.raises(sqlite3.DatabaseError, match="Immutable journey run"):
        db.execute("DELETE FROM journey_runs")


def test_record_needs_an_existing_unbroken_journey(plan):
    service = make_service(make_graph())
    with pytest.raises(JourneyNotFound):
        record_journey_run(service, "p1", {**run(plan["digest"]), "journeyId": "jina"})
    with pytest.raises(JourneyBroken):
        record_journey_run(service, "p1", {**run(plan["digest"]), "journeyId": "rozbita",
                                           "segments": [{"from": "a", "to": "b", "ok": True}]})
    with pytest.raises(JourneyRunInvalid):
        record_journey_run(service, "p1", ["není objekt"])


def test_journeys_carry_last_run_only_when_a_run_exists_and_stale_follows_the_map(plan):
    graph = make_graph()
    service = make_service(graph)
    assert all("lastRun" not in item for item in project_journeys(service, "p1")["journeys"])
    record_journey_run(service, "p1", run(plan["digest"]))
    kampan, rozbita = project_journeys(service, "p1")["journeys"]
    assert kampan["lastRun"]["passed"] is True and kampan["lastRun"]["stale"] is False and "lastRun" not in rozbita
    graph["nodes"][3]["site"]["path"] = "/aktuality"
    assert project_journeys(service, "p1")["journeys"][0]["lastRun"]["stale"] is True
    assert last_runs(graph, {}) == {}
