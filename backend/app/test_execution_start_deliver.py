"""Obřad karty na 2 volání (docs/navrhy/2026-10-28-zefektivneni-opory.md §3): `start` → práce → `deliver`.

Lokální projekt bez GitHubu, plná autonomie: agent kartu převezme jedním voláním, commitne v pracovní kopii
a jedním voláním ji odevzdá (kroky, výsledek, lokální sloučení, kontrola, uzavření). Varianta: vlastní dávka
`canvas-plan` mezi `start` a `deliver` změní rozsah kontextu karty → server ho přepne (re-pin) a `deliver`
projde; cizí změna dál vrací 409 s nápovědou „spusť start znovu“.
"""
import time

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_local_merge_autonomy import (
    AGENT,
    HUB,
    accept_baseline,
    card_entry,
    head,
    local_project,
    ok,
    plan_card,
    state,
)
from backend.canvas.test_canvas_plan import ORIGIN
from backend.canvas.test_opora_folder_repository import git

OTHER = {**AGENT, "X-Opora-Actor": "agent; name=jiny"}


class Counter:
    """Počítá volání API na kartu (start + deliver), ostatní volání testu jsou příprava a ověření."""

    def __init__(self, client):
        self.client, self.calls = client, 0

    def post(self, path, **kwargs):
        self.calls += 1
        return self.client.post(path, **kwargs)


def ready(client, tmp_path):
    repo, scope = local_project(client, tmp_path)
    ok(client.post("/api/project-settings/agent-autonomy", headers={"origin": ORIGIN},
                   json={"project": scope["project"], "full": True}))
    card = plan_card(client, scope)
    accept_baseline(client, scope)
    for verb in ("propose_graph", "accept"):  # kontext v2 potřebuje přijatý graf plánu
        action = next(item for item in state(client, scope)["actions"] if item["verb"] == verb and item["status"] == "ready")
        ok(client.post(action["path"], headers=AGENT, json={**scope, **action["preconditions"]}))
    return repo, scope, card


def commit_card(repo, card, name="modul.py"):
    (repo / name).write_text("VALUE = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Modul karty", "-m", f"Opora-Node: {card}")
    return head(repo)


def start(api, scope, card, headers=AGENT):
    return api.post(HUB + "/executions/start", headers=headers, json={**scope, "nodeId": card})


def deliver(api, scope, started, **extra):
    body = {**scope, "summary": "Modul hotový, testy zelené.",
            "steps": [{"stepId": "s1", "status": "done"}, {"stepId": "s2", "status": "done", "notes": "pytest"}],
            "checks": [{"name": "npm test", "status": "green", "output": "2 passed"}], **extra}
    return api.post(f"{HUB}/executions/{started['executionId']}/deliver",
                    headers={**AGENT, "X-Opora-Execution-Token": started["token"]}, json=body)


def test_card_ceremony_is_two_calls(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope, card = ready(client, tmp_path)
        api = Counter(client)
        started = ok(start(api, scope, card))
        assert [item["id"] for item in started["steps"]] == ["s1", "s2"]
        assert started["next"]["verb"] == "deliver" and started["resumed"] is False
        # Idempotence: týž aktér s živým převzetím dostane stávající běh (nepočítá se, je to jen ověření).
        again = ok(start(client, scope, card))
        assert again["executionId"] == started["executionId"] and again["resumed"] is True

        sha = commit_card(repo, card)
        delivered = ok(deliver(api, scope, started))
        assert api.calls == 2
        assert delivered["closed"] is True and delivered["missing"] == [], delivered
        assert delivered["merged"] == sha and delivered["checks"] == 1
        assert delivered["next"]["verb"] == "pick"
        entry = card_entry(client, scope, card)
        assert entry["dod"]["done"] is True, entry["dod"]
        receipt = ok(client.get(f"{HUB}/executions/{started['executionId']}/results",
                                params=scope, headers=AGENT))["results"][-1]["result"]
        notes = {item["stepId"]: item["evidence"]["notes"] for item in receipt["stepResults"]}
        assert notes == {"s1": "Modul karty", "s2": "pytest"}  # krok bez notes = předmět commitu karty
        assert receipt["selfChecks"]["headSha"] == sha and receipt["selfChecks"]["checks"][0]["status"] == "passed"


def test_red_check_stops_the_close_and_says_what_next(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        commit_card(repo, card)
        red = ok(deliver(client, scope, started, checks=[{"name": "npm test", "status": "red"}]))
        assert red["closed"] is False and "gate_ready" in red["missing"], red
        assert red["next"]["verb"] == "deliver" and "npm test=green" in red["next"]["command"]
        # Oprava: druhé odevzdání téhož běhu přeskočí výsledek a uzavře kartu.
        fixed = ok(deliver(client, scope, started))
        assert fixed["closed"] is True and fixed["delivered"]["receiptId"] == red["delivered"]["receiptId"]


def test_invalid_body_is_422_with_field(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        bad = deliver(client, scope, started, steps=[{"stepId": "s9", "status": "done"}])
        assert bad.status_code == 422 and bad.json()["field"] == "steps[].stepId", bad.text
        wrong = client.post(HUB + "/executions/start", headers=AGENT, json={**scope, "node": card})
        assert wrong.status_code == 422 and wrong.json()["code"] == "invalid_payload", wrong.text


def test_own_plan_change_repins_the_context_and_deliver_passes(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        digest = ok(client.get("/api/view", params=scope))["digest"]
        plan = {"nodes": [{"ref": "pod", "kind": "node", "parent": "@" + card, "name": "Podkarta"}],
                "edges": [], "decisions": []}
        batch = ok(client.post("/api/canvas-plan", headers=AGENT, json={**scope, "digest": digest, "plan": plan}))
        assert batch["rePinned"] == [started["executionId"]], batch
        commit_card(repo, card)
        delivered = ok(deliver(client, scope, started))
        assert delivered["closed"] is True, delivered


def test_foreign_plan_change_is_409_with_start_hint(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        digest = ok(client.get("/api/view", params=scope))["digest"]
        plan = {"nodes": [{"ref": "pod", "kind": "node", "parent": "@" + card, "name": "Cizí podkarta"}],
                "edges": [], "decisions": []}
        batch = ok(client.post("/api/canvas-plan", headers=OTHER, json={**scope, "digest": digest, "plan": plan}))
        assert "rePinned" not in batch
        commit_card(repo, card)
        refused = deliver(client, scope, started)
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "execution_context_changed" and "start" in refused.json()["hint"]


def test_expired_lease_is_accepted_on_deliver_and_logged(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        db = client.app.state.service.db_for(scope["project"])
        with db:
            db.execute("UPDATE card_leases SET expires_at=? WHERE node_id=?", (time.time() - 1, card))
        commit_card(repo, card)
        delivered = ok(deliver(client, scope, started))
        assert delivered["leaseRenewed"] is True and delivered["closed"] is True, delivered
        log = ok(client.get("/api/activity-log", params={**scope, "actor": "agent"}))["entries"]
        assert any(item["summary"].startswith("lease_renewed_on_deliver") for item in log)
