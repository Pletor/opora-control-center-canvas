"""`GET /api/intake` přes skutečnou aplikaci: oblasti, poslední vstupy a počty; jen čtení, chyby rozsahu 404 / 422."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import intake
from backend.canvas.test_canvas_plan import ORIGIN


def test_intake_view_reads_entries_and_refuses_unknown_scope(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/intake", params={"project": "draft", "workspace": "draft"}).json() == {
            "areas": [], "unassigned": [], "entries": [], "pending": 0, "duplicates": 0}
        db = app.state.service.db_for("draft")
        with db:
            intake.record(db, "draft", "heart_message", None, "Přidej hledání.", "2026-10-30T10:00:00Z")
            intake.record(db, "draft", "gate_ask", "gt_1", "přidej hledání", "2026-10-30T10:01:00Z")
        body = client.get("/api/intake", params={"project": "draft", "workspace": "draft"}).json()
        assert (body["pending"], body["duplicates"]) == (1, 1)
        assert [(entry["source"], entry["verdict"]) for entry in body["entries"]] == [
            ("gate_ask", "duplicate"), ("heart_message", "pending")]
        assert body["entries"][0]["sourceRef"] == "gt_1" and body["entries"][0]["layer"] == "determinism"
        for params, status in (({"project": "nikde", "workspace": "draft"}, 404),
                               ({"project": "draft"}, 422), ({"project": "draft", "workspace": "w-neni"}, 404)):
            assert client.get("/api/intake", params=params).status_code == status


def test_heart_proposes_a_milestone_and_only_a_human_activates_it(tmp_path):
    """Řez 3 (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5): návrh jen token srdce, rozhodnutí člověk nebo agent s plnou autonomií,
    pohled „Požadavky a plán“ ukazuje návrh, aktivní milník s kritérii a postup z `done.confirmed`."""
    from backend.brain_opora.determinism import tokens
    from backend.canvas.test_canvas_plan import HEADERS, SCOPE, seed

    agent = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        seed(client)  # oblast a0, karta n0
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        service = app.state.service
        body = {**SCOPE, "area": "a0", "title": "Stará oblast hotová",
                "criteria": [{"text": "Stará karta uzavřená", "cards": ["n0"]}]}
        assert client.post("/api/brain/heart/milestone", headers=HEADERS, json=body).json()["code"] == "gate_token_invalid"
        heart = {**HEADERS, tokens.HEADER: tokens.issue_heart(service, "draft", "draft")[1]}
        ui = dict(client.cookies)
        client.cookies.clear()  # srdce nemá doklad UI
        made = client.post("/api/brain/heart/milestone", headers=heart, json=body)
        assert made.status_code == 201, made.text
        milestone = made.json()
        assert milestone["status"] == "proposed" and milestone["criteria"] == [
            {"id": "c1", "text": "Stará karta uzavřená", "cards": ["n0"]}]
        assert client.post("/api/brain/heart/milestone", headers=heart, json={**body, "area": "n0"}
                           ).json()["code"] == "area_not_found"
        assert client.post("/api/brain/heart/milestone", headers=heart, json={**body, "extra": 1}
                           ).json()["code"] == "invalid_payload"
        view = client.get("/api/intake", params=SCOPE).json()
        assert [item["id"] for item in view["areas"][0]["proposed"]] == [milestone["id"]]
        decision = {**SCOPE, "milestoneId": milestone["id"], "action": "activate"}
        assert client.post("/api/intake/milestone", headers=agent, json=decision).status_code == 403
        client.cookies.update(ui)  # člověk v UI
        done =client.post("/api/intake/milestone", headers=HEADERS, json=decision)
        assert done.status_code == 200 and done.json() == {"id": milestone["id"], "status": "active", "superseded": None}
        assert client.post("/api/intake/milestone", headers=HEADERS, json=decision).status_code == 409
        active = client.get("/api/intake", params=SCOPE).json()["areas"][0]["milestone"]
        assert (active["done"], active["progress"], active["criteria"][0]["done"]) == (False, 0, False)
        db = service.db_for("draft")
        with db:
            db.execute("UPDATE desktop_v3_state SET state=json_set(state, '$.nodes.n0.done', json('{\"confirmed\":true}'))"
                       " WHERE project_id='draft' AND workspace_id='draft'")
        active = client.get("/api/intake", params=SCOPE).json()["areas"][0]["milestone"]
        assert (active["done"], active["progress"], active["criteria"][0]["cards"]) == (
            True, 100, [{"id": "n0", "done": True}])
        text = client.get("/api/brain/heart/snapshot", params=SCOPE).json()["snapshot"]
        assert f"- milník {milestone['id']} „Stará oblast hotová“ splněn – odložené požadavky k otevření: žádné" in text


def test_agent_decides_a_milestone_only_with_full_autonomy(tmp_path):
    """Brána milníku čte oprávnění, ne původce (docs/plna-autonomie-agenta.md §2): agent bez autonomie 403,
    s plnou autonomií projde."""
    from backend.canvas.test_canvas_plan import HEADERS, SCOPE, seed

    agent = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        seed(client)
        db = app.state.service.db_for("draft")
        for index in (1, 2, 3, 4):
            with db:
                from database.repositories.intake_milestones import IntakeMilestones
                IntakeMilestones(db).insert({"id": f"ms_{index}", "workspaceId": "draft", "areaId": "a0",
                                             "title": f"M{index}", "criteria": [{"id": "c1", "text": "x", "cards": ["n0"]}],
                                             "status": "proposed", "createdAt": "2026-10-30T10:00:00Z"})
        decision = {**SCOPE, "milestoneId": "ms_1", "action": "activate"}
        assert client.post("/api/intake/milestone", headers=agent, json=decision).status_code == 403
        assert client.post("/api/project-settings/agent-autonomy", headers=HEADERS,
                           json={"project": "draft", "full": True}).status_code == 200
        done = client.post("/api/intake/milestone", headers=agent, json=decision)
        assert done.status_code == 200 and done.json()["status"] == "active", done.text
        rejected = client.post("/api/intake/milestone", headers=agent, json={**decision, "milestoneId": "ms_2", "action": "reject"})
        assert rejected.status_code == 200 and rejected.json()["status"] == "superseded"


def test_heart_token_decides_a_milestone_only_when_project_autonomy_is_on(tmp_path):
    """Token srdce má oprávnění vždy, ale o milníku rozhodne jen při zapnuté plné autonomii projektu."""
    from backend.brain_opora.determinism import tokens
    from backend.canvas.test_canvas_plan import HEADERS, SCOPE, seed

    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        seed(client)
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        db = app.state.service.db_for("draft")
        from database.repositories.intake_milestones import IntakeMilestones
        for index in (1, 2):
            with db:
                IntakeMilestones(db).insert({"id": f"ms_{index}", "workspaceId": "draft", "areaId": "a0",
                                             "title": f"M{index}", "criteria": [{"id": "c1", "text": "x", "cards": ["n0"]}],
                                             "status": "proposed", "createdAt": "2026-10-30T10:00:00Z"})
        heart = {**HEADERS, tokens.HEADER: tokens.issue_heart(app.state.service, "draft", "draft")[1]}
        ui = dict(client.cookies)
        client.cookies.clear()
        decision = {**SCOPE, "milestoneId": "ms_1", "action": "activate"}
        refused = client.post("/api/intake/milestone", headers=heart, json=decision)
        assert refused.status_code == 403 and "Velínu" in refused.text
        client.cookies.update(ui)
        assert client.post("/api/project-settings/agent-autonomy", headers=HEADERS,
                           json={"project": "draft", "full": True}).status_code == 200
        client.cookies.clear()
        done = client.post("/api/intake/milestone", headers=heart, json=decision)
        assert done.status_code == 200 and done.json()["status"] == "active", done.text
