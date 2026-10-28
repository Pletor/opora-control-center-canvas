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
    return [(row[0], row[1], row[2], row[3], row[4], json.loads(row[5])["key"]) for row in rows]


def stored(service, open_only=True):
    return GuardFindings(service.db_for("draft"), "draft").list(open_only=open_only)


def test_diff_splits_new_ongoing_and_resolved():
    assert findings.diff({"a", "b"}, ["b", "c"]) == (["c"], ["b"], ["a"])
    assert findings.diff(set(), []) == ([], [], [])


def test_new_finding_is_stored_and_told_once(service):
    first = findings.apply(service, "draft", "mapa", [item("k1", nodeId="n1", workspaceId="main")], NOW)
    second = findings.apply(service, "draft", "mapa", [item("k1", nodeId="n1", workspaceId="main")], NOW + 60)
    assert first == {"new": ["k1"], "ongoing": [], "resolved": []}
    assert second == {"new": [], "ongoing": ["k1"], "resolved": []}
    assert events(service) == [("guard.alert", "main", "n1", "system", "strazce:mapa", "k1")]
    [row] = stored(service)
    assert row["firstSeen"] == findings.at_of(NOW) and row["lastSeen"] == findings.at_of(NOW + 60)
    assert row["workspaceId"] == "main" and row["resolvedAt"] is None and row["guard"] == "mapa"


def test_vanished_finding_is_resolved_and_a_return_reopens_it(service):
    findings.apply(service, "draft", "mapa", [item("k1"), item("k2", "block")], NOW)
    assert findings.apply(service, "draft", "mapa", [item("k2", "block")], NOW + 1)["resolved"] == ["k1"]
    assert [row["key"] for row in stored(service)] == ["k2"]
    assert findings.apply(service, "draft", "mapa", [item("k1"), item("k2", "block")], NOW + 2)["new"] == ["k1"]
    assert [kind for kind, *_ in events(service)] == ["guard.alert", "guard.alert", "guard.resolved", "guard.alert"]
    reopened = next(row for row in stored(service) if row["key"] == "k1")
    assert reopened["firstSeen"] == findings.at_of(NOW + 2) and reopened["resolvedAt"] is None


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
