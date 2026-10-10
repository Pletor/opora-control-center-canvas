"""Pipeline karty: router určí proces, agent etapy jen přidává a hlásí stav; server hlídá pořadí,
nezávislost, GOAL, podlahu a smyčku oprav. Člověk proces jen sleduje a přepíná."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.card_pipeline import MAX_RETRIES, validate_stages
from backend.editor.agent_memory.test_agent_output import EMPTY, HEADERS, ORIGIN, SCOPE, output, send
from backend.editor.agent_memory.test_completion_evidence import evidence

ROUTER = {**HEADERS, "X-Opora-Actor": "agent; name=router-1"}
AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=worker"}
CARD = {"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0}
GRAPH = {"nodes": [CARD], "edges": []}
TASK_GRAPH = {"nodes": [{**CARD, "name": "[task] Ohnisko"}], "edges": []}
GOAL_GRAPH = {"nodes": [{**CARD, "goal_mode": "until_checks_pass",
                         "checks": [{"id": "unit", "command": "uv run pytest"}]}], "edges": []}


def stage(sid, kind, lens="", **overrides):
    item = {"id": sid, "kind": kind, "lens": lens, "title": f"Etapa {sid}", "brief": "", "status": "todo",
            "note": "", "by": "human", "approved": True, "doneBy": "", "at": ""}
    item.update(overrides)
    return item


def pipeline():
    return {"profile": "code", "items": [stage("work", "work"), stage("test", "test"),
                                         stage("hacker", "critic", "hacker")]}


def state_with(stages):
    value = copy.deepcopy(EMPTY)
    node = {"phase": "discover", "criteria": [], "steps": []}
    if stages:
        node["stages"] = stages
    value["nodes"] = {"focus": node}
    return value


def prepared(client, stages=None, graph=GRAPH, routed=True):
    view = client.get("/api/view", params=SCOPE).json()
    assert client.post("/api/graph", headers=HEADERS,
                       json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200
    saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                        json={**SCOPE, "expectedRevision": 0,
                              "state": state_with((stages or pipeline()) if routed else None)})
    assert saved.status_code == 200, saved.text
    return saved.json()


def route(client, revision, headers=ROUTER, **body):
    return client.post("/api/desktop-v3/pipeline", headers=headers, json={
        **SCOPE, "nodeId": "focus", "expectedRevision": revision, "op": "route", "reason": "Kód backendu.", **body})


def report(client, revision, stages, agent="worker", **extra):
    body = {**SCOPE, "nodeId": "focus", "expectedRevision": revision, "agent": agent,
            "output": output(blocks=[], reports=[], decisions=[], done={"proposed": False, "note": ""},
                             stages=stages, **extra)}
    return send(client, body)


def items_of(response):
    return response.json()["state"]["nodes"]["focus"]["stages"]["items"]


def routed_stages(response):
    """Štíhlá odpověď POST /pipeline (karta P3): jen revize, karta a její nová pipeline, žádný stav."""
    value = response.json()
    assert "state" not in value and value["nodeId"] == "focus" and type(value["revision"]) is int
    return value["stages"]


def test_shape_rejects_unknown_kind_lens_and_dangling_retry():
    validate_stages(pipeline())
    for broken in (stage("x", "deploy"), stage("x", "critic"), stage("x", "test", "hacker"),
                   stage("x", "test", retryOf="nobody")):
        with pytest.raises(ValueError):
            validate_stages({"profile": "code", "items": [broken]})


def test_router_routes_from_server_profile_and_frontier_dispatches_the_session(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, routed=False)["revision"]
        frontier = client.get("/api/desktop-v3/frontier", params=SCOPE).json()
        assert [row["id"] for row in frontier["needsRouting"]] == ["focus"]
        routed = route(client, revision, profile="security")
        assert routed.status_code == 200, routed.text
        stages = routed_stages(routed)
        assert stages == client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]["focus"]["stages"]
        assert stages["routedBy"] == "router-1" and stages["reason"] == "Kód backendu."
        assert all(item["approved"] and item["by"] == "agent" for item in stages["items"])
        frontier = client.get("/api/desktop-v3/frontier", params=SCOPE).json()
        assert frontier["needsRouting"] == []
        row = frontier["frontier"][0]["pipeline"]
        assert row["current"]["kind"] == "work" and row["total"] == len(stages["items"])
        profiles = client.get("/api/desktop-v3/pipeline-profiles").json()["profiles"]
        assert [p["id"] for p in profiles][:2] == ["goal", "code"]


def test_floor_rejects_a_weak_pipeline_from_the_router_but_not_from_a_human(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, graph=TASK_GRAPH, routed=False)["revision"]
        weak = route(client, revision, profile="custom", stages=[{"kind": "work", "lens": "", "title": "Hotovo", "brief": ""}])
        assert weak.status_code == 409 and "review" in weak.text and "kritik hacker" in weak.text and "test" in weak.text
        research = route(client, revision, profile="research")
        assert research.status_code == 409 and "test" in research.text
        human = route(client, revision, headers=HEADERS, profile="custom",
                      stages=[{"kind": "work", "lens": "", "title": "Ručně", "brief": ""}])
        assert human.status_code == 200, human.text
        assert routed_stages(human)["routedBy"] == "human"
        again = route(client, human.json()["revision"], profile="code")
        assert again.status_code == 403


def test_agent_adds_stages_without_a_human_but_never_removes_reorders_or_skips(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        saved = prepared(client)
        added = client.post("/api/desktop-v3/pipeline", headers=AGENT, json={
            **SCOPE, "nodeId": "focus", "expectedRevision": saved["revision"], "op": "add", "reason": "Chybí kontrola UX.",
            "stages": [{"kind": "critic", "lens": "user", "title": "Kritik UX", "brief": ""}]})
        assert added.status_code == 200, added.text
        assert routed_stages(added)["items"][0]["title"] == "Kritik UX" and routed_stages(added)["items"][0]["approved"] is True
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert stored["revision"] == added.json()["revision"] and stored["state"]["nodes"]["focus"]["stages"] == routed_stages(added)
        for mutate in (lambda s: s["items"].pop(0),
                       lambda s: s["items"][0].update(status="skipped"),
                       lambda s: s["items"].reverse(),
                       lambda s: s.update(profile="design"),
                       lambda s: s["items"][1].update(brief="nic")):
            broken = copy.deepcopy(stored["state"])
            mutate(broken["nodes"]["focus"]["stages"])
            refused = client.post("/api/desktop-v3/state", headers=AGENT,
                                  json={**SCOPE, "expectedRevision": added.json()["revision"], "state": broken})
            assert refused.status_code == 403, refused.text


def test_stages_pass_in_order_with_handoff_and_critic_needs_another_session(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)["revision"]
        early = report(client, revision, [{"id": "test", "status": "passed", "note": "zelené"}])
        assert early.status_code == 409 and "předchozími" in early.text
        silent = report(client, revision, [{"id": "work", "status": "passed", "note": " "}])
        assert silent.status_code == 409 and "předávku" in silent.text
        done = report(client, revision, [{"id": "work", "status": "passed", "note": "hotovo, viz diff"}])
        assert done.status_code == 200, done.text
        assert items_of(done)[0]["doneBy"] == "worker" and items_of(done)[0]["at"]
        revision = report(client, done.json()["revision"], [{"id": "test", "status": "passed", "note": "ok"}]).json()["revision"]
        self_review = report(client, revision, [{"id": "hacker", "status": "passed", "note": "nic"}])
        assert self_review.status_code == 409 and "jiná relace" in self_review.text
        critic = report(client, revision, [{"id": "hacker", "status": "passed", "note": "bez nálezu"}], agent="astra")
        assert critic.status_code == 200, critic.text


def test_failed_critic_queues_fix_and_retry_until_a_human_must_decide(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)["revision"]
        for sid in ("work", "test"):
            revision = report(client, revision, [{"id": sid, "status": "passed", "note": "ok"}]).json()["revision"]
        failing = "hacker"
        for loop in range(MAX_RETRIES + 1):
            failed = report(client, revision, [{"id": failing, "status": "failed", "note": f"obejde lease {loop}"}], agent="astra")
            assert failed.status_code == 200, failed.text
            items, revision = items_of(failed), failed.json()["revision"]
            if loop == MAX_RETRIES:
                break
            position = next(i for i, item in enumerate(items) if item["id"] == failing)
            fix, retry = items[position + 1], items[position + 2]
            assert fix["kind"] == "fix" and retry["retryOf"] == "hacker" and retry["kind"] == "critic"
            revision = report(client, revision, [{"id": fix["id"], "status": "passed", "note": "opraveno"}]).json()["revision"]
            failing = retry["id"]
        assert len(items) == 3 + 2 * MAX_RETRIES
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"}).json()
        assert brief["pipeline"]["stuck"] and any("Pipeline" in w["ask"] for w in brief["loop"]["waitingOnHuman"])
        frontier = client.get("/api/desktop-v3/frontier", params=SCOPE).json()
        assert frontier["waiting"][0]["id"] == "focus"


def test_failed_review_queues_fix_and_retry_like_critic(tmp_path):
    stages = {"profile": "code", "items": [stage("work", "work"), stage("review", "review"), stage("test", "test")]}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = report(client, prepared(client, stages)["revision"], [{"id": "work", "status": "passed", "note": "ok"}]).json()["revision"]
        failed = report(client, revision, [{"id": "review", "status": "failed", "note": "chybí práh"}], agent="reviewer")
        assert failed.status_code == 200, failed.text
        fix, retry = items_of(failed)[2], items_of(failed)[3]
        assert fix["kind"] == "fix" and "chybí práh" in fix["brief"]
        assert retry["kind"] == "review" and retry["retryOf"] == "review" and retry["status"] == "todo"


def test_repeated_failed_report_does_not_duplicate_the_queued_retry(tmp_path):
    stages = {"profile": "code", "items": [stage("work", "work"), stage("review", "review"), stage("user", "critic", "user")]}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = report(client, prepared(client, stages)["revision"], [{"id": "work", "status": "passed", "note": "ok"}]).json()["revision"]
        failed = report(client, revision, [{"id": "review", "status": "failed", "note": "nález"}], agent="reviewer")
        fix = items_of(failed)[2]
        revision = report(client, failed.json()["revision"], [{"id": fix["id"], "status": "passed", "note": "opraveno"}]).json()["revision"]
        again = report(client, revision, [{"id": "review", "status": "failed", "note": "nález znovu"}], agent="reviewer")
        assert again.status_code == 200, again.text
        assert sum(1 for item in items_of(again) if item.get("retryOf") == "review") == 1


def retry_op(client, revision, stage_id, headers=AGENT):
    return client.post("/api/desktop-v3/pipeline", headers=headers, json={
        **SCOPE, "nodeId": "focus", "expectedRevision": revision, "op": "retry", "stageId": stage_id,
        "reason": "Review selhalo bez opakování; oprava proběhla jinde."})


def test_stuck_stage_is_requeued_by_retry_op_until_loops_run_out(tmp_path):
    stuck_review = {"profile": "code", "items": [
        stage("work", "work", status="passed", note="ok", doneBy="worker"),
        stage("review", "review", status="failed", note="B1, B2", doneBy="reviewer"),
        stage("fix", "fix", status="passed", note="B1 opraveno", doneBy="fixer"),
        stage("test", "test", status="passed", note="zelené", doneBy="tester")]}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, stuck_review)["revision"]
        assert client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"}).json()["pipeline"]["stuck"]
        assert retry_op(client, revision, "test").status_code == 409
        queued = retry_op(client, revision, "review")
        assert queued.status_code == 200, queued.text
        items = routed_stages(queued)["items"]
        assert [item["id"] for item in items[:4]] == ["work", "review", "fix", "test"]
        assert items[4]["kind"] == "fix" and items[5]["retryOf"] == "review" and items[5]["by"] == "agent"
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"}).json()["pipeline"]
        assert not brief["stuck"] and brief["current"]["id"] == items[4]["id"]
        assert retry_op(client, queued.json()["revision"], "review").status_code == 409


def test_retry_op_refuses_agent_after_max_loops(tmp_path):
    items = [stage("work", "work", status="passed", note="ok", doneBy="worker"),
             stage("review", "review", status="failed", note="nález", doneBy="reviewer")]
    for loop in range(MAX_RETRIES):
        items += [stage(f"fix{loop}", "fix", status="passed", note="ok", doneBy="fixer"),
                  stage(f"review{loop}", "review", status="failed", note="pořád", doneBy="reviewer", retryOf="review")]
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, {"profile": "code", "items": items})["revision"]
        refused = retry_op(client, revision, f"review{MAX_RETRIES - 1}")
        assert refused.status_code == 403, refused.text


def test_passed_retry_supersedes_the_failed_stage_for_closure(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)["revision"]
        for sid in ("work", "test"):
            revision = report(client, revision, [{"id": sid, "status": "passed", "note": "ok"}]).json()["revision"]
        failed = report(client, revision, [{"id": "hacker", "status": "failed", "note": "díra"}], agent="astra")
        fix, retry = items_of(failed)[3], items_of(failed)[4]
        revision = report(client, failed.json()["revision"], [{"id": fix["id"], "status": "passed", "note": "záplata"}]).json()["revision"]
        passed = report(client, revision, [{"id": retry["id"], "status": "passed", "note": "drží"}], agent="astra")
        assert passed.status_code == 200, passed.text
        state = passed.json()["state"]
        state["nodes"]["focus"]["evidence"] = evidence()
        state["nodes"]["focus"]["done"] = {"confirmed": True, "at": "2026-10-07T12:00:00+00:00", "by": "human", "note": ""}
        closed = client.post("/api/desktop-v3/state", headers=HEADERS,
                             json={**SCOPE, "expectedRevision": passed.json()["revision"], "state": state})
        assert closed.status_code == 200, closed.text


def test_goal_test_stage_needs_green_checks(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, graph=GOAL_GRAPH)["revision"]
        revision = report(client, revision, [{"id": "work", "status": "passed", "note": "ok"}]).json()["revision"]
        red = report(client, revision, [{"id": "test", "status": "passed", "note": "ok"}])
        assert red.status_code == 409 and "GOAL" in red.text
        green = report(client, revision, [{"id": "test", "status": "passed", "note": "ok"}], evidence=evidence())
        assert green.status_code == 200, green.text


def test_card_does_not_close_with_open_stages_and_brief_shows_the_current_one(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        saved = prepared(client)
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"}).json()
        assert brief["pipeline"]["current"]["id"] == "work"
        assert any("Pipeline" in text for text in brief["harness"]["stopConditions"])
        state = saved["state"]
        node = state["nodes"]["focus"]
        node["evidence"] = evidence()
        node["done"] = {"confirmed": True, "at": "2026-10-07T12:00:00+00:00", "by": "human", "note": ""}
        refused = client.post("/api/desktop-v3/state", headers=HEADERS,
                              json={**SCOPE, "expectedRevision": saved["revision"], "state": state})
        assert refused.status_code == 409 and "pipeline" in refused.text
        for item in node["stages"]["items"]:
            item["status"] = "skipped" if item["kind"] == "critic" else "passed"
        closed = client.post("/api/desktop-v3/state", headers=HEADERS,
                             json={**SCOPE, "expectedRevision": saved["revision"], "state": state})
        assert closed.status_code == 200, closed.text


def critics_round():
    return {"profile": "code", "items": [stage("work", "work"), stage("user", "critic", "user"),
                                         stage("sly", "critic", "sly"), stage("hacker", "critic", "hacker"),
                                         stage("test", "test")]}


def test_critics_of_one_round_report_in_any_order_but_not_before_earlier_stages(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, critics_round())["revision"]
        early = report(client, revision, [{"id": "hacker", "status": "passed", "note": "bez blokátoru"}], agent="astra")
        assert early.status_code == 409 and "předchozími" in early.text
        revision = report(client, revision, [{"id": "work", "status": "passed", "note": "ok"}]).json()["revision"]
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"}).json()["pipeline"]
        assert brief["parallel"] == ["user", "sly", "hacker"]
        last_first = report(client, revision, [{"id": "hacker", "status": "passed", "note": "bez blokátoru"}], agent="astra")
        assert last_first.status_code == 200, last_first.text
        revision = report(client, last_first.json()["revision"], [{"id": "user", "status": "passed", "note": "ok"}],
                          agent="hodny").json()["revision"]
        after_round = report(client, revision, [{"id": "test", "status": "passed", "note": "zelené"}])
        assert after_round.status_code == 409 and "Etapa sly" in after_round.text


def test_failed_critics_of_one_round_share_one_fix_and_each_gets_a_retry(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, critics_round())["revision"]
        revision = report(client, revision, [{"id": "work", "status": "passed", "note": "ok"}]).json()["revision"]
        revision = report(client, revision, [{"id": "hacker", "status": "failed", "note": "únik tokenu"}], agent="astra").json()["revision"]
        revision = report(client, revision, [{"id": "user", "status": "passed", "note": "ok"}], agent="hodny").json()["revision"]
        failed = report(client, revision, [{"id": "sly", "status": "failed", "note": "chybí test mazání"}], agent="vycurany")
        assert failed.status_code == 200, failed.text
        items = items_of(failed)
        assert [item["id"] for item in items[:4]] == ["work", "user", "sly", "hacker"]
        fixes = [item for item in items if item["kind"] == "fix"]
        assert len(fixes) == 1 and items[4]["kind"] == "fix"
        assert "únik tokenu" in fixes[0]["brief"] and "chybí test mazání" in fixes[0]["brief"]
        assert [item.get("retryOf") for item in items[5:7]] == ["hacker", "sly"]
        assert items[7]["id"] == "test" and len(items) == 8
        revision = report(client, failed.json()["revision"], [{"id": fixes[0]["id"], "status": "passed", "note": "opraveno"}]).json()["revision"]
        # Opakování tvoří další kolo: i ta se odevzdávají v libovolném pořadí.
        retried = report(client, revision, [{"id": items[6]["id"], "status": "passed", "note": "drží"}], agent="vycurany")
        assert retried.status_code == 200, retried.text


def test_ideas_from_a_critic_land_on_the_card_without_duplicates_and_brief_shows_open_ones(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, critics_round())["revision"]
        revision = report(client, revision, [{"id": "work", "status": "passed", "note": "ok"}]).json()["revision"]
        ideas = [{"text": "Dlouhý název souboru zalomit.", "source": "critic:sly"}]
        passed = report(client, revision, [{"id": "sly", "status": "passed", "note": "bez blokátoru"}],
                        agent="vycurany", ideas=ideas)
        assert passed.status_code == 200, passed.text
        stored = passed.json()["state"]["nodes"]["focus"]["ideas"]
        assert len(stored) == 1 and stored[0]["stageId"] == "sly" and stored[0]["status"] == "open"
        assert stored[0]["by"] == "vycurany" and stored[0]["source"] == "critic:sly"
        again = report(client, passed.json()["revision"], [], agent="hodny",
                       ideas=[{"text": "  dlouhý NÁZEV souboru zalomit. ", "source": "critic:user"}])
        assert again.status_code == 200 and len(again.json()["state"]["nodes"]["focus"]["ideas"]) == 1
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"}).json()
        assert [item["text"] for item in brief["ideas"]["open"]] == ["Dlouhý název souboru zalomit."]
        assert any("blocker" in rule for rule in brief["pipeline"]["policy"])
        bad = report(client, again.json()["revision"], [], ideas=[{"text": "x", "source": "boss"}])
        assert bad.status_code in (409, 422) and "source" in bad.text


def test_only_a_human_marks_ideas_done(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client, critics_round())["revision"]
        added = report(client, revision, [], ideas=[{"text": "Přidat nápovědu.", "source": "review"}])
        state = added.json()["state"]
        state["nodes"]["focus"]["ideas"][0]["status"] = "done"
        refused = client.post("/api/desktop-v3/state", headers=AGENT,
                              json={**SCOPE, "expectedRevision": added.json()["revision"], "state": state})
        assert refused.status_code == 403, refused.text
        human = client.post("/api/desktop-v3/state", headers=HEADERS,
                            json={**SCOPE, "expectedRevision": added.json()["revision"], "state": state})
        assert human.status_code == 200, human.text
        assert human.json()["state"]["nodes"]["focus"]["ideas"][0]["status"] == "done"


def test_pipeline_write_is_slim_and_full_query_returns_the_whole_state(tmp_path):
    """Karta P3 (etapa test): štíhlá odpověď POST /pipeline zůstane < 10 kB i nad velkým stavem
    a `?full=1` vrátí celý stav shodný s GET /state."""
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client, routed=False)
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        big = {**current["state"], "decisions": [
            {"id": f"d{i}", "text": "x" * 3000, "nodeId": "", "path": "", "pinned": False,
             "createdAt": "2026-10-10T10:00:00+00:00", "by": "human"} for i in range(100)]}
        saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                            json={**SCOPE, "expectedRevision": current["revision"], "state": big})
        assert saved.status_code == 200, saved.text
        revision = saved.json()["revision"]
        slim = route(client, revision, profile="code")
        assert slim.status_code == 200, slim.text
        assert len(slim.content) < 10 * 1024 and slim.json()["revision"] == revision + 1
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert routed_stages(slim) == stored["state"]["nodes"]["focus"]["stages"]
        assert len(stored["state"]["decisions"]) == 100
        added = client.post("/api/desktop-v3/pipeline?full=1", headers=ROUTER, json={
            **SCOPE, "nodeId": "focus", "expectedRevision": revision + 1, "op": "add", "reason": "Chybí UX.",
            "stages": [{"kind": "critic", "lens": "user", "title": "Kritik UX", "brief": "Projdi UI."}]})
        assert added.status_code == 200, added.text
        body = added.json()
        assert body["revision"] == revision + 2 and len(added.content) > 300 * 1024
        assert body["state"] == client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]
