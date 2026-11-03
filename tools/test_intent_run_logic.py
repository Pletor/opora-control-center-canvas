"""Runner záměru stránky bez prohlížeče: plán, pořadí, vyhodnocení `check` a doklad `opora.intent-run/1`."""
import pytest

from tools import intent_run_logic as logic

PLAN = {"schema": "opora.intent-plan/1", "pageId": "landing", "workflowVersionId": "v1",
        "digest": "sha256:" + "a" * 64, "path": "/video",
        "nodes": [{"nodeId": "type", "kind": "step", "do": "type", "scope": "body", "text": "a@b.cz"},
                  {"nodeId": "send", "kind": "step", "do": "submit", "scope": "body"},
                  {"nodeId": "mail", "kind": "expect", "check": "email", "value": "e-mail", "does": "send_email"},
                  {"nodeId": "seen", "kind": "expect", "check": "visible", "value": "Děkujeme"},
                  {"nodeId": "ok", "kind": "expect", "check": "path", "value": "/dekujeme/"}]}


def observer(text="Děkujeme za zájem", path="/dekujeme"):
    return {"visible": lambda value: value in text,
            "path": lambda value: logic.normalize_path(value) == logic.normalize_path(path)}


def test_check_plan_refuses_other_shapes():
    assert logic.check_plan(PLAN) is PLAN
    for bad in ({**PLAN, "schema": "opora.journey-plan/1"}, {**PLAN, "nodes": []},
                {**PLAN, "nodes": [{"nodeId": "x", "kind": "jump"}]}, {**PLAN, "digest": None}):
        with pytest.raises((TypeError, ValueError)):
            logic.check_plan(bad)


def test_walk_does_steps_and_checks_visible_and_path_in_the_browser():
    done = []
    results = logic.walk(PLAN, lambda step: done.append(step["nodeId"]) or (True, None), observer(), lambda _: None)
    assert done == ["type", "send"]
    assert results == [{"nodeId": "type", "ok": True}, {"nodeId": "send", "ok": True},
                       {"nodeId": "mail", "ok": None, "reason": "neověřeno: kontrolu email prohlížeč neověří"},
                       {"nodeId": "seen", "ok": True}, {"nodeId": "ok", "ok": True}]
    run = logic.build_run(PLAN, results)
    assert run["schema"] == "opora.intent-run/1" and run["digest"] == PLAN["digest"] and logic.run_passed(run)


def test_failed_expectations_carry_reasons():
    results = logic.walk(PLAN, lambda step: (True, None), observer(text="Chyba", path="/video"), lambda _: None)
    assert results[3] == {"nodeId": "seen", "ok": False, "reason": "na stránce chybí „Děkujeme“"}
    assert results[4] == {"nodeId": "ok", "ok": False, "reason": "cesta není /dekujeme"}
    assert not logic.run_passed(logic.build_run(PLAN, results))


def test_failed_step_stops_the_replay_and_leaves_the_rest_unverified():
    lines = []
    results = logic.walk(PLAN, lambda step: (step["nodeId"] != "send", "v body chybí tlačítko odeslání"),
                         observer(), lines.append)
    assert results[1] == {"nodeId": "send", "ok": False, "reason": "v body chybí tlačítko odeslání"}
    assert [r["ok"] for r in results[2:]] == [None, None, None]
    assert results[4]["reason"] == "nepřehráno: krok send neprošel"
    assert lines == ["type: ok", "send: selhal: v body chybí tlačítko odeslání"]


def test_unknown_or_empty_check_is_unverified():
    assert logic.evaluate({"check": None, "value": "x"}, observer()) == (
        None, "neověřeno: kontrolu bez druhu prohlížeč neověří")
    assert logic.evaluate({"check": "visible", "value": ""}, observer()) == (
        None, "neověřeno: kontrola visible nemá hodnotu")


def test_unopened_page_fails_the_first_node_only():
    results = logic.unopened(PLAN, "nelze otevřít http://x/video: timeout", lambda _: None)
    assert results[0] == {"nodeId": "type", "ok": False, "reason": "nelze otevřít http://x/video: timeout"}
    assert {r["ok"] for r in results[1:]} == {None}
