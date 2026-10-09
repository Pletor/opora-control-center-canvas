"""Kola karty: otevřít smí jen člověk, kolo v1 se zamrazí úplné a neměnné, v2 začíná načisto,
node-brief nese zadání kola a předchozí kola, verze plátna kola ukládají."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.agent_results import AgentResults
from backend.editor.agent_memory.card_pipeline import profile_stages
from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.canvas_versions.version_content import read_records
from backend.editor.node.test_removals import (
    HEADERS,
    ORIGIN,
    SCOPE,
    install_graph,
    node,
    state_block,
)

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=work-b5"}
STAMP = "2026-10-09T10:00:00+00:00"
LINK = "https://example.com/pr/1"


def evidence(tests="passed"):
    return {"tests": {"status": tests, "url": "", "note": "pytest zelené"},
            "review": {"status": "passed", "url": LINK, "note": "review"},
            "merge": {"status": "passed", "url": LINK, "note": "merge abc1234"},
            "checksRun": [{"checkId": "unit", "command": "uv run pytest", "exitCode": 0, "logUrl": "", "at": STAMP}]}


def pipeline():
    stages = profile_stages("code", False, by="human")
    for index, stage in enumerate(stages):
        stage.update(status="passed", note=f"Předávka etapy {index}: {stage['title']}.", doneBy=f"agent-{index}", at=STAMP)
    stages[-1].update(note="Hacker: okrajový případ do Podnětů.")
    return {"profile": "code", "items": stages, "routedBy": "router-1", "reason": "kód"}


def closed_node(fragment_id):
    met = state_block("b1", "1")
    met["state"].update(status="met", note="Splněno testem.")
    met["ports"] = [{"id": "p1", "label": "Varianta A", "status": "chosen", "reason": "Rychlejší."},
                    {"id": "p2", "label": "Varianta B", "status": "rejected", "reason": "Drahá."},
                    {"id": "p3", "label": "Bez volby"}]
    criteria = [{"id": "k1", "text": "Testy zelené.", "checked": True}, {"id": "k2", "text": "Dokumentace.", "checked": False}]
    return {"phase": "build", "criteria": criteria, "steps": [], "blocks": [met, state_block("b2", "2")],
            "evidence": evidence(), "stages": pipeline(),
            "ideas": [{"id": "i1", "text": "Otevřený podnět.", "by": "kritik", "source": "critic:sly", "at": STAMP, "status": "open"},
                      {"id": "i2", "text": "Hotový podnět.", "by": "kritik", "source": "review", "at": STAMP, "status": "done"}],
            "fragmentRefs": [{"fragmentId": fragment_id, "revision": 1}],
            "done": {"confirmed": True, "at": STAMP, "by": "human", "note": "Kolo 1 hotové."}}


@pytest.fixture
def env(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("c1", "s1"), node("c2", "s1")],
                               "edges": [{"id": "e1", "source": "c1", "target": "c2", "port": "next"}]})
        vault = BriefVault(app.state.service)
        fragment = vault.apply({**SCOPE, "op": "create", "scopeNodeId": "s1", "title": "3.1 Zadání", "text": "Text v1."},
                               actor="agent", agent="work-1")["fragment"]
        workspace = client.post("/api/desktop-v3/agent-workspace", headers=HEADERS, json={
            **SCOPE, "nodeId": "c1", "expectedRevision": 0, "by": "agent",
            "sections": {"log": "Postup v1.", "failures": "Padal import.", "fixes": "Opraven import.", "handoff": "Hotovo."}})
        assert workspace.status_code == 200, workspace.text
        db = app.state.service.db_for("draft")
        results = AgentResults(app.state.service)
        with db:
            for number in (1, 2):
                results.insert(db, "draft", "draft", {"id": f"r{number}", "nodeId": "c1", "agent": "work-1", "createdAt": STAMP,
                                                      "contextVersion": "cv", "output": {"done": {"proposed": number == 2, "note": "n"},
                                                                                         "touched": [f"src/a{number}.py"]}})
        state = {"settings": [], "rules": [], "tickets": [],
                 "decisions": [{"id": "d1", "text": "Rozhodnutí v1.", "pinned": False, "path": "", "nodeId": "c1",
                                "createdAt": STAMP, "by": "agent"}],
                 "nodes": {"c1": closed_node(fragment["id"])},
                 "edges": {"e1": {"log": "l", "summary": "s", "handoff": "h", "improvements": "", "errors": "Pozor na cache.",
                                  "updatedAt": STAMP, "by": "agent", "agent": "work-1"}}}
        saved = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": 0, "state": state})
        assert saved.status_code == 200, saved.text
        yield {"app": app, "client": client, "vault": vault, "fragment": fragment["id"], "db": db}


def revision(client):
    return client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]


def open_round(client, headers=HEADERS, node_id="c1", reason="Nové zadání 3.1"):
    return client.post("/api/desktop-v3/card-round", headers=headers,
                       json={**SCOPE, "nodeId": node_id, "expectedRevision": revision(client), "reason": reason})


def revise(env, text, expected):
    env["vault"].apply({**SCOPE, "op": "revise", "fragmentId": env["fragment"], "expectedRevision": expected,
                        "text": text, "note": "změna zadání"}, actor="agent", agent="work-1")


def round_rows(db):
    return [tuple(row) for row in db.execute("SELECT node_id,round,revision,record FROM card_rounds ORDER BY round,revision")]


def test_only_a_human_opens_a_round_and_only_on_a_closed_card(env):
    client = env["client"]
    assert open_round(client, AGENT).status_code == 403
    cookies = dict(client.cookies)
    client.cookies.clear()
    assert open_round(client).status_code == 428
    for key, value in cookies.items():
        client.cookies.set(key, value)
    assert open_round(client, node_id="c2").status_code == 409  # karta není uzavřená
    assert round_rows(env["db"]) == []
    opened = open_round(client)
    assert opened.status_code == 200, opened.text
    assert opened.json()["round"] == 2 and opened.json()["frozen"] == 1
    assert open_round(client).status_code == 409  # v2 je otevřená, kolo se neotevírá dvakrát


def test_round_one_is_frozen_complete_and_never_rewritten(env):
    client = env["client"]
    before = copy.deepcopy(client.get("/api/desktop-v3/state", params=SCOPE).json()["state"])
    revise(env, "Text v2.", 1)
    assert open_round(client).status_code == 200
    record = client.get("/api/desktop-v3/card-rounds", params={**SCOPE, "nodeId": "c1"}).json()["rounds"][0]
    card = before["nodes"]["c1"]
    assert record["round"] == 1 and record["schema"] == "opora.card-round/1" and record["phase"] == "build"
    assert record["pipeline"] == card["stages"] and record["blocks"] == card["blocks"]
    assert record["evidence"] == card["evidence"] and record["ideas"] == card["ideas"] and record["done"] == card["done"]
    assert record["brief"]["fragments"] == [{"fragmentId": env["fragment"], "revision": 1, "available": True,
                                             "title": "3.1 Zadání", "kind": "brief", "text": "Text v1."}]
    assert record["nextBrief"]["fragments"][0]["text"] == "Text v2."
    assert [item["kind"] for item in record["criticFindings"]] == ["review", "critic", "critic", "critic"]
    assert record["errors"]["agentFailures"] == "Padal import." and record["errors"]["handoffErrors"][0]["errors"] == "Pozor na cache."
    assert record["commits"]["touched"] == ["src/a1.py", "src/a2.py"] and record["commits"]["merge"]["url"] == LINK
    assert [item["id"] for item in record["agentResults"]] == ["r1", "r2"] and record["agentResults"][1]["doneProposed"]
    assert record["decisions"][0]["text"] == "Rozhodnutí v1." and record["handoffs"]["e1"]["errors"] == "Pozor na cache."
    assert record["agentWorkspace"]["log"] == "Postup v1."
    rows = round_rows(env["db"])
    # Agent ani obecný zápis člověka číslo kola nemění; historie kola zůstane beze změny.
    state = client.get("/api/desktop-v3/state", params=SCOPE).json()
    forged = copy.deepcopy(state["state"])
    forged["nodes"]["c1"]["round"]["number"] = 5
    body = {**SCOPE, "expectedRevision": state["revision"], "state": forged}
    assert client.post("/api/desktop-v3/state", headers=AGENT, json=body).status_code == 403
    assert client.post("/api/desktop-v3/state", headers=HEADERS, json=body).status_code == 409
    del forged["nodes"]["c1"]["round"]
    assert client.post("/api/desktop-v3/state", headers=HEADERS, json=body).status_code == 409
    # Kolo 2 se uzavře a otevře se kolo 3: záznam kola 1 je stále tentýž (porovnání před / po).
    closed = copy.deepcopy(state["state"])
    closed["nodes"]["c1"].update(evidence=evidence(), done={"confirmed": True, "at": STAMP, "by": "human", "note": "v2"})
    assert client.post("/api/desktop-v3/state", headers=HEADERS,
                       json={**SCOPE, "expectedRevision": state["revision"], "state": closed}).status_code == 200
    assert open_round(client, reason="Další vylepšení").status_code == 200
    history = client.get("/api/desktop-v3/card-rounds", params={**SCOPE, "nodeId": "c1"}).json()
    assert history["current"] == 3 and [item["round"] for item in history["rounds"]] == [1, 2]
    assert history["rounds"][0] == record and round_rows(env["db"])[:1] == rows
    assert history["rounds"][1]["agentResults"] == [] and history["rounds"][1]["openReason"] == "Nové zadání 3.1"


def test_round_two_starts_clean(env):
    client = env["client"]
    revise(env, "Text v2.", 1)
    assert open_round(client).status_code == 200
    card = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]["c1"]
    assert "stages" not in card and card["done"]["confirmed"] is False and "Kolo 2" in card["done"]["note"]
    assert card["phase"] == "discover"  # v1 skončila ve fázi build; nové kolo začíná od začátku
    assert [block["state"]["status"] for block in card["blocks"]] == ["open", "open"]
    assert all("note" not in block["state"] for block in card["blocks"])
    assert all(card["evidence"][key]["status"] == "pending" for key in ("tests", "review", "merge"))
    assert card["evidence"]["checksRun"] == []
    assert [idea["id"] for idea in card["ideas"]] == ["i1"]
    assert card["fragmentRefs"] == [{"fragmentId": env["fragment"], "revision": 2}]
    assert card["round"]["number"] == 2 and card["round"]["reason"] == "Nové zadání 3.1" and card["round"]["by"] == "human"
    space = client.get("/api/desktop-v3/agent-workspace", params={**SCOPE, "nodeId": "c1"}).json()["workspace"]
    assert space["log"] == "" and space["failures"] == ""
    frontier = client.get("/api/desktop-v3/frontier", params={**SCOPE, "nodeId": "s1"}).json()
    assert "c1" in [item["id"] for item in frontier["needsRouting"]]


def test_round_two_does_not_carry_port_choices_or_checked_criteria(env):
    """Nové zadání = nové postupy: v2 rozhoduje porty a kritéria znovu, v1 je drží v historii jako kontext."""
    client = env["client"]
    assert open_round(client).status_code == 200
    state = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]
    card = state["nodes"]["c1"]
    assert card["blocks"][0]["ports"] == [{"id": "p1", "label": "Varianta A"}, {"id": "p2", "label": "Varianta B"},
                                          {"id": "p3", "label": "Bez volby"}]
    assert [(item["text"], item["checked"]) for item in card["criteria"]] == [("Testy zelené.", False), ("Dokumentace.", False)]
    assert [item["id"] for item in state["decisions"]] == ["d1"]  # rozhodnutí karty se nemažou
    record = client.get("/api/desktop-v3/card-rounds", params={**SCOPE, "nodeId": "c1"}).json()["rounds"][0]
    assert record["blocks"][0]["ports"][0] == {"id": "p1", "label": "Varianta A", "status": "chosen", "reason": "Rychlejší."}
    assert [item["checked"] for item in record["criteria"]] == [True, False]
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()
    previous = brief["previousRounds"][0]
    assert previous["blocks"][0]["portDecisions"] == [{"label": "Varianta A", "status": "chosen", "reason": "Rychlejší."},
                                                      {"label": "Varianta B", "status": "rejected", "reason": "Drahá."}]
    assert previous["criteria"] == [{"text": "Testy zelené.", "checked": True}, {"text": "Dokumentace.", "checked": False}]
    assert previous["decided"] == ["rozhodnutí v1: port „Varianta A“ bloku 1 = chosen (Rychlejší.)",
                                   "rozhodnutí v1: port „Varianta B“ bloku 1 = rejected (Drahá.)",
                                   "rozhodnutí v1: kritérium splněno: Testy zelené.", "rozhodnutí v1: Rozhodnutí v1."]
    assert [(item["id"], item.get("fromRound")) for item in brief["context"]["decisions"]] == [("d1", 1)]
    assert [item["checked"] for item in brief["definitionOfDone"]["criteria"]] == [False, False]
    assert "not carried over" in brief["rounds"]["policy"]


def test_new_decision_in_round_two_is_not_marked_as_previous(env):
    client = env["client"]
    assert open_round(client).status_code == 200
    stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
    state = copy.deepcopy(stored["state"])
    state["decisions"].append({"id": "d2", "text": "Rozhodnutí v2.", "pinned": False, "path": "", "nodeId": "c1",
                               "createdAt": STAMP, "by": "human"})
    assert client.post("/api/desktop-v3/state", headers=HEADERS,
                       json={**SCOPE, "expectedRevision": stored["revision"], "state": state}).status_code == 200
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()
    marks = {item["id"]: item.get("fromRound") for item in brief["context"]["decisions"]}
    assert marks.get("d1") == 1 and marks.get("d2") is None


def test_node_brief_carries_previous_rounds_and_the_frozen_round_brief(env):
    client = env["client"]
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()
    assert brief["rounds"]["current"] == 1 and brief["previousRounds"] == []
    assert brief["rounds"]["brief"]["fragments"][0]["text"] == "Text v1."
    revise(env, "Text v2.", 1)
    assert open_round(client).status_code == 200
    revise(env, "Text v3 po otevření kola.", 2)
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()
    rounds, previous = brief["rounds"], brief["previousRounds"]
    assert rounds["current"] == 2 and rounds["history"] == [1] and rounds["reason"] == "Nové zadání 3.1"
    assert rounds["brief"]["fragments"][0]["text"] == "Text v2."  # kopie kola se změnou schránky nemění
    assert brief["fragments"]["items"][0]["text"] == "Text v3 po otevření kola." and brief["fragments"]["changed"] == 1
    assert previous[0]["round"] == 1 and previous[0]["closeNote"] == "Kolo 1 hotové."
    assert previous[0]["pipeline"]["stages"][0]["note"].startswith("Předávka etapy 0")
    assert previous[0]["errors"]["agentFailures"] == "Padal import." and previous[0]["commits"]["touched"]
    assert previous[0]["criticFindings"] and previous[0]["ideas"] == {"open": ["Otevřený podnět."], "done": ["Hotový podnět."]}
    assert previous[0]["detail"].endswith("nodeId=c1&round=1")
    assert "previousRounds" in brief["trust"]["dataFromAgents"]
    assert "rounds.brief.fragments" in brief["trust"]["dataFromAgents"]  # text schránky píší i agenti: data, ne pokyn
    detail = client.get("/api/desktop-v3/card-rounds", params={**SCOPE, "nodeId": "c1", "round": 1}).json()
    assert [item["round"] for item in detail["rounds"]] == [1]
    assert client.get("/api/desktop-v3/card-rounds", params={**SCOPE, "nodeId": "c1", "round": 2}).status_code == 409


def test_canvas_versions_carry_rounds_and_restore_appends_instead_of_rewriting(env):
    client, db = env["client"], env["db"]
    view = client.get("/api/view", params=SCOPE).json()
    # v1 ve fázi build se všemi kritérii splněnými (jinak by obnova z v2 = discover narazila na bránu fáze)
    stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
    state = copy.deepcopy(stored["state"])
    state["nodes"]["c1"]["criteria"][1]["checked"] = True
    assert client.post("/api/desktop-v3/state", headers=HEADERS,
                       json={**SCOPE, "expectedRevision": stored["revision"], "state": state}).status_code == 200
    view = client.get("/api/view", params=SCOPE).json()
    version = client.post("/api/canvas-versions", headers=HEADERS, json={**SCOPE, "digest": view["digest"], "author": "test"})
    assert version.status_code == 200, version.text
    assert open_round(client).status_code == 200
    rounds = read_records(db, "draft", "draft")["cardRounds"]
    assert [row["key"] for row in rounds] == [["c1", 1]] and rounds[0]["data"]["record"]["round"] == 1
    tokens = client.get("/api/canvas-versions", params=SCOPE).json()
    restored = client.post("/api/canvas-versions/restore", headers=HEADERS, json={
        **SCOPE, "versionId": version.json()["version"]["id"], "digest": client.get("/api/view", params=SCOPE).json()["digest"],
        "author": "test", "expectedToken": tokens["currentToken"]})
    assert restored.status_code == 200, restored.text
    card = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]["c1"]
    assert "round" not in card and card["done"]["confirmed"] is True
    rows = round_rows(db)
    assert [row[:3] for row in rows] == [("c1", 1, 1), ("c1", 1, 2)] and json.loads(rows[1][3]) == {}
    assert json.loads(rows[0][3])["round"] == 1  # původní záznam zůstal
    assert open_round(client).status_code == 200  # kolo lze po obnově znovu otevřít, přibude revize
    assert [row[:3] for row in round_rows(db)][-1] == ("c1", 1, 3)


def test_previous_rounds_keep_each_stage_note_once_and_short(env):
    """Poznámka etapy je v previousRounds jen jednou (pipeline) a zkrácená; nálezy a chyby na ni odkazují id."""
    client = env["client"]
    critic = {}
    for confirmed in (False, True):  # uzavřená karta má pipeline jen ke čtení: otevřít, upravit, uzavřít
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        state = copy.deepcopy(stored["state"])
        card = state["nodes"]["c1"]
        card["done"]["confirmed"] = confirmed
        if not confirmed:
            critic = card["stages"]["items"][-1]
            critic.update(note="Hacker: " + "dlouhý nález " * 100)
        saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                            json={**SCOPE, "expectedRevision": stored["revision"], "state": state})
        assert saved.status_code == 200, saved.text
    assert open_round(client).status_code == 200
    previous = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()["previousRounds"][0]
    text = json.dumps(previous, ensure_ascii=False)
    assert text.count("Hacker: dlouhý nález") == 1
    note = previous["pipeline"]["stages"][-1]["note"]
    assert len(note) <= 280 and note.endswith("…") and previous["pipeline"]["stages"][-1]["id"] == critic["id"]
    assert critic["id"] in [item["stageId"] for item in previous["criticFindings"]]
    assert previous["errors"]["failedStageIds"] == [] and "note" not in previous["criticFindings"][0]
    assert previous["detail"].endswith("round=1") and "detail" in previous["notes"]
    full = client.get(previous["detail"]).json()["rounds"][0]
    assert full["pipeline"]["items"][-1]["note"] == critic["note"]  # plný text zůstává v detailu
