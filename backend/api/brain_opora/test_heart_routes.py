"""Srdce přes skutečnou aplikaci (docs/brain-heart.md §1, §4, §5): zprávy, stav, snímek, eskalace a token srdce
v úkolech a odpovědích. Supervisor v testech neběží (OPORA_HEART=off), žádný proces `claude` nevznikne."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
SESSION = {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}
MESSAGE = {**SCOPE, "text": "Chci web o dvou stránkách."}


def code(response):
    return response.json().get("code")


def gate_on(client):
    assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                       ).status_code == 200


def test_messages_are_human_only_need_the_gate_and_show_in_status(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.app.state.heart.thread is None  # OPORA_HEART=off
        assert client.post("/api/brain/heart/messages", headers=AGENT, json=MESSAGE).status_code == 403
        assert code(client.post("/api/brain/heart/messages", headers=HEADERS, json=MESSAGE)) == "gate_off"
        gate_on(client)
        assert code(client.post("/api/brain/heart/messages", headers=HEADERS, json={**SCOPE, "text": " "})
                    ) == "invalid_payload"
        queued = client.post("/api/brain/heart/messages", headers=HEADERS, json=MESSAGE)
        assert queued.status_code == 200 and queued.json() == {"queued": True, "pending": 1}
        status = client.get("/api/brain/heart/status", params={"project": "draft"}).json()
        assert status["pending"] == 1 and status["batches"] == [] and status["session"]["sessionId"] is None
        assert status["enabled"] is False and status["nextAllowedAt"]
        assert client.get("/api/brain/heart/status", params={"project": "nikde"}).status_code == 404
        text = client.get("/api/brain/heart/snapshot", params=SCOPE).json()["snapshot"]
        assert text.startswith("PROJEKT") and "FRONTA ÚKOLŮ" in text
        # zpráva je trvalá (brain/messages.jsonl) a snímek ji čte
        assert "Chci web o dvou stránkách." in text.split("ZPRÁVY ČLOVĚKA:")[1].split("PRAVIDLA:")[0]


def test_worker_token_of_the_project_relays_a_message_marked_via(tmp_path):
    """Relé záměru (docs/brain-heart-orchestrator.md §8): pracovník brány předá srdci zprávu člověka."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()["id"]
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        foreign = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT,
                                                       json={**SESSION, "project": other}).json()["token"]}
        ui = dict(client.cookies)
        client.cookies.clear()  # pracovník nemá doklad UI
        assert code(client.post("/api/brain/heart/messages", headers=worker, json=MESSAGE)) == "gate_off"
        client.cookies.update(ui)
        gate_on(client)
        client.cookies.clear()
        relayed = client.post("/api/brain/heart/messages", headers=worker, json=MESSAGE)
        assert relayed.status_code == 200 and relayed.json() == {"queued": True, "pending": 1}, relayed.text
        text = client.get("/api/brain/heart/snapshot", params=SCOPE).json()["snapshot"]
        assert "Chci web o dvou stránkách. (přes dev)" in text.split("ZPRÁVY ČLOVĚKA:")[1].split("PRAVIDLA:")[0]
        bad = client.post("/api/brain/heart/messages", headers={**AGENT, tokens.HEADER: "x"}, json=MESSAGE)
        assert bad.status_code == 401 and code(bad) == "gate_token_invalid"
        assert client.post("/api/brain/heart/messages", headers=AGENT, json=MESSAGE).status_code == 403
        scoped = client.post("/api/brain/heart/messages", headers=foreign, json=MESSAGE)
        assert scoped.status_code == 403 and code(scoped) == "gate_scope", scoped.text


