"""Živá karta K1: tvar odpovědi nad skutečnými záznamy, odvození stavu, sekce null bez dat, vrstvy node-briefu."""
import json

import pytest

from backend.agi_pletor.linie import evaluate
from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.api.editor.test_opora_execution_routes import BASE, payload
from backend.api.editor.test_opora_execution_routes import (
    client as client,  # noqa: PLC0414 - shared pytest fixture
)
from backend.brain_opora.determinism import triggers
from backend.canvas import live_card
from backend.canvas.opora_card_done import REQUIREMENTS
from backend.canvas.test_canvas_plan import HEADERS, SCOPE

LIVE = "/api/oporahub/live-card"
KEYS = {"nodeId", "title", "kind", "crumbs", "state", "progress", "pills", "truths", "edges", "flow", "output", "linie",
        "runs", "cost", "recent", "decisions", "children", "next", "heart", "agent"}


@pytest.mark.parametrize("status,extra,expected", [
    ("closed", {}, "leaf"), ("ready", {"merged": True}, "leaf"), ("ready", {"dry": True}, "dry"),
    ("running", {}, "bud"), ("reported", {}, "bud"), ("ready", {"held": True}, "bud"),
    ("needs-acceptance", {}, "prop"), ("needs-plan", {}, "seed"), ("needs-steps", {}, "seed"),
    ("blocked", {}, "seed"), (None, {}, "seed")])
def test_state_table(status, extra, expected):
    assert live_card.state_of({"kind": "node"}, {"status": status} if status else None, **extra) == expected


def test_goal_card_and_leaf_wins_over_dry():
    assert live_card.state_of({"goal_mode": "until_checks_pass"}, {"status": "ready"}) == "goal"
    assert live_card.state_of({}, {"status": "closed"}, dry=True) == "leaf"


def test_every_trigger_has_a_sentence():
    assert set(live_card.TRIGGER_WHEN) == set(triggers.CARD_KINDS)


def read(client, headers=AGENT, **params):
    return client.get(LIVE, params={**SCOPE, "nodeId": "n0", **params}, headers=headers)


def test_running_card_from_real_records(client):
    execution = client.post(BASE + "/claim", headers=AGENT, json=payload(client)).json()
    response = read(client)
    assert response.status_code == 200, response.text
    card = response.json()
    assert set(card) == KEYS
    assert card["nodeId"] == "n0" and card["state"] == "bud"
    assert card["runs"][0]["executionId"] == execution["executionId"] and card["runs"][0]["costUsd"] is None
    assert card["cost"] == {"totalUsd": None, "budgetUsd": None}
    assert card["truths"]["mirror"] == {"available": False, "milestone": "F1"}
    assert card["truths"]["future"] == {"available": False}  # bez otevřené práce Linie
    assert card["flow"] is None and card["output"] is None and card["linie"] is None  # bez prvku, skenu a Linie
    assert card["agent"]["address"] == "opora://card/n0"
    assert card["agent"]["lease"]["holder"] == "agent:builder"
    assert {item["layer"]: item["exists"] for item in card["agent"]["reads"]}["folie"] is True
    assert any(item["kind"] == "lease.claimed" for item in card["recent"])
    assert execution["token"] not in response.text


def test_read_writes_nothing_and_needs_identity(client):
    service = client.app.state.service
    before = service.db_for("draft").total_changes
    assert read(client).status_code == 200
    assert service.db_for("draft").total_changes == before
    client.cookies.clear()
    assert read(client, headers=HEADERS).status_code == 428


@pytest.mark.parametrize("node", ["", "../n0", "missing"])
def test_invalid_or_missing_node_is_conflict(client, node):
    assert read(client, nodeId=node).status_code == 409


