import pytest

from backend.canvas.sync_signals import collect, evaluate


def scope(scope_id, kind="node", parent=None, path=None, origin="existing", path_kind="file",
          revision=0, saved=None, checks=True, closed=False):
    ref = {"origin": origin, "path": path, "kind": path_kind} if path else None
    return {"kind": kind, "id": scope_id, "name": scope_id, "parentId": parent, "sourceRef": ref,
            "specRevision": revision, "specSavedAt": saved, "checksGreen": checks, "closed": closed}


def state(**over):
    base = {"observedAt": "2026-09-17T10:00:00", "gitHead": "abc1234", "scopes": [], "paths": {},
            "pairs": {}, "unclaimedCommits": [], "workspaces": [], "docIssues": []}
    base.update(over)
    return base


def pair(revision=1, merged=True, last="2026-09-17T09:00:00", touches=True):
    return {"oporaCommit": "op1", "revisionInCode": revision, "mergedToMain": merged,
            "touchesOwned": touches, "lastCommitAt": last, "confidence": "strong"}


def missing(kind=None, renamed=None):
    return {"exists": False, "kind": kind, "renamedTo": renamed}


def here(kind="file"):
    return {"exists": True, "kind": kind, "renamedTo": None}


# Jeden případ na každý typ echa, který tento krok počítá; závažnost je z části 7 kontraktu.
CASES = [
    ("source-missing", "high", state(
        scopes=[scope("n1", path="backend/a.py")], paths={"backend/a.py": missing()})),
    ("source-missing", "high", state(
        scopes=[scope("n1", path="backend/a.py")], paths={"backend/a.py": here("directory")})),
    ("source-renamed", "medium", state(
        scopes=[scope("n1", path="backend/a.py")],
        paths={"backend/a.py": missing(renamed="backend/b.py")})),
    ("planned-exists", "low", state(
        scopes=[scope("n1", path="backend/new.py", origin="planned")],
        paths={"backend/new.py": here()})),
    ("duplicate-path", "medium", state(
        scopes=[scope("n1", path="backend/a.py"), scope("n2", path="backend/a.py")],
        paths={"backend/a.py": here()})),
    ("spec-ahead", "high", state(scopes=[scope("n1", revision=2)])),
    ("spec-ahead", "high", state(
        scopes=[scope("n1", revision=2)], pairs={"n1": pair(revision=1)})),
    # Bez traileru rozhoduje čas: commit v mainu je starší než uložené zadání.
    ("spec-ahead", "high", state(
        scopes=[scope("n1", revision=1, saved="2026-09-17T09:30:00")],
        pairs={"n1": pair(revision=None, last="2026-09-16T08:00:00")})),
    ("code-unclaimed", "medium", state(
        unclaimedCommits=[{"sha": "deadbee", "paths": ["backend/a.py"], "date": "2026-09-16"}])),
    ("checks-unknown", "high", state(
        scopes=[scope("n1", checks=False)], pairs={"n1": pair()})),
    ("base-stale", "medium", state(
        scopes=[scope("n1")], workspaces=[{"id": "w1", "nodeId": "n1", "branch": "work/n1",
                                          "baseInMain": False}])),
    ("workspace-orphan", "low", state(
        scopes=[scope("n1")], workspaces=[{"id": "w1", "nodeId": "duch", "branch": "work/x",
                                           "baseInMain": True}])),
    ("doc-path-missing", "medium", state(
        docIssues=[{"doc": "docs/README.md", "line": 12, "path": "backend/pryc.py"}])),
]


@pytest.mark.parametrize("kind,severity,world", CASES, ids=[f"{c[0]}-{i}"
                                                            for i, c in enumerate(CASES)])
def test_each_type_is_recognised_with_its_severity(kind, severity, world):
    signals = collect(world)
    matching = [signal for signal in signals if signal["type"] == kind]
    assert len(matching) == 1, [signal["type"] for signal in signals]
    assert matching[0]["severity"] == severity
    assert matching[0]["action"]
    assert matching[0]["observedAt"] == world["observedAt"]
    assert matching[0]["gitHead"] == world["gitHead"]


def test_existing_source_in_the_right_kind_is_quiet():
    world = state(scopes=[scope("n1", path="backend/a.py")], paths={"backend/a.py": here()})
    assert collect(world) == []


def test_planned_path_that_does_not_exist_is_quiet():
    world = state(scopes=[scope("n1", path="backend/new.py", origin="planned")],
                  paths={"backend/new.py": missing()})
    assert collect(world) == []


