import pytest

from backend.canvas.sync_signals import evaluate
from backend.canvas.test_sync_signals import here, missing, pair, scope, state


def verdicts(world):
    return {item["scope"]["id"]: item for item in evaluate(world)["verdicts"]}


def green_world(**over):
    """Svět, ve kterém uzel `n1` projde celou bránou; testy z něj ubírají."""
    world = state(scopes=[scope("n1", path="backend/a.py", revision=2,
                                saved="2026-09-16T08:00:00")],
                  paths={"backend/a.py": here()},
                  pairs={"n1": pair(revision=2, last="2026-09-17T09:00:00")})
    world.update(over)
    return world


def test_green_node_passes_every_check_in_the_order_from_part_four():
    verdict = verdicts(green_world())["n1"]
    assert [check["id"] for check in verdict["checks"]] == [
        "spec", "source", "pair", "checks", "evidence", "docs", "noHighEcho"]
    assert all(check["passed"] for check in verdict["checks"])
    assert verdict["state"] == "green"
    assert verdict["canCommit"] and verdict["canMerge"]
    assert verdict["blocking"] == [] and verdict["nextSteps"] == []


# Neprošlá kontrola nese typ echa z části 7 a jednu akci, která ji uzavře.
FAILING = [
    ("spec", "opora-uncommitted", "potvrď commit",
     green_world(scopes=[scope("n1", path="backend/a.py", revision=0)])),
    ("source", "source-missing", "oprav vazbu nebo obnov soubor",
     green_world(paths={"backend/a.py": missing()})),
    ("source", None, "doplň vazbu na kód",
     green_world(scopes=[scope("n1", revision=2, saved="2026-09-16T08:00:00")])),
    ("pair", "spec-ahead", "zadej práci; uzavře ji nový pár",
     green_world(pairs={"n1": pair(revision=1)})),
    ("checks", "checks-unknown", "spusť testy a zapiš výsledek",
     green_world(scopes=[scope("n1", path="backend/a.py", revision=2,
                               saved="2026-09-16T08:00:00", checks=False)])),
    ("evidence", "evidence-missing", "doplň důkaz, nebo fázi otevři",
     green_world(scopes=[scope("n1", path="backend/a.py", revision=2,
                               saved="2026-09-16T08:00:00", evidence=False)])),
    ("docs", "doc-path-missing", "oprav odkaz nebo dokument zruš",
     green_world(docIssues=[{"doc": "backend/a.py", "line": 3, "path": "backend/pryc.py"}])),
]


@pytest.mark.parametrize("check_id,signal,step,world", FAILING,
                         ids=[f"{case[0]}-{case[1]}" for case in FAILING])
def test_failed_check_names_its_signal_and_its_step(check_id, signal, step, world):
    verdict = verdicts(world)["n1"]
    failed = {check["id"]: check for check in verdict["checks"] if not check["passed"]}
    assert check_id in failed, verdict["checks"]
    assert failed[check_id]["signal"] == signal
    assert step in verdict["nextSteps"]
    assert verdict["canMerge"] is False


def test_closed_scope_gets_a_verdict_but_no_checks():
    world = green_world(scopes=[scope("n1", path="backend/a.py", revision=3, evidence=False,
                                      closed=True)], paths={"backend/a.py": missing()})
    result = evaluate(world)
    assert result["signals"] == []
    verdict = result["verdicts"][0]
    assert verdict["state"] == "closed"
    assert verdict["canCommit"] is False and verdict["canMerge"] is False
    assert verdict["checks"] == [] and verdict["blocking"] == [] and verdict["nextSteps"] == []


def tree(second_node_revision=2):
    """Oblast > sektor > dva uzly; druhý uzel jde rozbít vyšší revizí zadání."""
    return state(
        scopes=[
            scope("a1", kind="area"),
            scope("s1", kind="sector", parent="a1", path="backend/canvas",
                  path_kind="directory"),
            scope("n1", parent="s1", path="backend/a.py", revision=2,
                  saved="2026-09-16T08:00:00"),
            scope("n2", parent="s1", path="backend/b.py", revision=second_node_revision,
                  saved="2026-09-16T08:00:00"),
        ],
        paths={"backend/a.py": here(), "backend/b.py": here(),
               "backend/canvas": here("directory")},
        pairs={"n1": pair(revision=2), "n2": pair(revision=2)})


