"""Žádosti srdci a operace L7e přes skutečnou aplikaci: idempotentní POST /work, pokus, kroky jen agentem, deník."""
from fastapi.testclient import TestClient

from backend.api.agi_pletor.test_linie_routes import AGENT, BASE, JSON, repo  # noqa: F401 (fixture)
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

Q = {"project": "draft"}
WORK = {"title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"], "branch": "feat/uzel",
        "baseBranch": "develop", "target": "develop"}


def test_requests_work_attempt_and_journal(tmp_path, repo):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        made = client.post("/api/pletor/requests", headers=JSON, params=Q, json={"text": "Uzel", "idempotencyKey": "r1"})
        assert made.status_code == 200 and [s["k"] for s in made.json()["steps"]] == ["accepted"]
        rid = made.json()["id"]
        again = client.post("/api/pletor/requests", headers=JSON, params=Q, json={"text": "Jiné", "idempotencyKey": "r1"})
        assert again.status_code == 409 and again.json()["code"] == "idempotency_conflict"

        body = {**WORK, "requestId": rid, "idempotencyKey": "w1"}
        first = client.post(f"{BASE}/work", headers=HEADERS, params={**Q, "workspace": "main"}, json=body)
        second = client.post(f"{BASE}/work", headers=HEADERS, params={**Q, "workspace": "main"}, json=body)
        assert first.status_code == second.status_code == 200
        tid = first.json()["ticketId"]
        assert second.json()["ticketId"] == tid and first.json()["work"]["requestId"] == rid
        clash = client.post(f"{BASE}/work", headers=HEADERS, params={**Q, "workspace": "main"},
                            json={**body, "title": "Jiný"})
        assert clash.status_code == 409 and clash.json()["code"] == "idempotency_conflict"

        step = {"k": "ticket", "evidence": {"ticket": tid}}
        human = client.post(f"/api/pletor/requests/{rid}/steps", headers=JSON, params=Q, json=step)
        assert human.status_code == 403 and human.json()["code"] == "agent_only"
        assert client.post(f"/api/pletor/requests/{rid}/steps", headers=AGENT, params=Q, json=step).status_code == 200
        bare = client.post(f"/api/pletor/requests/{rid}/steps", headers=AGENT, params=Q, json={"k": "plan"})
        assert bare.status_code == 422 and bare.json()["code"] == "evidence_required"

        tried = client.post(f"{BASE}/work/{tid}/attempt", headers=AGENT, params=Q,
                            json={"branch": "feat/uzel", "requestId": rid, "idempotencyKey": "a1"})
        assert tried.status_code == 200 and tried.json()["work"]["attempts"][0]["createdBy"] == "agent"
        shown = client.get(f"/api/pletor/requests/{rid}", headers=HEADERS, params=Q).json()
        assert [s["k"] for s in shown["steps"]] == ["accepted", "ticket", "attempt"]
        listed = client.get("/api/pletor/requests", headers=HEADERS, params={**Q, "open": 1}).json()
        assert listed["open"] == 1 and listed["requests"][0]["id"] == rid

        blocked = client.post(f"{BASE}/work/{tid}/block", headers=AGENT, params=Q, json={"reason": "API"})
        assert blocked.json()["work"]["blocked"]["by"] == "agent:dev"
        assert client.post(f"{BASE}/work/{tid}/unblock", headers=JSON, params=Q).json()["work"]["blocked"] is None

        log = client.get(f"{BASE}/journal", headers=HEADERS, params=Q).json()
        kinds = [e["kind"] for e in log["events"]]
        assert kinds == ["linie.request.accepted", "linie.work.created", "linie.request.step", "linie.attempt",
                         "linie.request.step", "linie.block", "linie.unblock"]
        tail = client.get(f"{BASE}/journal", headers=HEADERS, params={**Q, "after": log["events"][-2]["id"]}).json()
        assert [e["kind"] for e in tail["events"]] == ["linie.unblock"] and tail["lastId"] == log["lastId"]