def test_flow_output_linie_and_cost_from_sources(client):
    """Sekce z plátna 2, Linie a ceny se plní jen z dodaných zdrojů (tvar jako `library.project_flow`, sken, trace)."""
    execution = client.post(BASE + "/claim", headers=AGENT, json=payload(client)).json()
    facts = live_card.gather(client.app.state.service, SCOPE["project"], SCOPE["workspace"], "n0")
    node = next(item for item in facts["graph"]["nodes"] if item["id"] == "n0")
    node["element"], node["card"] = {"kind": "form"}, {"section": "hero"}
    page = {"id": "p1", "name": "Domů", "site": {"kind": "page", "sections": [{"id": "hero", "name": "Úvod"}]}}
    flow = {"nodes": [{"id": "vstup-1", "notes": "E-mail"}, {"id": "krok-1", "params": {"title": "Odeslat"}},
                      {"id": "data-1", "notes": "CRM"}, {"id": "ruční", "notes": "nezařadí se"}]}
    scan = {"scanId": "a" * 32, "proposal": {"captures": {"page": "page.png", "sections": {"hero": "hero.png", "x": "x.png"}}}}
    work = {"mark": "OP-ABCDEF", "branch": "feat/x", "headSha": "b" * 40}
    linie = {"ticket": {"ticketId": "tk_1", "work": work}, "shown": {"axes": evaluate.axes(work)},
             "trace": {"commits": [{"sha7": "bbbbbbb", "title": "feat: x"}], "gaps": [{"text": "Commit bez běhu."}],
                       "pr": None, "preview": {"url": "http://127.0.0.1:8790", "state": "running"}}}
    costs = {"executions": {execution["executionId"]: 0.42}, "nodes": {"n0": 0.42}}
    card = live_card.compose({**facts, "page": page, "flow": flow, "scan": scan, "linie": linie, "costs": costs})
    assert card["flow"]["inputs"] == ["E-mail"] and card["flow"]["steps"] == ["Odeslat"] and card["flow"]["dataTo"] == ["CRM"]
    assert card["flow"]["pageId"] == "p1" and card["flow"]["source"].startswith("/api/library/project-flows?")
    assert [item["label"] for item in card["output"]["captures"]] == ["Úvod"]  # prvek dostane jen výřez svého boxu
    assert card["output"]["captures"][0]["url"].startswith(f"/api/page-plan/scan/{'a' * 32}/capture/hero.png?")
    assert card["output"]["preview"] == {"url": "http://127.0.0.1:8790", "status": "running"}
    assert card["linie"]["mark"] == "OP-ABCDEF" and card["linie"]["commits"] == [{"sha7": "bbbbbbb", "title": "feat: x"}]
    assert {axis["name"] for axis in card["linie"]["axes"]} == {"work", "checks", "acceptance", "integration", "deploy"}
    assert card["agent"]["address"] == "opora://card/OP-ABCDEF"
    assert card["runs"][0]["costUsd"] == 0.42 and card["cost"]["totalUsd"] == 0.42
    blocked = live_card.compose({**facts, "linie": {**linie, "ticket": {"ticketId": "tk_1", "work": {**work, "blocked": {"reason": "x"}}}}})
    assert blocked["state"] == "dry"
    print(json.dumps(card, ensure_ascii=False, indent=1))


def test_node_brief_layers(client):
    params = {**SCOPE, "nodeId": "n0"}
    full = client.get("/api/desktop-v3/node-brief", params=params).json()
    assert "schema" in full and "truths" not in full  # bez layer beze změny
    souhrn = client.get("/api/desktop-v3/node-brief", params={**params, "layer": "souhrn"})
    assert souhrn.status_code == 200, souhrn.text
    assert set(souhrn.json()) == {"id", "title", "state", "progress", "next", "blocked", "truths"}
    assert souhrn.json()["truths"]["mirror"] is None
    tvar = client.get("/api/desktop-v3/node-brief", params={**params, "layer": "tvar"}).json()
    assert set(tvar) == {"criteria", "edges", "children"}
    assert client.get("/api/desktop-v3/node-brief", params={**params, "layer": "proces"}).status_code == 422


def test_reality_speaks_czech_and_keeps_the_key():
    assert set(live_card.REQUIREMENT_TEXT) == set(REQUIREMENTS)
    reality = live_card._reality({"missing": ["merged"]}, "q", None)
    assert reality["items"][3] == {"key": "merged", "text": "Sloučeno do main", "status": "miss"}
    assert all(item["text"] != item["key"] for item in reality["items"])