def test_duplicate_path_is_reported_once_per_path_with_both_scopes():
    world = state(scopes=[scope("n2", path="backend/a.py"), scope("n1", path="backend/a.py")],
                  paths={"backend/a.py": here()})
    duplicates = [signal for signal in collect(world) if signal["type"] == "duplicate-path"]
    assert len(duplicates) == 1
    assert duplicates[0]["subject"]["path"] == "backend/a.py"
    assert duplicates[0]["subject"]["id"] is None
    assert duplicates[0]["evidence"]["actual"] == "rozsahy: n1, n2"


def test_pair_that_holds_the_current_revision_is_quiet():
    world = state(scopes=[scope("n1", revision=2, saved="2026-09-16T08:00:00")],
                  pairs={"n1": pair(revision=2, last="2026-09-17T09:00:00")})
    assert collect(world) == []


def test_missing_checks_without_a_merged_pair_is_quiet():
    world = state(scopes=[scope("n1", checks=False)])
    assert collect(world) == []
    world = state(scopes=[scope("n1", checks=False)],
                  pairs={"n1": pair(merged=False)})
    assert collect(world) == []


def test_one_signal_per_unclaimed_commit():
    world = state(unclaimedCommits=[{"sha": "aaa", "paths": ["x.py"], "date": "2026-09-16"},
                                    {"sha": "bbb", "paths": ["y.py"], "date": "2026-09-16"}])
    signals = collect(world)
    assert {signal["subject"]["id"] for signal in signals} == {"aaa", "bbb"}


def test_one_signal_per_doc_issue_even_on_the_same_path():
    world = state(docIssues=[{"doc": "docs/a.md", "line": 1, "path": "backend/pryc.py"},
                             {"doc": "docs/b.md", "line": 9, "path": "backend/pryc.py"}])
    assert len(collect(world)) == 2


def test_closed_scope_never_echoes():
    broken = {"backend/a.py": missing()}
    world = state(scopes=[scope("n1", path="backend/a.py", revision=3,
                                checks=False, closed=True)], paths=broken,
                  pairs={"n1": pair(revision=1)})
    assert collect(world) == []


def test_signal_ids_are_stable_and_short():
    world = state(scopes=[scope("n1", path="backend/a.py", revision=2)],
                  paths={"backend/a.py": missing()})
    first, second = collect(world), collect(state(**world))
    assert [signal["id"] for signal in first] == [signal["id"] for signal in second]
    for signal in first:
        assert len(signal["id"]) == 16
        assert int(signal["id"], 16) >= 0


def test_signals_are_sorted_by_type_and_id():
    world = state(scopes=[scope("n1", path="backend/a.py", revision=2),
                          scope("n2", path="backend/a.py", revision=2)],
                  paths={"backend/a.py": missing()},
                  docIssues=[{"doc": "docs/a.md", "line": 1, "path": "x.py"}])
    signals = collect(world)
    assert [(s["type"], s["id"]) for s in signals] == sorted((s["type"], s["id"])
                                                             for s in signals)


def test_empty_state_survives():
    assert evaluate({}) == {"signals": [], "verdicts": []}
    assert evaluate(state()) == {"signals": [], "verdicts": []}


def test_trailer_revision_closes_spec_ahead_even_when_the_commit_is_older():
    # Trailer říká revizi přímo, takže je autoritativní; čas uložení zadání ho nepřebije.
    world = state(scopes=[scope("n1", revision=2, saved="2026-09-17T09:30:00")],
                  pairs={"n1": pair(revision=2, last="2026-09-16T08:00:00")})
    assert [signal["type"] for signal in evaluate(world)["signals"]] == []


def test_commit_dated_in_the_future_is_not_taken_as_proof():
    # Kritik posune hodiny a commitne „do budoucna“, aby kód vypadal novější než zadání.
    world = state(observedAt="2026-09-17T10:00:00",
                  scopes=[scope("n1", revision=1, saved="2026-09-17T09:30:00")],
                  pairs={"n1": pair(revision=None, last="2030-01-01T00:00:00")})
    found = [signal for signal in evaluate(world)["signals"] if signal["type"] == "spec-ahead"]
    assert len(found) == 1
    assert "budoucnosti" in found[0]["evidence"]["actual"]


def test_commit_newer_than_the_spec_closes_spec_ahead_without_a_trailer():
    world = state(observedAt="2026-09-17T10:00:00",
                  scopes=[scope("n1", revision=1, saved="2026-09-17T08:00:00")],
                  pairs={"n1": pair(revision=None, last="2026-09-17T09:00:00")})
    assert [signal["type"] for signal in evaluate(world)["signals"]] == []


def test_orphan_spec_is_reported_like_an_orphan_workspace():
    world = state(scopes=[scope("n1")], orphanSpecs=["smazany-uzel"])
    found = [signal for signal in evaluate(world)["signals"]
             if signal["type"] == "workspace-orphan"]
    assert [signal["subject"]["id"] for signal in found] == ["smazany-uzel"]
    assert "zadání" in found[0]["evidence"]["source"]