def test_sector_and_area_are_green_only_when_their_nodes_are():
    good = verdicts(tree())
    assert good["n1"]["canMerge"] and good["n2"]["canMerge"]
    assert good["s1"]["state"] == "green" and good["a1"]["state"] == "green"
    bad = verdicts(tree(second_node_revision=3))
    assert bad["n2"]["canMerge"] is False
    assert bad["s1"]["canMerge"] is False
    assert bad["a1"]["canMerge"] is False
    assert [check["id"] for check in bad["s1"]["checks"]] == ["source", "children", "noHighEcho"]
    assert [check["id"] for check in bad["a1"]["checks"]] == ["children"]


def test_sector_source_check_stands_on_its_own_link():
    world = tree()
    world["paths"]["backend/canvas"] = missing()
    result = verdicts(world)
    assert result["s1"]["canMerge"] is False
    assert result["s1"]["checks"][0] == {"id": "source", "name": result["s1"]["checks"][0]["name"],
                                         "passed": False, "signal": "source-missing"}
    assert result["n1"]["canMerge"] is True


def test_closed_node_counts_as_green_for_its_sector():
    world = tree()
    world["scopes"][3]["closed"] = True
    result = verdicts(world)
    assert result["n2"]["state"] == "closed"
    assert result["s1"]["state"] == "green"


def test_spec_ahead_blocks_merge_but_never_commit():
    verdict = verdicts(green_world(pairs={"n1": pair(revision=1)}))["n1"]
    assert verdict["canCommit"] is True
    assert verdict["canMerge"] is False
    assert verdict["state"] == "waiting"
    assert verdict["blocking"]


def test_other_high_echo_blocks_commit_too():
    verdict = verdicts(green_world(paths={"backend/a.py": missing()}))["n1"]
    assert verdict["canCommit"] is False
    assert verdict["canMerge"] is False


def test_state_is_draft_without_a_merged_pair():
    verdict = verdicts(green_world(pairs={}))["n1"]
    assert verdict["state"] == "draft"


def test_verdicts_are_sorted_by_scope_id():
    order = [item["scope"]["id"] for item in evaluate(tree())["verdicts"]]
    assert order == sorted(order) == ["a1", "n1", "n2", "s1"]


def test_doc_issue_outside_the_scope_paths_does_not_block_it():
    world = green_world(docIssues=[{"doc": "docs/jine.md", "line": 3, "path": "frontend/x.ts"}])
    verdict = verdicts(world)["n1"]
    assert verdict["state"] == "green"
    assert evaluate(world)["signals"][0]["type"] == "doc-path-missing"


def test_empty_area_and_sector_are_not_green():
    world = state(scopes=[scope("a1", kind="area"),
                          scope("s1", kind="sector", path="backend", path_kind="directory")])
    found = verdicts(world)
    assert found["a1"]["state"] == "draft" and found["a1"]["canMerge"] is False
    assert found["s1"]["state"] == "draft" and found["s1"]["canMerge"] is False
    assert "doplň nebo srovnej rozsahy pod ním" in found["a1"]["nextSteps"]


def test_area_turns_green_only_with_a_green_scope_under_it():
    world = state(
        scopes=[scope("a1", kind="area"),
                scope("n1", parent="a1", path="backend/a.py", revision=2,
                      saved="2026-09-16T08:00:00")],
        paths={"backend/a.py": here()},
        pairs={"n1": pair(revision=2, last="2026-09-17T09:00:00")},
    )
    found = verdicts(world)
    assert found["n1"]["state"] == "green"
    assert found["a1"]["state"] == "green" and found["a1"]["canMerge"] is True


def test_pair_without_a_touched_path_never_opens_the_gate():
    # Kritik napíše trailer do zprávy commitu, ale na vlastněnou cestu nesáhne.
    world = green_world(pairs={"n1": pair(revision=2, last="2026-09-17T09:00:00", touches=False)})
    verdict = verdicts(world)["n1"]
    assert verdict["canMerge"] is False
    assert [check["passed"] for check in verdict["checks"] if check["id"] == "pair"] == [False]