def test_domain_of_site_lists_its_pages_scans_and_progress(client, monkeypatch):
    """Uzel = doména webu (plátno 2, `site.kind application`): stránky pod ní (i vnořené) jako potomci s postupem
    z prvků logiky a celostránkové snímky posledního skenu jako výstup; stránka jiné domény se nepočítá."""
    service = client.app.state.service
    facts = live_card.gather(service, SCOPE["project"], SCOPE["workspace"], "n0")
    graph = facts["graph"]
    graph["nodes"] += [
        {"id": "dom", "kind": "sector", "name": "app.example.cz", "parentId": None, "site": {"kind": "application"}},
        {"id": "home", "kind": "sector", "name": "Domů", "parentId": "dom", "site": {"kind": "page", "path": "/"}},
        {"id": "deep", "kind": "sector", "name": "Ceník", "parentId": "home", "site": {"kind": "page", "path": "/cenik"}},
        {"id": "el1", "kind": "node", "name": "Formulář", "parentId": "home", "element": {"kind": "form"}},
        {"id": "el2", "kind": "node", "name": "Tlačítko", "parentId": "home", "element": {"kind": "button"}},
        {"id": "other", "kind": "sector", "name": "Jiná doména", "parentId": None, "site": {"kind": "application"}},
        {"id": "foreign", "kind": "sector", "name": "Cizí", "parentId": "other", "site": {"kind": "page", "path": "/"}}]
    by_id = {item["id"]: item for item in graph["nodes"]}
    scans = {"home": {"scanId": "c" * 32, "proposal": {"captures": {"page": "page.png", "sections": {"hero": "hero.png"}}}}}
    monkeypatch.setattr(live_card.page_plan_scan, "latest", lambda s, p, w, page, adopted=False: (
        scans[page] if page in scans else (_ for _ in ()).throw(live_card.GateError(404, "scan_not_found", "x", "y"))))
    monkeypatch.setattr(live_card, "confirmed_nodes", lambda db, p, w, nodes: {"el1"} & set(nodes))
    domain = live_card._domain(service, SCOPE["project"], SCOPE["workspace"], by_id["dom"], graph)
    assert [entry["page"]["id"] for entry in domain] == ["home", "deep"]
    assert live_card._domain(service, SCOPE["project"], SCOPE["workspace"], by_id["n0"], graph) is None
    card = live_card.compose({**facts, "nodeId": "dom", "domain": domain, "page": None, "flow": None, "scan": None})
    assert card["flow"] is None
    assert card["output"]["captures"] == [
        {"label": "Domů", "url": f"/api/page-plan/scan/{'c' * 32}/capture/page.png?project=draft&workspace=draft"}]
    assert card["output"]["source"].endswith("&pageId={pageId}")
    children = {item["nodeId"]: item for item in card["children"]}
    assert children["home"]["progress"] == 50 and children["home"]["state"] == "bud"
    assert children["deep"]["progress"] is None and children["deep"]["state"] == "seed"
    assert "foreign" not in children


def test_mirror_from_plan_reality():
    """Zrcadlo kódu: bez commitů i očekávání do F1, jinak položky se stavem shoda / chybí / navíc / přibylo."""
    assert live_card._mirror(None, "q") == {"available": False, "milestone": "F1"}
    empty = {"matched": [], "missing": [], "extra": [], "symbols": [], "evidence": None}
    assert live_card._mirror(empty, "q") == {"available": False, "milestone": "F1"}
    item = {"kind": "file", "name": "a.py", "path": "a.py", "line": None, "source": "abc1234", "change": "added"}
    found = {**empty, "matched": [item], "extra": [item | {"path": "b.py", "name": "b.py"}],
             "symbols": [{"kind": "route", "name": "GET /x", "path": "a.py", "line": 3, "source": "abc1234",
                          "note": "# OP-ABC123.1: proč"}], "evidence": {"commit": "abc", "at": "t"}}
    mirror = live_card._mirror(found, "q")
    assert mirror["available"] is True and mirror["source"] == "/api/oporahub/plan-reality?q"
    assert [(i["name"], i["status"], i["text"]) for i in mirror["items"]] == [
        ("a.py", "ok", "added"), ("b.py", "bad", "added"), ("GET /x", "ok", "# OP-ABC123.1: proč")]
    assert mirror["counts"] == {"matched": 1, "missing": 0, "extra": 1} and mirror["evidence"]["commit"] == "abc"


