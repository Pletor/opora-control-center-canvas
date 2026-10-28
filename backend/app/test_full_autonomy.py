"""Plná autonomie agentů (docs/plna-autonomie-agenta.md): oprávnění odděleně od původce.

Člověk projde vždy; agent bez autonomie dostane 403; agent v projektu se zapnutou autonomií
projde bránou „jen člověk“, ale záznam činnosti i data dál říkají, že to byl agent.
Přepínač sám a výjimky §4 zůstávají jen člověku.
"""
import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_human_session import AGENT, close_as, stored
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

TOGGLE = "/api/project-settings/agent-autonomy"


def autonomy(client, full, headers=HEADERS):
    return client.post(TOGGLE, headers=headers, json={"project": SCOPE["project"], "full": full})


def agent_log(client):
    return client.get("/api/activity-log", params={**SCOPE, "actor": "agent"}).json()["entries"]


def test_switch_is_off_by_default_and_only_human_flips_it(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        settings = client.get("/api/project-settings", params={"project": "draft"}).json()
        assert settings["agentAutonomy"] == {"full": False}
        # Agent si autonomii nesvěří: ani když je vypnutá, ani když už platí (výjimka §4).
        assert autonomy(client, True, AGENT).status_code == 403
        on = autonomy(client, True)
        assert on.status_code == 200
        assert on.json()["agentAutonomy"]["full"] is True and on.json()["agentAutonomy"]["by"] == "human"
        assert autonomy(client, False, AGENT).status_code == 403
        assert client.get("/api/project-settings", params={"project": "draft"}).json()["agentAutonomy"]["full"] is True
        client.cookies.clear()
        assert autonomy(client, False).status_code == 428
        assert autonomy(client, "ano").status_code in (403, 428)


def test_agent_without_autonomy_gets_403_and_human_passes(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert close_as(client, AGENT, "agent").status_code == 403
        payload = {**SCOPE, "sectorId": "s0", "nodeIds": ["n0"], "expectedRevision": stored(client)["revision"]}
        assert client.post("/api/desktop-v3/confirm-proposals", headers=AGENT, json=payload).status_code == 403
        assert close_as(client, HEADERS).status_code == 200
        assert all(entry.get("autonomy") is None for entry in agent_log(client))


def test_agent_with_autonomy_passes_human_gate_but_stays_agent(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert autonomy(client, True).status_code == 200
        closed = close_as(client, AGENT, "agent")
        assert closed.status_code == 200, closed.text
        done = stored(client)["state"]["nodes"]["n0"]["done"]
        # Atribuce: potvrzení zapsal agent, nikdy „human“.
        assert done["confirmed"] is True and done["by"] == "agent"
        entry = next(item for item in agent_log(client) if item["path"] == "/api/desktop-v3/state")
        assert entry["actor"] == "agent" and entry["agent"] == "lazy" and entry["autonomy"] == "full"
        # Agent smí uzavřenou kartu i znovu otevřít (dřív jen člověk).
        current = stored(client)
        reopened = copy.deepcopy(current["state"])
        reopened["nodes"]["n0"]["done"]["confirmed"] = False
        assert client.post("/api/desktop-v3/state", headers=AGENT,
                           json={**SCOPE, "expectedRevision": current["revision"], "state": reopened}).status_code == 200


def test_autonomy_is_marked_only_when_a_gate_needed_it(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert autonomy(client, True).status_code == 200
        # Běžný zápis agenta (bez brány „jen člověk“) se jako autonomní akce neoznačí.
        assert client.post("/api/canvas-versions", headers=AGENT,
                           json={**SCOPE, "author": "lazy", "note": ""}).status_code in (200, 409)
        assert all(entry.get("autonomy") is None for entry in agent_log(client)
                   if entry["path"] == "/api/canvas-versions")


def test_human_only_exceptions_stay_human_with_autonomy(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert autonomy(client, True).status_code == 200
        assert client.post("/api/assistant/jev-key", headers=AGENT, json={"key": None}).status_code == 403
        assert client.post("/api/memory/provision", headers=AGENT, json={"confirmed": True}).status_code == 403
        assert client.post("/api/oporahub/repository", headers=AGENT,
                           json={"project": "draft", "repository": "a/b", "branch": "main"}).status_code == 403
        assert autonomy(client, False, AGENT).status_code == 403


def test_autonomy_is_scoped_to_the_request_project(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert autonomy(client, True).status_code == 200
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()
        assert client.get("/api/project-settings", params={"project": other["id"]}).json()["agentAutonomy"]["full"] is False
        payload = {"project": other["id"], "workspace": "draft", "sectorId": "s0", "nodeIds": ["n0"], "expectedRevision": 0}
        assert client.post("/api/desktop-v3/confirm-proposals", headers=AGENT, json=payload).status_code == 403
        # Projekt s autonomií v query neodemkne zápis do jiného projektu v těle.
        assert client.post("/api/desktop-v3/confirm-proposals", headers=AGENT, params={"project": SCOPE["project"]},
                           json=payload).status_code == 403


def test_agent_state_and_node_brief_carry_autonomy(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"})
        assert brief.status_code == 200, brief.text
        assert brief.json()["autonomy"]["full"] is False and brief.json()["autonomy"]["sectorId"] == "s0"
        assert autonomy(client, True).status_code == 200
        assert client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()["autonomy"]["full"] is True
        state = client.get("/api/oporahub/agent-state", params=SCOPE, headers=AGENT)
        assert state.status_code == 200, state.text
        assert state.json()["autonomy"] == {"full": True}


def test_agent_with_autonomy_accepts_specification_change_under_its_own_name(tmp_path):
    from backend.api.editor.test_opora_changeset_routes import BASE, baseline_payload, proposal_payload
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.post(BASE + "/baselines", headers=AGENT, json=baseline_payload(client)).status_code == 403
        assert autonomy(client, True).status_code == 200
        baseline = client.post(BASE + "/baselines", headers=AGENT, json=baseline_payload(client))
        assert baseline.status_code == 200, baseline.text
        proposal = client.post(BASE + "/changesets", headers=AGENT, json=proposal_payload(client)).json()
        accepted = client.post(BASE + "/changesets/" + proposal["id"] + "/accept", headers=AGENT,
                               json={**SCOPE, "expectedAcceptedHead": baseline.json()["id"], "by": {"kind": "human"}})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["by"] == {"kind": "agent", "name": "lazy"}
        entry = next(item for item in agent_log(client) if item["path"].endswith("/accept"))
        assert entry["autonomy"] == "full" and entry["actor"] == "agent"
