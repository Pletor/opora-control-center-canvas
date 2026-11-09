"""Dávka plánu srdce přes skutečnou aplikaci (docs/brain-heart-orchestrator.md §3 O2, O2b): vzor z promptu projde
validací `/api/canvas-plan`, odmítnutí nese text serveru a ostrý `plan` sám přijme graf tokenem srdce, takže první
karta je pro orchestrátora `claim` ready. Plánovač srdce ani model neběží."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.api.brain_opora import test_heart_workspace as spaces
from backend.app.factory import create_app
from backend.brain.seed import SEED_DIR
from backend.brain_opora.determinism import tokens
from backend.brain_opora.heart import command, opora_heart
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.editor.agent_packet.specification_context import capture_specification


def heart_prompt():
    """Systémový prompt srdce ze seedu Brainu (skill `heart`, výchozí aktivní verze)."""
    return command.skill_body((SEED_DIR / "opora-heart" / "skills" / "heart" / "SKILL.md").read_text(encoding="utf-8"))


def prompt_example():
    """První blok ```json v části Plán promptu srdce."""
    prompt = heart_prompt()
    part = prompt.split("## Plán", 1)[1].split("\n## ", 1)[0]
    return json.loads(re.search(r"```json\n(.*?)\n```", part, re.DOTALL).group(1))


@pytest.fixture
def heart(tmp_path, monkeypatch):
    """Aplikace se zapnutou bránou; `opora_heart.call` jde přes TestClient s tokenem srdce a chybami jako ze sítě."""
    for key, value in {"OPORA_PROJECT": "draft", "OPORA_WORKSPACE": "draft"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app(tmp_path / "app"), base_url=ORIGIN) as client:
        seed(client)
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        client.cookies.clear()  # srdce nemá doklad UI

        def call(method, path, body=None, query=None, actor="heart"):
            headers = {**HEADERS, tokens.HEADER: token, "X-Opora-Actor": f"agent; name={actor}"}
            response = client.request(method, path, params=query, json=body, headers=headers)
            if response.status_code >= 400:
                raise opora_heart.Failure(opora_heart.server_failure(response.status_code, response.json()))
            return response.json()

        monkeypatch.setattr(opora_heart, "call", call)
        yield client, call, tmp_path


def plan(tmp_path, body, *flags):
    (tmp_path / "plan.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    args = opora_heart.parser().parse_args(["plan", "--file", "plan.json", *flags])
    try:
        return opora_heart.run(args)
    except opora_heart.Failure as failure:
        return failure.payload


def test_prompt_example_is_the_tool_example_and_passes_the_real_dry_run(heart):
    _, call, tmp_path = heart
    assert prompt_example() == opora_heart.PLAN_EXAMPLE
    done = plan(tmp_path, prompt_example(), "--dry-run")
    assert done["ok"] is True and done["dryRun"] is True and set(done["refs"]) == {"mvp", "model", "cli"}
    assert "accepted" not in done
    assert call("GET", "/api/oporahub/agent-state", query=SCOPE)["heads"]["acceptedHead"] is None


def test_plan_example_carries_card_effort_and_the_prompt_explains_it():
    efforts = [node["card"]["effort"] for node in opora_heart.PLAN_EXAMPLE["nodes"] if "effort" in node.get("card", {})]
    assert "medium" in efforts and set(efforts) <= {"low", "medium", "high", "max"}
    prompt = heart_prompt()
    assert "card.effort" in prompt and "low|medium|high|max" in prompt


def test_plan_with_unknown_card_effort_is_rejected_with_the_server_text(heart):
    _, _, tmp_path = heart
    bad = json.loads(json.dumps(opora_heart.PLAN_EXAMPLE))
    bad["nodes"][1]["card"]["effort"] = "extreme"
    done = plan(tmp_path, bad, "--dry-run")
    assert done["status"] in (409, 422) and "karta" in done["hint"].lower()


def test_rejected_plan_tells_the_heart_what_the_server_said(heart):
    _, _, tmp_path = heart
    # Tvar, který srdce v sondě o-smoke poslalo (pole úkolu brány místo karty).
    bad = {"nodes": [{"id": "t1", "title": "Třída", "why": "základ", "files": ["ukoly.py"]}], "edges": []}
    done = plan(tmp_path, bad, "--dry-run")
    assert done["status"] in (409, 422) and done["hint"] != opora_heart.GENERIC_HINT
    assert done["error"] in done["hint"] and "plan --example" in done["hint"]
    assert "files" in done["hint"]


def test_plan_accepts_the_graph_so_the_first_card_is_claimable(heart):
    _, call, tmp_path = heart
    done = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")
    assert done["ok"] is True and done["accepted"] is True, done
    assert done["acceptSteps"] == ["propose_graph", "accept"]
    state = call("GET", "/api/oporahub/agent-state", query=SCOPE)
    assert state["heads"]["acceptedHead"] and state["heads"]["workingDiffers"] is False
    claims = {action["targetId"]: action for action in state["actions"] if action["verb"] == "claim"}
    assert claims[done["refs"]["model"]]["status"] == "ready"
    assert claims[done["refs"]["cli"]]["blockReason"] == "blocked_by_predecessor"
    assert not [action for action in state["actions"] if action["verb"] in ("propose_graph", "accept", "accept_baseline")]
    # Přijetí zapsalo srdce (agent s plnou autonomií v projektu svého tokenu), ne člověk.
    history = call("GET", "/api/oporahub/graph-proposals", query=SCOPE)["items"]
    assert [(item["by"], item["accepted"]) for item in history] == [({"kind": "agent", "name": "heart"}, True)]


def claims(call):
    state = call("GET", "/api/oporahub/agent-state", query=SCOPE)
    return state, {action["targetId"]: action for action in state["actions"] if action["verb"] == "claim"}


def test_second_plan_over_the_accepted_graph_is_accepted_and_keeps_earlier_claims(heart):
    """Fáze 2 je vždy další plán: přírůstek jde návrhem grafu (jako „Rozšíření plánu“ v UI) a přijme ho srdce."""
    _, call, tmp_path = heart
    first = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")
    assert first["accepted"] is True
    refs = first["refs"]
    step = [{"id": "s1", "order": 1, "title": "Export a test", "dependsOn": [], "acceptance": ["test exportu projde"]}]
    more = {"nodes": [{"ref": "export", "kind": "node", "parent": "@" + refs["mvp"], "name": "[task] Export do CSV",
                       "purpose": "Úkoly do souboru.", "card": {"layer": "backend", "status": "ready", "effort": "high"},
                       "spec": {"goal": "python ukoly.py export zapíše CSV.", "non_goals": "",
                                "acceptance": "python -m unittest projde", "steps": step},
                       "checks": [{"id": "unit", "command": "python -m unittest"}]}],
            "edges": [{"from": "export", "to": "@" + refs["cli"], "port": "next"}]}
    dry = plan(tmp_path, more, "--dry-run")
    assert dry["ok"] is True and dry["dryRun"] is True and "accepted" not in dry
    done = plan(tmp_path, more, "--accept")
    assert done["ok"] is True and done["accepted"] is True, done
    assert done["acceptSteps"] == ["graph_addition", "accept"] and done["warnings"] == []
    state, ready = claims(call)
    assert state["heads"]["workingDiffers"] is False
    export = done["refs"]["export"]
    assert ready[export]["status"] == "ready"  # nová karta
    assert ready[refs["model"]]["status"] == "ready"  # dřívější claim zůstal
    assert ready[refs["cli"]]["blockReason"] == "blocked_by_predecessor"  # nová vazba export → cli
    view = call("GET", "/api/view", query=SCOPE)["graph"]
    node = next(item for item in view["nodes"] if item["id"] == export)
    assert node["parentId"] == refs["mvp"]
    # Karta pozdějšího plánu nese card (i effort) a checks jako první plán a dojdou do zadání dělníka.
    assert node["card"] == more["nodes"][0]["card"] and node["checks"] == more["nodes"][0]["checks"]
    client = heart[0]
    assigned = next(item for item in capture_specification(client.app.state.service, "draft", "draft", export)
                    ["specification"]["graph"]["nodes"] if item["id"] == export)
    assert assigned["effort"] == "high" and assigned["checks"] == more["nodes"][0]["checks"]
    assert {(edge["source"], edge["target"]) for edge in view["edges"]} >= {(export, refs["cli"])}
    history = call("GET", "/api/oporahub/graph-proposals", query=SCOPE)["items"]
    assert [item["accepted"] for item in history] == [True, True]
    assert all(item["by"] == {"kind": "agent", "name": "heart"} for item in history)


def test_later_plan_with_unknown_card_effort_is_rejected_like_the_first_plan(heart):
    _, _, tmp_path = heart
    bad = json.loads(json.dumps(opora_heart.PLAN_EXAMPLE))
    bad["nodes"][1]["card"]["effort"] = "extreme"
    first = plan(tmp_path, bad, "--dry-run")
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")["refs"]
    later = {"nodes": [{**bad["nodes"][1], "ref": "bad", "parent": "@" + refs["mvp"]}], "edges": []}
    done = plan(tmp_path, later)
    assert done["status"] in (409, 422) and "Neplatná karta uzlu." in done["error"] and "Neplatná karta uzlu." in first["error"]
    assert len(call_history(heart)) == 1  # nic nového nevzniklo


def call_history(heart):
    return heart[1]("GET", "/api/oporahub/graph-proposals", query=SCOPE)["items"]


def vault_card(call, refs):
    """Karta tvaru generátoru Schránky (`card_of`) za živý fragment v sektoru prvního plánu, se značenou oblastí
    a sektorem; k tomu blok s portem na existující kartě a vazba block z jeho portu na novou kartu."""
    from backend.editor.brief_vault.brief_vault_plan import area_size
    from backend.editor.brief_vault.brief_vault_plan_cards import card_of
    fragment = call("POST", "/api/brief-vault", {**SCOPE, "op": "create", "scopeNodeId": refs["mvp"],
                                                 "discipline": "be", "title": "Export", "text": "Export do CSV."})
    row = {"fragment_id": fragment["fragment"]["id"], "title": "Export"}
    card = card_of("f1", "s1", row, [], ["Export"], "be", 1, {"type": "SCHEMA", "done": "Export zapíše CSV."})
    batch = {"nodes": [{"ref": "a1", "kind": "area", "parent": None, "name": "Logika", "size": area_size("logika"),
                        "briefGroup": "logika"},
                       {"ref": "s1", "kind": "sector", "parent": "a1", "name": "Backend", "briefDiscipline": "be"},
                       card],
             "edges": [{"from": "@" + refs["model"], "to": "f1", "port": "block", "block": "pick", "blockPort": "yes"}],
             "extend": [{"node": "@" + refs["model"], "blocks": [
                 {"ref": "pick", "title": "Varianta", "ports": [{"ref": "yes", "label": "Ano → export"}]}]}]}
    return batch, row["fragment_id"]


def test_vault_batch_over_the_accepted_graph_keeps_the_brief_and_wires_an_existing_card(heart):
    """Další plán ze Schránky: karta nese fragmentRef, text a bloky, oblast a sektor značky; existující karta dostane
    blok s portem a vazba block z něj projde. Chybný port neprojde ani v dry-run, ani ostře a nic nezapíše."""
    _, call, tmp_path = heart
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")["refs"]
    batch, fragment_id = vault_card(call, refs)
    bad = json.loads(json.dumps(batch))
    bad["edges"][0]["blockPort"] = "no"
    before = call("GET", "/api/desktop-v3/state", query=SCOPE)["revision"], len(call_history(heart))
    for flags in (("--dry-run",), ("--accept",)):
        refused = plan(tmp_path, bad, *flags)
        assert refused["status"] == 409 and "nemá port" in refused["error"], refused
    assert (call("GET", "/api/desktop-v3/state", query=SCOPE)["revision"], len(call_history(heart))) == before
    dry = plan(tmp_path, batch, "--dry-run")
    assert dry["ok"] is True and dry["dryRun"] is True, dry
    done = plan(tmp_path, batch, "--accept")
    assert done["accepted"] is True, done
    assert done["acceptSteps"] == ["graph_addition", "accept"]
    assert len(call_history(heart)) == before[1] + 1
    saved = call("GET", "/api/oporahub/graph-proposals/" + done["proposalId"], query=SCOPE)
    assert saved["schemaVersion"] == 3 and saved["accepted"] is True
    assert saved["refs"] == done["refs"]
    accepted_head = call("GET", "/api/oporahub/graph-proposals/context", query=SCOPE)["acceptedHead"]
    accepted = call("GET", "/api/oporahub/revisions/" + accepted_head, query=SCOPE)
    assert accepted["proposalId"] == saved["id"] and accepted["parentRevision"] == saved["parentRevision"]
    assert accepted["graphManifestId"] and accepted["contentManifestId"]
    new = done["refs"]
    nodes = call("GET", "/api/desktop-v3/state", query=SCOPE)["state"]["nodes"]
    assert nodes == saved["contentEffects"]["after"]["nodes"]
    assert [item["fragmentId"] for item in nodes[new["f1"]]["fragmentRefs"]] == [fragment_id]
    assert [block["title"] for block in nodes[new["f1"]]["blocks"]] == [block["title"] for block in batch["nodes"][2]["blocks"]]
    assert (nodes[new["a1"]]["briefGroup"], nodes[new["s1"]]["briefDiscipline"]) == ("logika", "be")
    text = call("GET", "/api/node-text", query={**SCOPE, "node": new["f1"]})["text"]
    assert text == batch["nodes"][2]["text"]
    block = next(item for item in nodes[refs["model"]]["blocks"] if item["title"] == "Varianta")
    edge = next(item for item in call("GET", "/api/view", query=SCOPE)["graph"]["edges"] if item["port"] == "block")
    assert (edge["source"], edge["target"], edge["sourceBlockId"], edge["sourcePortId"]) == (
        refs["model"], new["f1"], block["id"], "yes")
    state, _ = claims(call)
    assert state["heads"]["workingDiffers"] is False


@pytest.mark.parametrize("flags", [(), ("--no-accept",)])
def test_no_accept_leaves_the_plan_for_the_human(heart, flags):
    _, call, tmp_path = heart
    done = plan(tmp_path, opora_heart.PLAN_EXAMPLE, *flags)
    assert done["accepted"] is False and "acceptSteps" not in done
    assert done["persisted"] is True and done["verified"] is True
    state = call("GET", "/api/oporahub/agent-state", query=SCOPE)
    assert state["heads"]["acceptedHead"] is None
    verbs = [action["verb"] for action in state["actions"]]
    assert "propose_graph" in verbs


def unlink(tmp_path, *flags):
    args = opora_heart.parser().parse_args(["unlink", *flags])
    try:
        return opora_heart.run(args)
    except opora_heart.Failure as failure:
        return failure.payload


def test_unlink_removes_the_edge_and_unblocks_the_successor(heart):
    _, call, tmp_path = heart
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")["refs"]
    _, ready = claims(call)
    assert ready[refs["cli"]]["blockReason"] == "blocked_by_predecessor"
    pair = ["--from", refs["model"], "--to", refs["cli"]]
    dry = unlink(tmp_path, *pair, "--dry-run")
    assert dry["dryRun"] is True and len(dry["removedEdges"]) == 1 and "accepted" not in dry
    _, ready = claims(call)
    assert ready[refs["cli"]]["blockReason"] == "blocked_by_predecessor"  # dry-run nic nezměnil
    done = unlink(tmp_path, *pair)
    assert done["accepted"] is True, done
    state, ready = claims(call)
    assert ready[refs["cli"]].get("blockReason") != "blocked_by_predecessor" and state["heads"]["workingDiffers"] is False
    edges = call("GET", "/api/view", query=SCOPE)["graph"]["edges"]
    assert (refs["model"], refs["cli"]) not in {(edge["source"], edge["target"]) for edge in edges}


def test_unlink_unknown_edge_is_a_clear_error(heart):
    _, _, tmp_path = heart
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")["refs"]
    done = unlink(tmp_path, "--from", refs["cli"], "--to", refs["model"])  # opačný směr
    assert done["code"] == "unlink_unknown_edge" and "není vazba next" in done["error"]


def prune(tmp_path, *flags):
    args = opora_heart.parser().parse_args(["prune", *flags])
    try:
        return opora_heart.run(args)
    except opora_heart.Failure as failure:
        return failure.payload


def test_prune_removes_nodes_with_their_edges_and_never_cascades(heart):
    """Živě: prázdné uzly po zkoušení v přijatém plánu blokovaly každou změnu grafu (409 specifikací)."""
    _, call, tmp_path = heart
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")["refs"]
    parent = prune(tmp_path, "--node", refs["mvp"])
    assert parent["code"] == "prune_children"
    dry = prune(tmp_path, "--node", refs["cli"], "--dry-run")
    assert dry["dryRun"] is True and dry["removedNodes"] == [refs["cli"]] and len(dry["removedEdges"]) == 1
    done = prune(tmp_path, "--node", refs["cli"])
    assert done["accepted"] is True, done
    graph = call("GET", "/api/view", query=SCOPE)["graph"]
    assert refs["cli"] not in {node["id"] for node in graph["nodes"]}
    assert refs["cli"] not in {edge["target"] for edge in graph["edges"]}
    assert prune(tmp_path, "--node", "missing")["code"] == "prune_unknown_node"


@pytest.fixture
def git_heart(tmp_path, monkeypatch):
    """Git projekt: architektura v main, karty v pracovním prostoru domény (fixture test_heart_workspace)."""
    yield from spaces.git_heart(tmp_path, monkeypatch)


def test_prune_clears_nodes_left_only_in_the_accepted_plan_and_adopts_the_new_architecture(git_heart):
    """Živě (Ample): prázdné uzly pod stránkou architektury zůstaly jen v přijatém grafu prostoru, když nová
    architektura z main stránku vypustila. Pracovní graf je už neměl, takže každá změna grafu padala na 409
    specifikací a žádná karta nešla převzít. Jeden `prune` je odebere a zároveň převezme architekturu."""
    client, call, pid, _ = git_heart
    tool = spaces.tool
    arch = tool("plan", plan=spaces.ARCHITECTURE)
    web, home = arch["refs"]["web"], arch["refs"]["home"]
    wid = tool("workspace", "--domain", web, "--reuse")["workspace"]
    filler = [{"ref": "s", "kind": "sector", "parent": "@" + home, "name": "Nový sektor"},
              {"ref": "u", "kind": "node", "parent": "s", "name": "Nový uzel"},
              {"ref": "u2", "kind": "node", "parent": "@" + home, "name": "Nový uzel"},
              {"ref": "a", "kind": "area", "parent": "@" + home, "name": "Nová oblast", "size": {"w": 400, "h": 300}}]
    first = tool("plan", "--accept", "--workspace", wid, plan={
        "nodes": [spaces.card("hero", "@" + web, "[task] Úvodní blok"), spaces.card("pata", "@" + web, "[task] Patička"),
                  *filler],
        "edges": [{"from": "hero", "to": "pata"}, {"from": "u", "to": "u2"}]})
    assert first["accepted"] is True, first
    refs, service = first["refs"], client.app.state.service
    # Pracovní graf prostoru výplň ztratí mimo návrh grafu (přijatý plán ji drží dál), pak main vypustí stránku.
    for key in ("s", "u2", "a"):
        preview = service.removals.preview(pid, wid, "node", refs[key])
        service.removals.remove({"project": pid, "workspace": wid, "kind": "node", "target": refs[key],
                                 "digest": preview["digest"], "confirmed": True}, actor="human")
    main = service.view(pid, "main")
    service.save_graph(pid, "main", {"nodes": [node for node in main["graph"]["nodes"] if node["id"] != home],
                                     "edges": main["graph"]["edges"]}, main["digest"], allow_removal=True, actor="human")
    state, _ = spaces.claims(call, pid, wid)
    assert state["heads"]["workingDiffers"] is True
    pair = ["--workspace", wid, "--from", refs["hero"], "--to", refs["pata"]]
    assert "Existing accepted specifications differ" in tool("unlink", *pair)["error"]

    filler_ids = [refs[key] for key in ("s", "u", "u2", "a")]
    nodes = [flag for node in filler_ids for flag in ("--node", node)]
    parent = tool("prune", "--workspace", wid, "--node", refs["s"])  # potomek u jen v přijatém grafu
    assert parent["code"] == "prune_children" and refs["u"] in parent["error"]
    dry = tool("prune", "--workspace", wid, *nodes, "--dry-run")
    assert dry["adoptArchitecture"] is True and len(dry["removedEdges"]) == 1 and "accepted" not in dry
    done = tool("prune", "--workspace", wid, *nodes)
    assert done["accepted"] is True and done["removedNodes"] == filler_ids, done
    state, ready = spaces.claims(call, pid, wid)
    assert state["heads"]["workingDiffers"] is False and ready[refs["hero"]]["status"] == "ready"
    accepted = call("GET", "/api/oporahub/graph-proposals/context", query={"project": pid, "workspace": wid})
    assert accepted["architectureContext"]["differs"] is False
    assert not {home, *filler_ids} & {node["id"] for node in accepted["acceptedGraph"]["nodes"]}

    assert tool("unlink", *pair)["accepted"] is True
    more = tool("plan", "--accept", "--workspace", wid, plan={"nodes": [spaces.card("kontakt", "@" + web, "[task] Kontakt")],
                                                   "edges": []})
    assert more["accepted"] is True and more["acceptSteps"] == ["graph_addition", "accept"], more
