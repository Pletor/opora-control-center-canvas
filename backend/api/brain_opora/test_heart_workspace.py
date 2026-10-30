"""Srdce staví worktree podle práce (docs/brain-heart-orchestrator.md §9 O7) přes skutečnou aplikaci a git projekt:
v `main` jen architektura (bez přijetí), pracovní prostor domény tokenem srdce (`POST /api/workspaces`), karty
a jejich přijetí v prostoru (`plan --workspace`), převzetí změněné architektury do prostorů, `activeWorkspace`,
sekce PROSTORY snímku a `ctx plan-of`. Supervisor ani model neběží."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import brain_files, tokens
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.canvas.test_canvas_service import managed_fixture

ARCHITECTURE = {"nodes": [
    {"ref": "env", "kind": "sector", "parent": None, "name": "Produkce"},
    {"ref": "web", "kind": "sector", "parent": "env", "name": "Web",
     "site": {"kind": "application", "environments": [{"name": "Produkce", "host": "web.example.cz"}]}},
    {"ref": "home", "kind": "node", "parent": "web", "name": "Domů", "site": {"kind": "page", "path": "/"}},
], "edges": []}
STEP = [{"id": "s1", "order": 1, "title": "Stránka a test", "dependsOn": [], "acceptance": ["test projde"]}]


def card(ref, parent, name):
    return {"ref": ref, "kind": "node", "parent": parent, "name": name, "purpose": "Kus webu.",
            "card": {"layer": "frontend", "status": "ready"},
            "spec": {"goal": f"{name} funguje.", "non_goals": "", "acceptance": "npm test projde", "steps": STEP}}


@pytest.fixture
def heart(tmp_path, monkeypatch):
    """Git projekt se zapnutou bránou; srdce (token prostoru `main`) volá aplikaci přes TestClient, cwd = `brain/`."""
    monkeypatch.setenv("OPORA_HEART", "off")
    fixture, project = managed_fixture(tmp_path)
    fixture.close()
    pid = project["id"]
    for key, value in {"OPORA_PROJECT": pid, "OPORA_WORKSPACE": "main"}.items():
        monkeypatch.setenv(key, value)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": pid, "enabled": True}
                           ).status_code == 200
        service = client.app.state.service
        _, token = tokens.issue_heart(service, pid, "main")
        client.cookies.clear()  # srdce nemá doklad UI
        brain = brain_files.brain_dir(service, pid)
        brain.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(brain)

        def call(method, path, body=None, query=None, actor="heart"):
            headers = {**HEADERS, tokens.HEADER: token, "X-Opora-Actor": f"agent; name={actor}"}
            response = client.request(method, path, params=query, json=body, headers=headers)
            if response.status_code >= 400:
                raise opora_heart.Failure(opora_heart.server_failure(response.status_code, response.json()))
            return response.json()

        monkeypatch.setattr(opora_heart, "call", call)
        yield client, call, pid, brain


def tool(*argv, plan=None):
    if plan is not None:
        os.makedirs("dilna/out", exist_ok=True)
        with open("dilna/out/plan.json", "w", encoding="utf-8") as file:
            json.dump(plan, file, ensure_ascii=False)
        argv = (argv[0], "--file", "dilna/out/plan.json", *argv[1:])
    try:
        return opora_heart.run(opora_heart.parser().parse_args(list(argv)))
    except opora_heart.Failure as failure:
        return failure.payload


def claims(call, pid, workspace):
    state = call("GET", "/api/oporahub/agent-state", query={"project": pid, "workspace": workspace})
    return state, {action["targetId"]: action for action in state["actions"] if action["verb"] == "claim"}


def test_main_is_architecture_and_cards_live_in_the_domain_workspace(heart):
    client, call, pid, brain = heart
    arch = tool("plan", plan=ARCHITECTURE)
    # main: architektura projde tokenem srdce, přijetí tu neexistuje (návrh grafu chce zapisovatelný prostor)
    assert arch["ok"] is True and arch["architecture"] is True and arch["adopted"] == [], arch
    assert "accepted" not in arch and not (brain / opora_heart.ACTIVE).exists()
    web = arch["refs"]["web"]
    refused = tool("plan", plan={"nodes": [card("x", "@" + web, "[task] V main")], "edges": []})
    assert refused["status"] == 409 and "pouze pro čtení" in refused["error"] and "--workspace" in refused["hint"]
    not_domain = tool("workspace", "--domain", arch["refs"]["home"])
    assert not_domain["status"] == 409 and "doméně" in not_domain["error"] and "site.kind" in not_domain["hint"]
    # pracovník bez tokenu prostor nezaloží, srdce ano (zeď: token srdce = plná autonomie ve svém projektu)
    worker = client.post("/api/workspaces", headers={**HEADERS, "X-Opora-Actor": "agent; name=delnik"},
                         json={"project": pid, "nodeId": web, "actor": "delnik"})
    assert worker.status_code == 403 and worker.json()["code"] == "gate_required"
    space = tool("workspace", "--domain", web, "--reuse")
    assert space["created"] is True and space["domain"] == web and space["branch"] == "work/" + space["workspace"]
    again = tool("workspace", "--domain", web, "--reuse")
    assert again == {**space, "created": False}
    wid = space["workspace"]

    done = tool("plan", "--workspace", wid, plan={"nodes": [card("hero", "@" + web, "[task] Úvodní blok")], "edges": []})
    assert done["accepted"] is True and done["acceptSteps"] == ["propose_graph", "accept"], done
    _, ready = claims(call, pid, wid)
    assert ready[done["refs"]["hero"]]["status"] == "ready"
    assert brain_files.active_workspace(brain) == wid
    status = client.get("/api/brain/heart/status", params={"project": pid}).json()
    assert status["activeWorkspace"] == wid

    # nová stránka v main: prostor s přijatým plánem architekturu převezme, jinak by jeho karty nešly převzít
    page = {"nodes": [{"ref": "kontakt", "kind": "node", "parent": "@" + web, "name": "Kontakt",
                       "site": {"kind": "page", "path": "/kontakt"}}], "edges": []}
    more = tool("plan", plan=page)
    assert more["architecture"] is True and more["adopted"] == [wid], more
    state, ready = claims(call, pid, wid)
    assert state["heads"]["workingDiffers"] is False and ready[done["refs"]["hero"]]["status"] == "ready"

    # `--workspace` u task a decide míří do prostoru, ne do main z prostředí
    task = tool("task", "--title", "Sonda", "--do", "Ověř build.", "--workspace", wid)
    assert task["status"] == "ready"
    listed = call("GET", "/api/brain/tasks", query={"project": pid, "workspace": wid})["tasks"]
    assert [item["taskId"] for item in listed] == [task["taskId"]]
    decided = tool("decide", "--text", "Web má jednu doménu.", "--workspace", wid)
    assert decided["by"] == "agent"

    snapshot = call("GET", "/api/brain/heart/snapshot", query={"project": pid, "workspace": "main"})["snapshot"]
    rows = snapshot.split("PROSTORY:\n", 1)[1].split("\nDENÍK:", 1)[0].splitlines()
    assert rows == [f"- {wid} · doména Web · karty volné 1 · běží 0 · hotové 0"]


def test_plan_in_a_workspace_adopts_architecture_changed_behind_its_back(heart):
    _, call, pid, _ = heart
    web = tool("plan", plan=ARCHITECTURE)["refs"]["web"]
    wid = tool("workspace", "--domain", web, "--reuse")["workspace"]
    first = tool("plan", "--workspace", wid, plan={"nodes": [card("hero", "@" + web, "[task] Úvodní blok")], "edges": []})
    assert first["accepted"] is True
    # architekturu změní někdo mimo nástroj srdce (člověk v UI, jiná dávka) → prostor ji ještě nepřevzal
    main = {"project": pid, "workspace": "main"}
    page = {"nodes": [{"ref": "o-nas", "kind": "node", "parent": "@" + web, "name": "O nás",
                       "site": {"kind": "page", "path": "/o-nas"}}], "edges": []}
    call("POST", "/api/canvas-plan", {**main, "digest": call("GET", "/api/view", query=main)["digest"], "plan": page})
    assert claims(call, pid, wid)[0]["heads"]["workingDiffers"] is True
    second = tool("plan", "--workspace", wid,
                  plan={"nodes": [card("pata", "@" + web, "[task] Patička")], "edges": []})
    assert second["accepted"] is True, second
    assert second["acceptSteps"] == ["adopt_architecture", "accept", "graph_addition", "accept"]
    state, ready = claims(call, pid, wid)
    assert state["heads"]["workingDiffers"] is False
    assert {ready[first["refs"]["hero"]]["status"], ready[second["refs"]["pata"]]["status"]} == {"ready"}


def test_ctx_plan_of_dumps_another_workspace_plan_into_the_workshop(heart):
    _, _, pid, brain = heart
    web = tool("plan", plan=ARCHITECTURE)["refs"]["web"]
    wid = tool("workspace", "--domain", web, "--reuse")["workspace"]
    hero = tool("plan", "--workspace", wid, plan={"nodes": [card("hero", "@" + web, "[task] Úvodní blok")],
                                                    "edges": []})["refs"]["hero"]
    done = tool("ctx", "plan-of", "--project", pid, "--workspace", wid)
    assert done["path"] == f"dilna/data/plan-of-{pid}.json" and done["items"] == 4
    items = {item["id"]: item for item in json.loads((brain / done["path"]).read_text(encoding="utf-8"))}
    assert items[hero]["spec"]["goal"] == "[task] Úvodní blok funguje." and items[hero]["spec"]["steps"][0]["id"] == "s1"
    assert items[hero]["parent"] == web and items[hero]["sector"] == web and items[hero]["architecture"] is False
    assert items[web]["architecture"] is True and items[web]["site"] == {"kind": "application"}
    main = tool("ctx", "plan-of", "--project", pid)  # git projekt bez --workspace = main: jen architektura
    assert main["items"] == 3
    assert tool("ctx", "plan-of")["code"] == "plan_of_project"
    assert tool("ctx", "plan-of", "--project", "nikde")["code"] == "project_not_found"