def test_heart_token_writes_tasks_answers_and_escalates_in_its_project(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        service = client.app.state.service
        _, token = tokens.issue_heart(service, "draft", "draft")
        heart = {**HEADERS, tokens.HEADER: token}
        client.cookies.clear()  # srdce nemá doklad UI
        task = client.post("/api/brain/tasks", headers=heart, json={**SCOPE, "order": 2, "title": "Hero",
                                                                    "body": {"do": "Hero sekce"}})
        assert task.status_code == 201, task.text
        assert (task.json()["createdBy"], task.json()["order"]) == ("heart", 2)
        cancel = client.post(f"/api/brain/tasks/{task.json()['taskId']}/cancel?project=draft", headers=heart, json={})
        assert cancel.status_code == 200 and cancel.json()["status"] == "cancelled"
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        ticket = client.post("/api/gate/requests", headers=worker, json={"kind": "ask", "body": {"question": "?"}}).json()
        answered = client.post(f"/api/gate/tickets/{ticket['ticketId']}/answer?project=draft", headers=heart,
                               json={"answer": {"text": "Ano"}})
        assert answered.status_code == 200 and answered.json()["answeredBy"] == "heart", answered.text
        # Pracovník ani agent bez tokenu srdce neodpovídají a úkoly nepíší.
        ticket = client.post("/api/gate/requests", headers=worker, json={"kind": "ask", "body": {"question": "?"}}).json()
        refused = client.post(f"/api/gate/tickets/{ticket['ticketId']}/answer?project=draft", headers=worker,
                              json={"answer": "x"})
        assert refused.status_code == 403 and code(refused) == "human_required"
        assert client.post("/api/brain/tasks", headers=AGENT, json={**SCOPE, "title": "x", "body": {"do": "x"}}
                           ).status_code == 403
        escalated = client.post("/api/brain/heart/escalate", headers=heart, json={**SCOPE, "text": "Barva?"})
        assert escalated.status_code == 201 and escalated.json()["kind"] == "ask", escalated.text
        # Pracovníka zastaví už zeď (zápis mimo /api/gate/*).
        assert code(client.post("/api/brain/heart/escalate", headers=worker, json={**SCOPE, "text": "x"})
                    ) == "gate_required"
        assert client.post("/api/brain/heart/messages", headers=heart, json=MESSAGE).status_code == 403


def test_heart_token_adds_decisions_and_proposes_rules_in_the_snapshot(tmp_path, monkeypatch):
    """`decide` a `rule` (§3a): tvar z nástroje srdce projde skutečnou routou; pravidlo je návrh agenta."""
    for key, value in {"OPORA_PROJECT": "draft", "OPORA_WORKSPACE": "draft"}.items():
        monkeypatch.setenv(key, value)
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        heart = {**HEADERS, tokens.HEADER: token}
        client.cookies.clear()  # srdce nemá doklad UI
        decision = opora_heart.decision_payload(opora_heart.parser().parse_args(
            ["decide", "--text", "Test h1 smí upravit úkol hero.", "--node", "n0", "--pin"]))
        added = client.post("/api/desktop-v3/decision", headers=heart, json=decision)
        assert added.status_code == 200, added.text
        assert added.json()["item"]["by"] == "agent" and added.json()["item"]["nodeId"] == "n0"
        rule = opora_heart.rule_payload(opora_heart.parser().parse_args(["rule", "--text", "Texty česky, tykání."]))
        proposed = client.post("/api/desktop-v3/rule", headers=heart, json=rule)
        assert proposed.status_code == 200, proposed.text
        assert proposed.json()["item"] == {**rule["item"], "by": "agent"}  # server označí návrh agenta
        text = client.get("/api/brain/heart/snapshot", params=SCOPE).json()["snapshot"]
        assert "- Texty česky, tykání. (návrh)" in text.split("PRAVIDLA:")[1].split("ROZHODNUTÍ:")[0]
        assert "- [připnuto] Test h1 smí upravit úkol hero. · karta n0" in text.split("ROZHODNUTÍ:")[1]
        # Pracovník bez tokenu srdce do paměti nepíše (zeď).
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        other = {**decision, "id": "hd_worker", "item": {**decision["item"], "id": "hd_worker"}}
        refused = client.post("/api/desktop-v3/decision", headers=worker, json=other)
        assert refused.status_code == 403 and code(refused) == "gate_required"


def test_heart_of_another_project_has_no_writer_rights_here(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()["id"]
        _, foreign = tokens.issue_heart(client.app.state.service, other, "draft")
        response = client.post("/api/brain/tasks", headers={**AGENT, tokens.HEADER: foreign},
                               json={**SCOPE, "title": "x", "body": {"do": "x"}})
        assert response.status_code == 403 and code(response) == "gate_scope"


def test_heart_drives_the_queue_through_the_gate_in_a_gate_on_project(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        heart = {**HEADERS, tokens.HEADER: token}
        client.cookies.clear()  # srdce nemá doklad UI

        def gate(kind, body, query=""):
            return client.post("/api/gate/requests" + query, headers=heart, json={"kind": kind, "body": body})

        created = gate("task.create", {"title": "Hero", "order": 1, "body": {"do": "Hero sekce"}})
        assert created.status_code == 201, created.text
        task = created.json()["answer"]["task"]
        assert (task["createdBy"], task["workspaceId"], task["order"]) == ("heart", "draft", 1)
        cancelled = gate("task.cancel", {"taskId": task["taskId"]}, "?project=draft")
        assert cancelled.status_code == 201 and cancelled.json()["answer"]["task"]["status"] == "cancelled"
        again = gate("task.cancel", {"taskId": task["taskId"]})
        assert again.status_code == 409 and code(again) == "task_closed" and again.json()["hint"]
        assert code(gate("ticket.answer", {"ticketId": "gt_none", "text": "x"})) == "ticket_not_found"


def test_escalations_are_for_the_human_and_an_answer_wakes_the_heart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        service, heart = client.app.state.service, client.app.state.heart
        _, token = tokens.issue_heart(service, "draft", "draft")
        ticket = gate.escalate(service, tokens.verify(service, token), "Jakou barvu?")
        listed = client.get("/api/brain/heart/escalations", headers=HEADERS, params=SCOPE)
        assert listed.status_code == 200, listed.text
        assert [(e["ticketId"], e["text"]) for e in listed.json()["escalations"]] == [(ticket["ticketId"], "Jakou barvu?")]
        # Agent ani srdce otázky pro člověka nečtou; chybějící prostor je 422.
        assert client.get("/api/brain/heart/escalations", headers=AGENT, params=SCOPE).status_code == 403
        assert client.get("/api/brain/heart/escalations", headers=HEADERS, params={"project": "draft"}
                          ).status_code == 422
        answered = client.post(f"/api/gate/tickets/{ticket['ticketId']}/answer?project=draft", headers=HEADERS,
                               json={"answer": {"text": "Modrou"}})
        assert answered.status_code == 200 and answered.json()["answeredBy"] == "human", answered.text
        assert [item for _, item, _ in heart.pending["draft"]] == [
            {"type": "message", "text": f"ODPOVĚĎ ČLOVĚKA na {ticket['ticketId']}: Modrou"}]
        assert client.get("/api/brain/heart/status", params={"project": "draft"}).json()["pending"] == 1
        assert client.get("/api/brain/heart/escalations", headers=HEADERS, params=SCOPE).json() == {"escalations": []}


def test_answer_to_a_worker_ticket_does_not_wake_the_heart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        asked = client.post("/api/gate/requests", headers=worker,
                            json={"kind": "ask", "body": {"question": "Smím?"}})
        assert asked.status_code == 201, asked.text
        answered = client.post(f"/api/gate/tickets/{asked.json()['ticketId']}/answer?project=draft", headers=HEADERS,
                               json={"answer": {"text": "Ano"}})
        assert answered.status_code == 200, answered.text
        assert client.app.state.heart.pending.get("draft", []) == []


def test_workshop_context_is_for_the_heart_of_its_own_project_only(tmp_path):
    """`ctx` (§3b): data dílny čte jen token srdce svého projektu a prostoru; pracovník ani cizí srdce ne."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        service = client.app.state.service
        _, token = tokens.issue_heart(service, "draft", "draft")
        heart = {**HEADERS, tokens.HEADER: token}
        client.cookies.clear()
        assert client.post("/api/brain/tasks", headers=heart, json={**SCOPE, "title": "Hero",
                                                                    "body": {"do": "Hero sekce"}}).status_code == 201
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        client.post("/api/gate/requests", headers=worker, json={"kind": "ask", "body": {"question": "?"}})
        tasks = client.get("/api/brain/heart/context", headers=heart, params={**SCOPE, "name": "tasks"})
        assert tasks.status_code == 200, tasks.text
        assert [(item["title"], item["body"]["do"]) for item in tasks.json()["items"]] == [("Hero", "Hero sekce")]
        tickets = client.get("/api/brain/heart/context", headers=heart, params={**SCOPE, "name": "tickets"}).json()
        assert [item["kind"] for item in tickets["items"]] == ["ask"]
        for name in ("journal", "messages", "rules", "decisions", "tree"):
            got = client.get("/api/brain/heart/context", headers=heart, params={**SCOPE, "name": name})
            assert got.status_code == 200 and isinstance(got.json()["items"], list), (name, got.text)
        assert code(client.get("/api/brain/heart/context", headers=heart, params={**SCOPE, "name": "x"})
                    ) == "invalid_payload"
        refused = client.get("/api/brain/heart/context", headers=worker, params={**SCOPE, "name": "tasks"})
        assert refused.status_code == 403 and code(refused) == "gate_scope"
        assert client.get("/api/brain/heart/context", headers=HEADERS, params={**SCOPE, "name": "tasks"}
                          ).status_code == 401
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()["id"]
        _, foreign = tokens.issue_heart(service, other, "draft")
        assert code(client.get("/api/brain/heart/context", headers={**HEADERS, tokens.HEADER: foreign},
                               params={**SCOPE, "name": "tasks"})) == "gate_scope"
        _, main = tokens.issue_heart(service, "draft", "main")
        assert code(client.get("/api/brain/heart/context", headers={**HEADERS, tokens.HEADER: main},
                               params={**SCOPE, "name": "tasks"})) == "gate_scope"


def test_heart_token_confirms_an_intake_verdict_and_nobody_else_writes_it(tmp_path):
    """Vstupní brána, řez 2 (docs/navrhy/2026-10-30-vstupni-brana.md §4): stanovisko vstupu potvrdí jen srdce."""
    from backend.brain_opora.determinism import intake

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        service = client.app.state.service
        db = service.db_for("draft")
        with db:
            entry = intake.record(db, "draft", "heart_message", None, "Přidej hybridní hledání.", "2026-10-30T10:00:00Z")
        body = {**SCOPE, "entry": entry["id"], "verdict": "later_extension", "reason": "po milníku Hledání"}
        assert code(client.post("/api/brain/heart/intake", headers=HEADERS, json=body)) == "gate_token_invalid"
        _, token = tokens.issue_heart(service, "draft", "draft")
        heart = {**HEADERS, tokens.HEADER: token}
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        client.cookies.clear()
        confirmed = client.post("/api/brain/heart/intake", headers=heart, json=body)
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json() == {"id": entry["id"], "verdict": "later_extension", "layer": "heart", "areaId": None,
                                    "reason": "po milníku Hledání", "requirementId": None}
        linked = client.post("/api/brain/heart/intake", headers=heart, json={
            **body, "requirement": "new", "title": "Hybridní hledání", "openCondition": "ms_1"})
        assert linked.status_code == 200 and linked.json()["requirementId"].startswith("rq_"), linked.text
        assert code(client.post("/api/brain/heart/intake", headers=heart, json={**body, "requirement": "new"})
                    ) == "invalid_payload"
        assert code(client.post("/api/brain/heart/intake", headers=worker, json=body)) == "gate_required"
        assert code(client.post("/api/brain/heart/intake", headers=heart, json={**body, "workspace": "main"})
                    ) == "gate_scope"
        assert code(client.post("/api/brain/heart/intake", headers=heart, json={**body, "verdict": "duplicate"})
                    ) == "invalid_payload"
        assert code(client.post("/api/brain/heart/intake", headers=heart, json={**body, "entry": "ie_x"})
                    ) == "intake_entry_not_found"


def test_heart_token_writes_a_brief_and_asks_and_intake_shows_the_brief(tmp_path):
    """Výslech, řez 1 (docs/navrhy/2026-10-30-vyslech-srdce.md §7): `brief` a `ask` jen token srdce svého prostoru,
    `GET /api/intake` nese u požadavku `brief: {status, questions, missing}`."""
    from backend.brain_opora.determinism.test_brief import CLEAR, add

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        service = client.app.state.service
        db = service.db_for("draft")
        with db:
            add(db, "rq_1", ["fix_for_milestone"], area=None)
        view = client.get("/api/intake", params=SCOPE).json()
        assert view["unassigned"][0]["brief"] is None
        body = {**SCOPE, "requirement": "rq_1", "synthesis": {"goal": "Metriky"}}
        question = {**SCOPE, "requirement": "rq_1", "question": "Kdo?", "recommended": "Člověk.", "why": "Rozsah."}
        assert code(client.post("/api/brain/heart/brief", headers=HEADERS, json=body)) == "gate_token_invalid"
        heart = {**HEADERS, tokens.HEADER: tokens.issue_heart(service, "draft", "draft")[1]}
        client.cookies.clear()
        assert code(client.post("/api/brain/heart/ask", headers=heart, json=question)) == "brief_missing"
        saved = client.post("/api/brain/heart/brief", headers=heart, json=body)
        assert saved.status_code == 200 and saved.json()["status"] == "draft" and saved.json()["missing"], saved.text
        asked = client.post("/api/brain/heart/ask", headers=heart, json=question)
        assert asked.status_code == 201 and asked.json()["question"] == "q1", asked.text
        assert code(client.post("/api/brain/heart/brief", headers=heart, json={**body, "extra": 1})) == "invalid_payload"
        assert code(client.post("/api/brain/heart/brief", headers=heart, json={**body, "synthesis": {"x": 1}})
                    ) == "invalid_payload"
        assert code(client.post("/api/brain/heart/brief", headers=heart, json={**body, "workspace": "main"})
                    ) == "gate_scope"
        assert code(client.post("/api/brain/heart/brief", headers=heart, json={**body, "requirement": "rq_x"})
                    ) == "intake_requirement_not_found"
        assert client.post("/api/brain/heart/brief", headers=heart, json={**body, "synthesis": CLEAR}
                           ).json()["status"] == "grilling"  # otázka čeká na člověka
        shown = client.get("/api/intake", params=SCOPE).json()["unassigned"][0]["brief"]
        assert shown["status"] == "grilling" and shown["questions"][0]["recommended"] == "Člověk."
        assert shown["missing"] == ["otázky výslechu čekají na odpověď člověka"]


def test_intake_setting_is_read_by_anyone_and_changed_only_by_a_human(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        read = client.get("/api/brain/intake-setting", params={"project": "draft"})
        assert read.json() == {"project": "draft", "jev": False, "jevPerDay": 200}
        assert client.post("/api/brain/intake-setting", headers=AGENT, json={"project": "draft", "jev": True}
                           ).status_code == 403
        saved = client.post("/api/brain/intake-setting", headers=HEADERS,
                            json={"project": "draft", "jev": True, "jevPerDay": 20})
        assert saved.status_code == 200 and saved.json() == {"project": "draft", "jev": True, "jevPerDay": 20}
        assert code(client.post("/api/brain/intake-setting", headers=HEADERS, json={"project": "draft"})
                    ) == "invalid_payload"
        gate_on(client)  # přepnutí brány povolení Jevu nesmaže
        assert client.get("/api/brain/intake-setting", params={"project": "draft"}).json()["jev"] is True
