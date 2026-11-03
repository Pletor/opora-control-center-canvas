"""`opora_hub.py start` / `deliver` (docs/navrhy/2026-10-28-zefektivneni-opory.md §3.4) nad skutečným backendem.

Lokální Git projekt bez GitHubu s plnou autonomií: dávka plánu přes stdin (`opora_write.py --json -`),
přijatý graf, pak karta na dvě volání skriptu: `start --node` → commit s `Opora-Node` → `deliver` → karta
uzavřená. Token nikdy není na výstupu, stav klienta leží v `$OPORA_HOME`, jinak v `<cwd>/.opora/` (gitignore).
"""

import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[7]))

import opora_api
import opora_hub
import opora_write
import test_opora_recipe as recipe
from test_opora_recipe import git, hub, scope

agent = recipe.agent  # fixture: lokální Git projekt bez GitHubu s plnou autonomií

STEPS = [{"id": "s1", "order": 1, "title": "Modul", "acceptance": ["modul existuje"], "dependsOn": []}]


def plan_via_stdin(agent, capsys, monkeypatch):
    code, view = opora_api.main(["GET", "/api/view", *scope(agent)]), json.loads(capsys.readouterr().out)
    assert code == 0, view
    plan = {"digest": view["result"]["digest"], "plan": {"nodes": [
        {"ref": "sektor", "kind": "sector", "parent": None, "name": "Modul"},
        {"ref": "karta", "kind": "node", "parent": "sektor", "name": "[task] Modul",
         "spec": {"goal": "Modul existuje.", "acceptance": "modul existuje", "steps": STEPS}}], "edges": [], "decisions": []}}
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(plan).encode("utf-8"))))
    code = opora_write.main(["/api/canvas-plan", *scope(agent), "--json", "-"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"], out
    return out["result"]["refs"]["karta"]


def accept_graph(agent, capsys):
    accept = hub(capsys, agent, "act", "--action-id", hub(capsys, agent, "state", "--fresh")["ready"][0]["id"])
    while accept["next"] and accept["next"]["verb"] in ("propose_graph", "accept", "accept_baseline"):
        accept = hub(capsys, agent, "act", "--action-id", accept["next"]["id"])


def test_card_in_two_script_calls(agent, capsys, monkeypatch):
    monkeypatch.setenv(opora_hub.HOME_ENV, str(agent["tmp"] / "home"))
    monkeypatch.delenv(opora_hub.STATE_DIR_ENV)
    card = plan_via_stdin(agent, capsys, monkeypatch)
    accept_graph(agent, capsys)

    started = hub(capsys, agent, "start", "--node", card)
    execution = started["executionId"]
    bundle = json.loads((agent["tmp"] / "home" / "hub" / f"execution-{execution}.json").read_text("utf-8"))
    assert "token" not in started and bundle["token"] not in json.dumps(started)
    assert [item["id"] for item in started["steps"]] == ["s1"] and started["next"]["verb"] == "deliver"
    assert Path(started["assignmentFile"]).is_file()

    (agent["repo"] / "modul.py").write_text("VALUE = 1\n", "utf-8")
    git(agent["repo"], "add", ".")
    git(agent["repo"], "commit", "-m", "Modul karty", "-m", f"Opora-Node: {card}")
    done = hub(capsys, agent, "deliver", "--execution", execution, "--summary", "Modul hotový.",
               "--step", "s1", "--check", "npm test=green")
    assert done["closed"] is True and done["missing"] == [] and done["checks"] == 1, done
    assert done["merged"] == git(agent["repo"], "rev-parse", "HEAD") and done["next"]["verb"] == "pick"


def test_bad_check_and_step_shapes_are_refused_before_sending():
    import pytest

    with pytest.raises(ValueError, match="green"):
        opora_hub.parse_checks(["npm test"])
    with pytest.raises(ValueError, match="ID"):
        opora_hub.parse_steps([":jen poznámka"])
    assert opora_hub.parse_steps(["s1:Komponenta: a test", "s2"]) == [
        {"stepId": "s1", "status": "done", "notes": "Komponenta: a test"}, {"stepId": "s2", "status": "done"}]
    assert opora_hub.parse_checks(["a=b=red"]) == [{"name": "a=b", "status": "red"}]


def test_state_lives_in_the_working_copy_and_is_gitignored(tmp_path, monkeypatch):
    for name in (opora_hub.HOME_ENV, opora_hub.STATE_DIR_ENV):
        monkeypatch.delenv(name, raising=False)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("node_modules/", "utf-8")
    monkeypatch.chdir(tmp_path)
    assert opora_hub.state_dir() == tmp_path / ".opora" / "hub"
    assert opora_hub.state_dir() == tmp_path / ".opora" / "hub"  # druhý zápis .gitignore nezdvojí
    assert (tmp_path / ".gitignore").read_text("utf-8") == "node_modules/\n.opora/\n"
    monkeypatch.setenv(opora_hub.HOME_ENV, str(tmp_path / "jinde"))
    assert opora_hub.state_dir() == tmp_path / "jinde" / "hub"


def test_api_and_write_scripts_refuse_the_composed_token_routes(agent, capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(opora_write, "_open", lambda req, timeout: calls.append(req))
    for path in ("/api/oporahub/executions/start", "/api/oporahub/executions/e1/deliver"):
        code = opora_api.main(["POST", path, "--json", "{}", *scope(agent)])
        out = json.loads(capsys.readouterr().out)
        assert code == opora_api.EXIT_REFUSED and "opora_hub.py" in out["hint"], out
        assert opora_write.main([path, *scope(agent), "--json", "{}"]) == 1
        capsys.readouterr()
    assert calls == []
