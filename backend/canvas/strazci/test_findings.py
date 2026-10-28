"""Diff nálezů strážce: nový → guard.alert, trvající → last_seen, zmizelý → guard.resolved; retence 14 dní."""
import json

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.strazci import findings
from database.repositories.guard_findings import GuardFindings

NOW = 1_800_000_000.0


@pytest.fixture
def service(tmp_path):
    instance = CanvasService(tmp_path / "data")
    yield instance
    instance.close()


def item(key, severity="warn", **extra):
    return {"key": key, "rule": "map.test", "severity": severity, "message": f"Nález {key}", **extra}


def events(service):
    rows = service.db_for("draft").execute(
        "SELECT kind, workspace_id, node_id, actor_kind, actor_name, data FROM opora_events"
        " WHERE kind LIKE 'guard.%' ORDER BY id").fetchall()
    return [(row[0], row[1], row[2], row[3], row[4], json.loads(row[5]).get("key") or json.loads(row[5])["rule"])
            for row in rows]


def event_data(service):
    rows = service.db_for("draft").execute("SELECT data FROM opora_events WHERE kind LIKE 'guard.%' ORDER BY id").fetchall()
    return [json.loads(row[0]) for row in rows]


def stored(service, open_only=True):
    return GuardFindings(service.db_for("draft"), "draft").list(open_only=open_only)


def test_diff_splits_new_ongoing_and_resolved():
    assert findings.diff({"a", "b"}, ["b", "c"]) == (["c"], ["b"], ["a"])
    assert findings.diff(set(), []) == ([], [], [])


def test_new_finding_is_stored_and_told_once(service):
    findings.apply(service, "draft", "mapa", [item("k0")], NOW - 30)  # první běh = jeden souhrn „baseline“
    findings.apply(service, "draft", "mapa", [], NOW - 10)
    first = findings.apply(service, "draft", "mapa", [item("k1", nodeId="n1", workspaceId="main")], NOW)
    second = findings.apply(service, "draft", "mapa", [item("k1", nodeId="n1", workspaceId="main")], NOW + 60)
    assert first == {"new": ["k1"], "ongoing": [], "resolved": []}
    assert second == {"new": [], "ongoing": ["k1"], "resolved": []}
    assert events(service)[-1] == ("guard.alert", "main", "n1", "system", "strazce:mapa", "k1")
    assert [kind for kind, *_ in events(service)] == ["guard.alert", "guard.resolved", "guard.alert"]
    [row] = stored(service)
    assert row["firstSeen"] == findings.at_of(NOW) and row["lastSeen"] == findings.at_of(NOW + 60)
    assert row["workspaceId"] == "main" and row["resolvedAt"] is None and row["guard"] == "mapa"


def test_vanished_finding_is_resolved_and_a_return_reopens_it(service):
    findings.apply(service, "draft", "mapa", [item("k1"), item("k2", "block")], NOW)
    assert findings.apply(service, "draft", "mapa", [item("k2", "block")], NOW + 1)["resolved"] == ["k1"]
    assert [row["key"] for row in stored(service)] == ["k2"]
    assert findings.apply(service, "draft", "mapa", [item("k1"), item("k2", "block")], NOW + 2)["new"] == ["k1"]
    assert [(kind, key) for kind, *_, key in events(service)] == [
        ("guard.alert", "baseline"), ("guard.resolved", "k1"), ("guard.alert", "k1")]
    reopened = next(row for row in stored(service) if row["key"] == "k1")
    assert reopened["firstSeen"] == findings.at_of(NOW + 2) and reopened["resolvedAt"] is None


def test_first_run_is_one_baseline_summary_not_a_flood(service):
    found = [item(f"k{index}", "block" if index < 3 else "warn", nodeId=f"n{index}") for index in range(30)]
    assert len(findings.apply(service, "draft", "mapa", found, NOW)["new"]) == 30
    [data] = event_data(service)
    assert data["rule"] == "baseline" and data["guard"] == "mapa" and data["count"] == 30
    assert data["bySeverity"] == {"block": 3, "warn": 27, "info": 0} and data["severity"] == "block"
    assert len(stored(service)) == 30


def test_batch_over_twenty_new_findings_is_one_summary(service):
    findings.apply(service, "draft", "prace", [item("k0")], NOW)
    findings.apply(service, "draft", "prace", [item("k0"), *[item(f"x{index}") for index in range(21)]], NOW + 1)
    findings.apply(service, "draft", "prace", [item("k0"), *[item(f"x{index}") for index in range(21)], item("y")], NOW + 2)
    assert [(data.get("rule"), data.get("key"), data.get("count")) for data in event_data(service)] == [
        ("baseline", None, 1), ("batch", None, 21), ("map.test", "y", None)]


def test_twenty_new_findings_are_still_told_one_by_one(service):
    findings.apply(service, "draft", "prace", [item("k0")], NOW)
    findings.apply(service, "draft", "prace", [item("k0"), *[item(f"x{index}") for index in range(20)]], NOW + 1)
    assert len(event_data(service)) == 21 and "count" not in event_data(service)[-1]


def test_other_guards_findings_are_untouched(service):
    findings.apply(service, "draft", "mapa", [item("map:1")], NOW)
    findings.apply(service, "draft", "prace", [], NOW + 1)
    assert [row["key"] for row in stored(service)] == ["map:1"]


def test_resolved_findings_older_than_14_days_are_deleted(service):
    findings.apply(service, "draft", "mapa", [item("k1")], NOW)
    findings.apply(service, "draft", "mapa", [], NOW + 1)
    assert len(stored(service, open_only=False)) == 1
    findings.apply(service, "draft", "mapa", [], NOW + 14 * 86400 + 2)
    assert stored(service, open_only=False) == []


def test_blocking_findings_are_listed_first(service):
    findings.apply(service, "draft", "mapa", [item("a", "info"), item("b", "block"), item("c", "warn")], NOW)
    assert [row["severity"] for row in stored(service)] == ["block", "warn", "info"]


@pytest.mark.parametrize("bad", [None, "x", [{"key": "", "rule": "r", "severity": "warn", "message": "m"}],
                                 [{"key": "k", "rule": "r", "severity": "fatal", "message": "m"}],
                                 [{"key": "k", "rule": "r", "severity": "warn", "message": "m", "guard": "jiny"}]])
def test_invalid_output_is_refused_without_writing(service, bad):
    with pytest.raises(ValueError):
        findings.apply(service, "draft", "mapa", bad, NOW)
    assert stored(service, open_only=False) == []