def test_monitor_shows_worker_heart_and_watchdog_in_recent_and_heart_has_severity(client):
    """F2: `tool.use` z Kanceláře s cílem, zásah srdce `worker.message` (patička: severity) a signál hlídače
    `card.signal` jsou v deníku karty s čitelným textem a aktérem; rub uvádí `ticket.direct` mezi zápisy srdce."""
    from backend.canvas.opora_events import emit_event

    office = {"schema": "opora.process-event/1", "id": "office:f2:1", "seq": 1, "at": "2026-11-11T10:00:00.000Z",
              "source": "office", "kind": "tool.use", "phase": "work", "state": "progress", "title": "Ada: Edit",
              "actor": {"kind": "worker", "id": "w-1", "name": "Ada"},
              "refs": {**SCOPE, "cardId": "n0", "workerId": "w-1"},
              "tool": {"name": "Edit", "action": "edit", "target": "frontend/app.tsx"}}
    assert client.post("/api/oporahub/process-events", json={"events": [office]},
                       headers={**AGENT, "content-type": "application/json"}).json()["accepted"] == 1
    service = client.app.state.service
    emit_event(service, project_id="draft", workspace_id="draft", kind="worker.message", node_id="n0",
               actor={"kind": "agent", "name": "heart"},
               data={"ticketId": "tk_1", "feedbackId": "tf_1", "severity": "course", "text": "Drž se souborů karty."})
    emit_event(service, project_id="draft", workspace_id="draft", kind="card.signal", node_id="n0",
               actor={"kind": "system", "name": "hlídač"},
               data={"signal": "card.drift", "detail": "editace mimo soubory karty: frontend/app.tsx"})
    card = read(client).json()
    lines = {(item["kind"], item["actor"], item["text"]) for item in card["recent"]}
    assert ("tool.use", "Ada", "Ada: Edit · frontend/app.tsx") in lines
    assert ("worker.message", "heart", "Srdce dělníkovi (course): Drž se souborů karty.") in lines
    assert ("card.signal", "hlídač", "card.drift: editace mimo soubory karty: frontend/app.tsx") in lines
    assert card["heart"]["severity"] == "course" and card["heart"]["text"] == "Drž se souborů karty."
    assert any(item["what"].startswith("ticket.direct") for item in card["agent"]["writes"])


def test_heart_footer_survives_the_event_window_from_ticket_feedback(client):
    """Zásah srdce je trvale ve zpětné vazbě ticketu karty; patička ho najde i bez události v okně deníku."""
    from backend.brain_opora.determinism.test_ticket import ISSUE, heart, send, worker

    service = client.app.state.service
    brain, office = heart(service), worker(service)
    tid = send(service, brain, "ticket.issue", {**ISSUE, "cardId": "n0"})["ticket"]["ticketId"]
    send(service, office, "ticket.claim", {"ticketId": tid})
    send(service, brain, "ticket.direct", {"ticketId": tid, "severity": "stop", "text": "Zastav běh."})
    db = service.db_for("draft")
    with db:
        db.execute("DELETE FROM opora_events WHERE kind='worker.message'")  # vypadla z okna 200 událostí karty
    card = read(client).json()
    assert {key: card["heart"][key] for key in ("severity", "text")} == {"severity": "stop", "text": "Zastav běh."}


def test_future_section_only_with_open_work():
    """F4: budoucnost je vidět jen s otevřenou prací Linie karty; tvar nese verdikt a práci z `plan_future`."""
    assert live_card._future(None) == {"available": False}
    work = {"mark": "OP-A", "branch": "feat/a", "target": "main", "changed": ["a.py"], "conflicts": ["a.py"],
            "impacts": [], "overlaps": []}
    assert live_card._future({"verdict": "blocked", "works": [work]}) == {
        "available": True, "verdict": "blocked", "works": [work]}
