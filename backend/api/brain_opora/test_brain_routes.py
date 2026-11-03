"""Přepínač a zeď brány přes skutečnou aplikaci (docs/brain-gate.md §1, §3, krok H1a2).

Brána vypnutá = dnešní chování. Zapnutou bránu přepne jen člověk; pak agent bez tokenu ani pracovník
mimo `/api/gate/*` nezapisují a srdce svého projektu jedná s plnou autonomií, jinde ne.
"""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_full_autonomy import agent_log
from backend.app.test_human_session import close_as, stored
from backend.brain_opora.determinism import tokens
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
SETTING = "/api/brain/gate-setting"
SESSION = {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}


def toggle(client, enabled, headers=HEADERS, project="draft"):
    return client.post(SETTING, headers=headers, json={"project": project, "enabled": enabled})


def plan(client, headers):
    return client.post("/api/canvas-plan", headers=headers, json={**SCOPE, "digest": "x", "plan": {"nodes": []}})


def code(response):
    return response.json().get("code")


def test_setting_is_readable_and_only_human_flips_it(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert client.get(SETTING, params={"project": "draft"}, headers=AGENT).json() == {
            "project": "draft", "enabled": False}
        assert toggle(client, True, AGENT).status_code == 403
        on = toggle(client, True)
        assert on.status_code == 200 and on.json()["enabled"] is True and on.json()["by"] == "human"
        assert client.get(SETTING, params={"project": "draft"}).json()["enabled"] is True
        assert toggle(client, False, AGENT).status_code == 403
        assert toggle(client, "ano").status_code == 422 and code(toggle(client, "ano")) == "invalid_payload"
        assert toggle(client, True, project="neni").status_code == 404
        assert client.get(SETTING, params={"project": "neni"}).status_code == 404
        assert toggle(client, False).json() == {"project": "draft", "enabled": False}


def test_wall_end_to_end(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        service = client.app.state.service
        # Brána vypnutá: zápis agenta zeď nevidí (odpověď je ta dnešní, ne gate_required).
        assert code(plan(client, AGENT)) != "gate_required"
        assert toggle(client, True).status_code == 200
        # Agent bez tokenu nezapisuje, čtení je volné.
        refused = plan(client, AGENT)
        assert refused.status_code == 403 and code(refused) == "gate_required"
        assert refused.json()["hint"] == "Write through the gate: POST /api/gate/requests"
        assert stored(client)["revision"] >= 1 and client.get("/api/view", params=SCOPE, headers=AGENT).status_code == 200
        # Pracovník: mimo bránu 403, bránou projde.
        issued = client.post("/api/gate/sessions", headers=AGENT, json=SESSION)
        assert issued.status_code == 201, issued.text
        worker = {**AGENT, tokens.HEADER: issued.json()["token"]}
        assert code(plan(client, worker)) == "gate_required"
        asked = client.post("/api/gate/requests", headers=worker, json={"kind": "ask", "body": {"question": "?"}})
        assert asked.status_code == 201, asked.text
        # Neplatný token 401.
        assert plan(client, {**AGENT, tokens.HEADER: "x" * 43}).status_code == 401
        # Srdce svého projektu: projde zdí a projde i branou „jen člověk“ (plná autonomie).
        assert close_as(client, AGENT, "agent").status_code == 403
        _, heart = tokens.issue_heart(service, "draft", "draft")
        closed = close_as(client, {**AGENT, tokens.HEADER: heart}, "agent")
        assert closed.status_code == 200, closed.text
        entry = next(item for item in agent_log(client) if item["path"] == "/api/desktop-v3/state")
        assert entry["agent"] == "dev" and entry["autonomy"] == "full"
        # Srdce jiného projektu sem nesmí.
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()["id"]
        _, foreign = tokens.issue_heart(service, other, "draft")
        scoped = plan(client, {**AGENT, tokens.HEADER: foreign})
        assert scoped.status_code == 403 and code(scoped) == "gate_scope"
        # Bránu si agent nevypne; člověk ano a pak je vše jako dnes.
        assert toggle(client, False, AGENT).status_code == 403
        assert toggle(client, False).status_code == 200
        assert code(plan(client, AGENT)) != "gate_required"


def test_heart_has_no_autonomy_in_a_project_with_the_gate_off(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        _, heart = tokens.issue_heart(client.app.state.service, "draft", "draft")
        # Brána vypnutá: token srdce nic neodemyká, agent zůstává bez autonomie.
        assert close_as(client, {**AGENT, tokens.HEADER: heart}, "agent").status_code == 403


def test_heart_without_actor_header_acts_as_agent_heart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert toggle(client, True).status_code == 200
        _, heart = tokens.issue_heart(client.app.state.service, "draft", "draft")
        client.cookies.clear()  # bez dokladu UI a bez hlavičky agenta je původce `unknown`
        assert code(plan(client, HEADERS)) == "gate_required"
        closed = close_as(client, {**HEADERS, tokens.HEADER: heart}, "agent")
        assert closed.status_code == 200, closed.text
        entry = next(item for item in agent_log(client) if item["path"] == "/api/desktop-v3/state")
        assert (entry["actor"], entry["agent"], entry["autonomy"]) == ("agent", "heart", "full")


def test_old_task_queue_is_gone_and_work_tickets_are_readable(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.get("/api/brain/tasks", params=SCOPE, headers=AGENT).status_code == 404
        assert client.post("/api/brain/tasks/ht_1/cancel?project=draft", headers=HEADERS, json={}).status_code == 404
        assert client.get("/api/brain/tickets", params=SCOPE, headers=AGENT).json() == {"tickets": []}

