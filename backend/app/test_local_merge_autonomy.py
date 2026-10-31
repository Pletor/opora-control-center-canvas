"""Lokální sloučení karty (docs/lokalni-slouceni.md): agent s plnou autonomií projde celou cestu karty sám.

Lokální projekt = složka s Git repem bez vzdáleného repa (žádná vazba na GitHub) → brána `local`.
Cesta: dávka plánu s kartou a `spec.steps` → přijetí zadání → claim → kroky `done` → přijetí karty →
commit v repu → `local-merge` → `cards[].dod` (gate `local`, gate_ready, merged, plan_written_back) →
`close_card` → karta `done`. Žádný krok nedělá člověk kromě zapnutí autonomie.
"""
import copy
import subprocess

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.canvas.test_opora_folder_repository import checkout, git

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=t"}
HUB = "/api/oporahub"
STEPS = [{"id": "s1", "order": 1, "title": "Napsat modul", "acceptance": ["modul existuje"], "dependsOn": []},
         {"id": "s2", "order": 2, "title": "Otestovat", "acceptance": ["testy projdou"], "dependsOn": ["s1"]}]


def head(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()


def local_project(client, tmp_path):
    repo = checkout(tmp_path, origin=None)
    created = client.post("/api/local-project", headers=HEADERS,
                          json={"path": str(repo), "name": "Lokál", "confirmed": True})
    assert created.status_code == 200, created.text
    return repo, {"project": created.json()["id"], "workspace": "draft"}


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def plan_card(client, scope):
    digest = client.get("/api/view", params=scope).json()["digest"]
    plan = {"nodes": [{"ref": "sektor", "kind": "sector", "parent": None, "name": "Modul"},
                      {"ref": "karta", "kind": "node", "parent": "sektor", "name": "[task] Modul",
                       "spec": {"goal": "Modul existuje.", "acceptance": "testy projdou", "steps": STEPS}}],
            "edges": [], "decisions": []}
    return ok(client.post("/api/canvas-plan", headers=AGENT, json={**scope, "digest": digest, "plan": plan}))["refs"]["karta"]


def accept_baseline(client, scope):
    context = ok(client.get(HUB + "/changesets/context", params=scope, headers=AGENT))
    return ok(client.post(HUB + "/baselines", headers=AGENT, json={
        **scope, "subject": "Zadání", "expectedAcceptedHead": None, "expectedGraphDigest": context["graphDigest"],
        "expectedSpecificationsVersion": context["specificationsVersion"]}))


def state(client, scope):
    return ok(client.get(HUB + "/agent-state", params=scope, headers=AGENT))


def claim(client, scope, card):
    action = next(item for item in state(client, scope)["actions"]
                  if item["verb"] == "claim" and item["targetId"] == card)
    assert action["status"] == "ready", action
    return ok(client.post(HUB + "/executions/claim", headers=AGENT,
                          json={**scope, "nodeId": card, "requestId": "claim-1", "ttlSeconds": 600,
                                **action["preconditions"]}))


def submit_steps(client, scope, record):
    done = [{"stepId": step["id"], "status": "done",
             "evidence": {"notes": "hotovo", "commits": ["abc1234"], "checks": ["pytest"]}} for step in STEPS]
    ok(client.post(f"{HUB}/executions/{record['executionId']}/results", headers=AGENT, json={
        **scope, "token": record["token"], "epoch": record["epoch"], "requestId": "result-1",
        "result": {"summary": "Modul hotový", "stepResults": done}}))


def card_entry(client, scope, card):
    return next(item for item in state(client, scope)["cards"] if item["nodeId"] == card)


def close_card(client, scope, card):
    current = ok(client.get("/api/desktop-v3/state", params=scope))
    nodes = copy.deepcopy(current["state"])
    # Karta bez bloků ještě nemá záznam ve stavu; uzavření ho založí jako UI.
    nodes["nodes"].setdefault(card, {"phase": "discover", "criteria": [], "steps": []})["done"] = {"confirmed": True, "by": "agent", "at": "2026-10-28T12:00:00Z", "note": "hotovo"}
    return client.post("/api/desktop-v3/state", headers=AGENT,
                       json={**scope, "expectedRevision": current["revision"], "state": nodes})


def test_agent_with_full_autonomy_closes_a_local_card_alone(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope = local_project(client, tmp_path)
        ok(client.post("/api/project-settings/agent-autonomy", headers=HEADERS,
                       json={"project": scope["project"], "full": True}))
        card = plan_card(client, scope)
        accept_baseline(client, scope)
        record = claim(client, scope, card)
        submit_steps(client, scope, record)
        dod = card_entry(client, scope, card)["dod"]
        assert dod["gate"] == "local" and dod["steps"] and dod["card_acceptance"], dod
        assert dod["missing"] == ["gate_ready", "merged", "plan_written_back", "human_close"], dod
        # Bez sloučení karta neuzavře.
        assert close_card(client, scope, card).status_code == 409

        (repo / "modul.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "modul")
        commit = head(repo)
        path = f"{HUB}/executions/{record['executionId']}/local-merge"
        bad = client.post(path, headers=AGENT, json={**scope, "commit": "0" * 40})
        assert bad.status_code == 422, bad.text
        merged = ok(client.post(path, headers=AGENT, json={**scope, "commit": commit}))
        assert merged["state"] == "merged" and merged["source"] == "local" and merged["commit"] == commit
        assert merged["planWrittenBack"] is True
        # Idempotence: týž commit vrátí stejnou vazbu.
        assert ok(client.post(path, headers=AGENT, json={**scope, "commit": commit}))["commit"] == commit

        dod = card_entry(client, scope, card)["dod"]
        assert dod["gate"] == "local" and dod["gate_ready"] and dod["merged"] and dod["plan_written_back"], dod
        assert dod["missing"] == ["human_close"], dod
        close = next(item for item in state(client, scope)["actions"] if item["verb"] == "close_card")
        # Uzavření je deterministické: kartu uzavře server sám (docs/oporahub-plan-steps.md), nikdo na ni nečeká.
        assert close["targetId"] == card and close["preconditions"]["gate"] == "local", close
        assert close["preconditions"]["missing"] == [] and close["blockReason"] == "server_closes", close
        assert not [item for item in state(client, scope)["decisions"] if item["kind"] == "close_card"]
        # Ruční uzavření zůstává možností.

        closed = close_card(client, scope, card)
        assert closed.status_code == 200, closed.text
        entry = card_entry(client, scope, card)
        assert entry["dod"]["done"] is True and entry["dod"]["missing"] == [], entry["dod"]
        assert ok(client.get("/api/desktop-v3/state", params=scope))["state"]["nodes"][card]["done"]["by"] == "agent"
        log = ok(client.get("/api/activity-log", params={**scope, "actor": "agent"}))["entries"]
        entry = next(item for item in log if item["path"].endswith("/local-merge") and item["status"] == 200)
        assert "local_merge" in entry["summary"] and commit in entry["summary"] and entry["agent"] == "t"


def test_local_merge_refuses_commit_outside_the_branch(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope = local_project(client, tmp_path)
        ok(client.post("/api/project-settings/agent-autonomy", headers=HEADERS,
                       json={"project": scope["project"], "full": True}))
        card = plan_card(client, scope)
        accept_baseline(client, scope)
        record = claim(client, scope, card)
        submit_steps(client, scope, record)
        git(repo, "checkout", "-b", "vedle")
        (repo / "vedle.py").write_text("X = 1\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "vedle")
        aside = head(repo)
        git(repo, "checkout", "main")
        path = f"{HUB}/executions/{record['executionId']}/local-merge"
        refused = client.post(path, headers=AGENT, json={**scope, "commit": aside})
        assert refused.status_code == 409, refused.text
        assert client.post(path, headers=AGENT, json={**scope, "commit": "nehex"}).status_code == 422
        # Jiný commit nahradí starší lokální vazbu.
        first = ok(client.post(path, headers=AGENT, json={**scope, "commit": head(repo)}))["commit"]
        git(repo, "merge", "--no-ff", "-m", "slouceni", "vedle")
        second = ok(client.post(path, headers=AGENT, json={**scope, "commit": head(repo)}))
        assert second["commit"] != first and second["state"] == "merged"


def test_without_autonomy_agent_reports_the_merge_but_a_human_closes(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope = local_project(client, tmp_path)
        card = plan_card(client, scope)
        assert client.post(HUB + "/baselines", headers=AGENT, json={**scope}).status_code in (403, 409)
        context = ok(client.get(HUB + "/changesets/context", params=scope, headers=HEADERS))
        ok(client.post(HUB + "/baselines", headers=HEADERS, json={
            **scope, "subject": "Zadání", "expectedAcceptedHead": None, "expectedGraphDigest": context["graphDigest"],
            "expectedSpecificationsVersion": context["specificationsVersion"]}))
        record = claim(client, scope, card)
        submit_steps(client, scope, record)
        # Vlastní odevzdaný běh: ohlášení sloučení je práce agenta, ne lidská brána.
        merged = ok(client.post(f"{HUB}/executions/{record['executionId']}/local-merge", headers=AGENT,
                                json={**scope, "commit": head(repo)}))
        assert merged["source"] == "local" and merged["number"] is None
        assert card_entry(client, scope, card)["dod"]["missing"] == ["human_close"]
        refused = close_card(client, scope, card)
        assert refused.status_code in (403, 409), refused.text  # 409: zapsaná karta bere jen výsledky běhu
        current = ok(client.get("/api/desktop-v3/state", params=scope))
        nodes = copy.deepcopy(current["state"])
        nodes["nodes"].setdefault(card, {"phase": "discover", "criteria": [], "steps": []})["done"] = {
            "confirmed": True, "by": "human", "at": "2026-10-28T12:00:00Z", "note": "hotovo"}
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json={
            **scope, "expectedRevision": current["revision"], "state": nodes}).status_code == 200
        assert card_entry(client, scope, card)["dod"]["done"] is True
