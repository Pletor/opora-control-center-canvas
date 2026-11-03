"""Hromadné `act` (opora_act_batch.py) nad skutečným backendem: dávka bez shellové smyčky a bez 409.

Eval: agent schvaloval akce smyčkou `for a in …; do act --action-id $a; done`; po prvním kroku se ID přepočítala
a další volání dostala 409. Dávka drží akce podle (verb, targetId), pořadí serveru, hotové přeskočí a cizí
změnu mezi kroky ohlásí jako konflikt s `changed`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[7]))

import opora_act_batch  # noqa: E402
import opora_api  # noqa: E402
import opora_hub  # noqa: E402
import opora_write  # noqa: E402
import test_opora_recipe as recipe  # noqa: E402
from test_opora_recipe import hub, scope  # noqa: E402

agent = recipe.agent  # fixture: lokální Git projekt bez GitHubu s plnou autonomií

STEPS = [{"id": "s1", "order": 1, "title": "Modul", "acceptance": ["modul existuje"], "dependsOn": []}]
ALL = ["--all-ready", "--verb", "propose_graph", "--verb", "accept", "--verb", "accept_baseline", "--verb", "claim"]


def plan(agent, capsys, name="Modul"):
    """Jedna karta dávkou canvas-plan; ve stavu pak čeká propose_graph a accept_baseline."""
    code, view = opora_api.main(["GET", "/api/view", *scope(agent)]), json.loads(capsys.readouterr().out)
    assert code == 0, view
    body = {"digest": view["result"]["digest"], "plan": {"nodes": [
        {"ref": "sektor", "kind": "sector", "parent": None, "name": name},
        {"ref": "karta", "kind": "node", "parent": "sektor", "name": f"[task] {name}",
         "spec": {"goal": "Modul existuje.", "acceptance": "modul existuje", "steps": STEPS}}], "edges": [], "decisions": []}}
    code = opora_write.main(["/api/canvas-plan", *scope(agent), "--json", json.dumps(body)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"], out
    return out["result"]["refs"]["karta"]


def act_err(capsys, agent, *argv):
    code = opora_hub.main(["act", *argv, *scope(agent)])
    captured = capsys.readouterr()
    return code, json.loads(captured.err or captured.out)


def test_batch_of_four_actions_runs_in_server_order_without_409(agent, capsys):
    card = plan(agent, capsys)
    first = hub(capsys, agent, "state", "--fresh")["ready"]
    assert [item["verb"] for item in first] == ["propose_graph", "accept_baseline"]
    assert all(item["command"] == f"opora_hub.py act --action-id {item['id']}" for item in first)

    out = hub(capsys, agent, "act", *ALL)
    # propose_graph změní stav (vznikne accept), accept pokryje i výchozí zadání, pak se uvolní claim karty.
    assert [(item["verb"], item["status"]) for item in out["done"]] == [
        ("propose_graph", "done"), ("accept", "done"), ("claim", "done")], out
    assert out["done"][2]["targetId"] == card
    assert [(item["verb"], item["reason"]) for item in out["skipped"]] == [("accept_baseline", "no_longer_needed")]
    assert set(out) == {"done", "skipped", "next"}
    assert "token" not in json.dumps(out)


def test_rerunning_the_same_batch_has_no_duplicate_effect(agent, capsys):
    plan(agent, capsys)
    hub(capsys, agent, "act", *ALL)
    before = opora_hub.agent_state(opora_write.base_url(recipe.ORIGIN), agent["project"], agent["workspace"], True)[0]
    again = hub(capsys, agent, "act", *ALL)
    after = opora_hub.agent_state(opora_write.base_url(recipe.ORIGIN), agent["project"], agent["workspace"], True)[0]
    assert again["done"] == [] and again["skipped"] == [], again
    assert before["heads"] == after["heads"]
    leases = [(item["nodeId"], (item.get("lease") or {}).get("executionId")) for item in after["cards"]]
    assert leases == [(item["nodeId"], (item.get("lease") or {}).get("executionId")) for item in before["cards"]]


def test_ids_from_one_snapshot_follow_their_verb_and_target(agent, capsys):
    """Eval: ID z jednoho čtení stavu; po accept by druhé ID bylo zastaralé (409), dávka ho přeskočí s důvodem."""
    plan(agent, capsys)
    hub(capsys, agent, "act", "--action-id", hub(capsys, agent, "state", "--fresh")["ready"][0]["id"])  # propose_graph
    ids = [item["id"] for item in hub(capsys, agent, "state", "--fresh")["ready"]]
    out = hub(capsys, agent, "act", *[arg for value in ids for arg in ("--action-id", value)])
    assert [item["verb"] for item in out["done"]] == ["accept"]
    assert out["skipped"] == [{"id": ids[1], "verb": "accept_baseline", "targetId": None, "reason": "no_longer_needed"}]
    assert out["next"]["verb"] == "claim" and out["next"]["command"].startswith("opora_hub.py start --node ")

    again = hub(capsys, agent, "act", *[arg for value in ids for arg in ("--action-id", value)])
    assert again["done"] == [] and [item["reason"].split(":")[0] for item in again["skipped"]] == ["stale_id"] * 2


def test_foreign_change_between_steps_stops_with_a_conflict(agent, capsys, monkeypatch):
    plan(agent, capsys)
    original = opora_hub.perform

    def foreign_then_ours(base, project, workspace, action, *rest):
        if action["verb"] == "accept":  # jiný aktér mezitím změní pracovní graf → hlavy v preconditions neplatí
            monkeypatch.setenv(opora_write.AGENT_ENV, "cizi-agent")
            plan(agent, capsys, "Cizí sektor")
            monkeypatch.setenv(opora_write.AGENT_ENV, "stavitel-e2e")
        return original(base, project, workspace, action, *rest)

    monkeypatch.setattr(opora_hub, "perform", foreign_then_ours)
    code, out = act_err(capsys, agent, *ALL)
    assert code == opora_hub.EXIT_CONFLICT, out
    assert out["status"] == 409 and out["code"] and out["hint"] and out["action"]["verb"] == "accept"
    assert [item["verb"] for item in out["done"]] == ["propose_graph"]
    assert "heads.graphDigest" in out["changed"], out["changed"]


def test_batch_arguments_and_helpers():
    with pytest.raises(ValueError, match="--verb"):
        opora_act_batch.run("http://127.0.0.1:1", "p", "w", all_ready=True)
    with pytest.raises(ValueError, match="--action-id"):
        opora_act_batch.run("http://127.0.0.1:1", "p", "w")
    action = {"id": "act_0123456789abcdef0123", "verb": "claim", "targetId": "n1"}
    assert opora_act_batch.request_id(action) == opora_act_batch.request_id(dict(action)) == "act-act_0123456789abcdef0123"
    before = {"heads": {"acceptedHead": "a", "graphDigest": "g"}, "cards": [{"nodeId": "n1", "stage": "x"}],
              "actions": [{"verb": "accept", "targetId": "p1", "status": "ready"}]}
    after = {"heads": {"acceptedHead": "a", "graphDigest": "h"}, "cards": [{"nodeId": "n1", "stage": "y"}],
             "actions": [{"verb": "rebase", "targetId": "p1", "status": "ready"}]}
    assert opora_act_batch.changed(before, after) == ["heads.graphDigest", "action:p1", "card:n1"]
    assert opora_act_batch.changed(before, before) == []
