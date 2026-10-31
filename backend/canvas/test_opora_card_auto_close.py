"""Deterministic card close (docs/oporahub-plan-steps.md): a merged, written-back card whose definition of done
misses only `human_close` is closed by the server itself, without a human, an agent or full autonomy."""
import copy

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_local_merge_autonomy import (
    AGENT,
    HUB,
    accept_baseline,
    card_entry,
    claim,
    head,
    local_project,
    ok,
    plan_card,
    state,
    submit_steps,
)
from backend.canvas.opora_card_auto_close import close_card, sweep
from backend.canvas.opora_execution_pr_manager import ExecutionPullRequestManager
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN


def human_baseline(client, scope):
    context = ok(client.get(HUB + "/changesets/context", params=scope, headers=HEADERS))
    ok(client.post(HUB + "/baselines", headers=HEADERS, json={
        **scope, "subject": "Zadání", "expectedAcceptedHead": None, "expectedGraphDigest": context["graphDigest"],
        "expectedSpecificationsVersion": context["specificationsVersion"]}))


def merged_card(client, tmp_path, autonomy=False):
    """Today's waiting card: merged + plan written back, `dod.missing == ["human_close"]`, project without autonomy."""
    repo, scope = local_project(client, tmp_path)
    if autonomy:
        ok(client.post("/api/project-settings/agent-autonomy", headers=HEADERS,
                       json={"project": scope["project"], "full": True}))
    card = plan_card(client, scope)
    (accept_baseline if autonomy else human_baseline)(client, scope)
    record = claim(client, scope, card)
    submit_steps(client, scope, record)
    return scope, card, record, repo


def test_server_closes_a_merged_written_back_card_without_a_human(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        service = client.app.state.service
        scope, card, record, repo = merged_card(client, tmp_path)
        # Before the merge the definition of done is not met: nothing to close.
        assert sweep(service, scope["project"]) == []
        ok(client.post(f"{HUB}/executions/{record['executionId']}/local-merge", headers=AGENT,
                       json={**scope, "commit": head(repo)}))
        waiting = card_entry(client, scope, card)
        assert waiting["dod"]["missing"] == ["human_close"] and waiting["reason"] == "awaiting_human_close", waiting

        assert sweep(service, scope["project"]) == [card]
        done = ok(client.get("/api/desktop-v3/state", params=scope))["state"]["nodes"][card]["done"]
        assert done["confirmed"] is True and done["by"] == "opora", done
        entry = card_entry(client, scope, card)
        assert entry["reason"] == "card_closed" and entry["dod"]["done"] is True and entry["dod"]["missing"] == []
        assert not [item for item in state(client, scope)["actions"] if item["verb"] == "close_card"]
        log = ok(client.get("/api/activity-log", params={**scope, "actor": "agent"}))["entries"]
        closed = next(item for item in log if item["agent"] == "opora")
        assert closed["nodeIds"] == [card] and "card_auto_close" in closed["summary"], closed
        # Idempotent: a closed card is left alone.
        assert sweep(service, scope["project"]) == []
        assert close_card(service, scope["project"], scope["workspace"], card) is False


def test_pr_loop_runs_the_close_on_its_first_tick_and_then_by_interval(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_CARD_AUTO_CLOSE_SECONDS", "30")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        service = client.app.state.service
        scope, card, record, repo = merged_card(client, tmp_path)
        now = [1000.0]
        manager = ExecutionPullRequestManager(service, clock=lambda: now[0])
        manager._close_cards(scope["project"])  # first tick: nothing merged yet
        ok(client.post(f"{HUB}/executions/{record['executionId']}/local-merge", headers=AGENT,
                       json={**scope, "commit": head(repo)}))
        now[0] += 10
        manager._close_cards(scope["project"])  # inside the interval: not re-evaluated
        assert card_entry(client, scope, card)["reason"] == "awaiting_human_close"
        now[0] += 30
        manager._close_cards(scope["project"])  # like the first tick after a restart
        assert card_entry(client, scope, card)["reason"] == "card_closed"
        manager.close()


def test_only_the_server_writes_a_close_by_opora(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope, card, record, repo = merged_card(client, tmp_path)
        ok(client.post(f"{HUB}/executions/{record['executionId']}/local-merge", headers=AGENT,
                       json={**scope, "commit": head(repo)}))
        current = ok(client.get("/api/desktop-v3/state", params=scope))
        nodes = copy.deepcopy(current["state"])
        nodes["nodes"].setdefault(card, {"phase": "discover", "criteria": [], "steps": []})["done"] = {
            "confirmed": True, "by": "opora", "at": "2026-10-31T12:00:00Z", "note": "podvrh"}
        forged = client.post("/api/desktop-v3/state", headers=HEADERS,
                             json={**scope, "expectedRevision": current["revision"], "state": nodes})
        assert forged.status_code in (400, 409, 422), forged.text
        assert not ok(client.get("/api/desktop-v3/state", params=scope))["state"]["nodes"].get(card, {}).get("done", {}).get("confirmed")


def test_deliver_closes_through_the_server_without_full_autonomy(tmp_path):
    """`deliver` no longer needs full autonomy for the close: the server closes a met definition of done."""
    from backend.canvas.opora_execution_deliver import deliver
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        service = client.app.state.service
        scope, card, record, repo = merged_card(client, tmp_path)
        result = deliver(service, record["executionId"], {**scope, "summary": "Modul hotový", "commit": head(repo)},
                         record["token"], "agent")
        assert result["closed"] is True and result["missing"] == [] and result["next"]["verb"] == "pick", result
        done = ok(client.get("/api/desktop-v3/state", params=scope))["state"]["nodes"][card]["done"]
        assert done["by"] == "opora"
