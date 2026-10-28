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
        asked = client.post("/api/gate/requests", headers=worker, json={"kind": "ask", "body": {"q": "?"}})
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


def ask_gate(client, auth, kind, body=None):
    response = client.post("/api/gate/requests", headers=auth, json={"kind": kind, "body": body or {}})
    return response


def report(client, auth, task, status):
    body = {"taskId": task, "sha": "abc1234", "summary": "hotovo", "checks": [{"name": "pytest", "status": status}]}
    return ask_gate(client, auth, "report", body)


def test_task_queue_end_to_end_through_the_gate(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert toggle(client, True).status_code == 200
        tasks = [client.post("/api/brain/tasks", headers=HEADERS, json={
            **SCOPE, "title": title, "body": {"do": title, "doneWhen": ["pytest zelený"]}}) for title in ("Jedna", "Dva")]
        assert [t.status_code for t in tasks] == [201, 201], tasks[0].text
        first, second = (t.json()["taskId"] for t in tasks)
        # Agent ani pracovník úkol nezapíší (zeď, pak „jen člověk“).
        assert client.post("/api/brain/tasks", headers=AGENT, json={**SCOPE, "title": "x", "body": {"do": "x"}}
                           ).status_code == 403
        auth = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        other = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        assert code(client.post("/api/brain/tasks", headers=auth, json={**SCOPE, "title": "x", "body": {"do": "x"}})
                    ) == "gate_required"
        got = ask_gate(client, auth, "next").json()
        assert got["status"] == "answered" and got["answer"]["task"]["id"] == first
        assert ask_gate(client, auth, "next").json()["answer"]["task"]["id"] == first
        foreign = report(client, other, first, "green")
        assert foreign.status_code == 409 and code(foreign) == "task_not_assigned" and foreign.json()["hint"]
        assert report(client, auth, first, "green").json()["answer"] == {"task": {"id": first, "status": "done",
                                                                                   "attempts": 0}}
        assert ask_gate(client, auth, "next").json()["answer"]["task"]["id"] == second
        assert report(client, auth, second, "red").json()["answer"]["task"] == {"id": second, "status": "ready",
                                                                                "attempts": 1}
        assert ask_gate(client, auth, "next").json()["answer"]["task"]["id"] == second
        assert report(client, auth, second, "red").json()["answer"]["task"]["status"] == "failed"
        empty = ask_gate(client, auth, "next").json()["answer"]
        assert empty["task"] is None and empty["plan"], empty  # seed má otevřené karty
        assert all(set(card) == {"id", "name", "stage"} for card in empty["plan"]) and len(empty["plan"]) <= 20
        listed = client.get("/api/brain/tasks", params=SCOPE, headers=AGENT).json()["tasks"]
        assert [(t["taskId"], t["status"]) for t in listed] == [(first, "done"), (second, "failed")]
        runs = client.app.state.service.db_for("draft").execute(
            "SELECT scope_id, status FROM check_runs WHERE sha='abc1234' ORDER BY recorded_at").fetchall()
        assert [tuple(row) for row in runs] == [(first, "green"), (second, "red"), (second, "red")]
        bad = report(client, auth, second, "green")
        assert bad.status_code == 409 and code(bad) == "task_not_assigned"
        invalid_sha = ask_gate(client, auth, "report", {"taskId": second, "sha": "zz", "summary": "", "checks": []})
        assert invalid_sha.status_code == 422 and code(invalid_sha) == "invalid_sha"


def test_human_cancels_a_task_and_agent_cannot(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        task = client.post("/api/brain/tasks", headers=HEADERS, json={**SCOPE, "title": "t", "body": {"do": "t"}}).json()
        cancel = f"/api/brain/tasks/{task['taskId']}/cancel?project=draft"
        assert client.post(cancel, headers=AGENT, json={}).status_code == 403
        done = client.post(cancel, headers=HEADERS, json={})
        assert done.status_code == 200 and done.json()["status"] == "cancelled", done.text
        again = client.post(cancel, headers=HEADERS, json={})
        assert again.status_code == 409 and code(again) == "task_closed"
        assert code(client.post("/api/brain/tasks", headers=HEADERS, json={**SCOPE, "title": "t", "body": {}})
                    ) == "invalid_payload"
