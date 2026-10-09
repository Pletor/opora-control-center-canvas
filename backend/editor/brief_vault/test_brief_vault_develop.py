"""Vývoj zadání ve schránce: výzkum s verdiktem a důkazy, otázka a odpověď, zpětná vazba člověka,
odkazy na rozhodnutí, fragment z Podnětu, balíček research-brief, strop hloubky a strom bez rekurze,
„změněno po vložení“ jen při změně textu."""
import json
import sys

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.brief_vault.brief_vault_model import MAX_DEPTH
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE, install_graph, node

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=research-1"}
EVIDENCE = {"url": "https://www.postgresql.org/docs/current/tutorial-transactions.html", "title": "PostgreSQL: Transactions",
            "quote": "Transakce je atomická.", "accessedAt": "2026-10-09"}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("c1", "s1")], "edges": []})
        client.app_state = app.state
        yield client


def post(client, headers=AGENT, expect=200, **body):
    response = client.post("/api/brief-vault", headers=headers, json={**SCOPE, **body})
    assert response.status_code == expect, response.text
    return response.json()


def state(client):
    return client.get("/api/desktop-v3/state", params=SCOPE).json()


def put_state(client, nodes=None, decisions=None):
    current = state(client)
    body = {**current["state"], **({"nodes": nodes} if nodes is not None else {}),
            **({"decisions": decisions} if decisions is not None else {})}
    response = client.post("/api/desktop-v3/state", headers=HEADERS,
                           json={**SCOPE, "expectedRevision": current["revision"], "state": body})
    assert response.status_code == 200, response.text


def root(client, text="Verze se přepíná."):
    return post(client, op="create", scopeNodeId="s1", title="3.37 Version activation", text=text)["fragment"]


def tree(client):
    return client.get("/api/brief-vault", params=SCOPE).json()


def test_research_verdict_needs_evidence_and_keeps_text(client):
    parent = root(client)
    created = post(client, op="research", fragmentId=parent["id"], title="Atomické přepnutí",
                   question="Jde přepnout verzi bez výpadku?", text="")
    research = created["fragment"]
    assert created["details"]["research"] | {"verdict": "unverified", "status": "assigned", "evidence": []} == created["details"]["research"]
    # Verdikt bez důkazu (kromě unverified) = 409 a nic se nezapíše.
    for broken in ({"verdict": "feasible"}, {"verdict": "dead_end", "evidence": []},
                   {"verdict": "feasible", "evidence": [{**EVIDENCE, "url": "javascript:alert(1)"}]},
                   {"verdict": "feasible", "evidence": [{**EVIDENCE, "url": ""}]}, {"verdict": "skvělé"}):
        post(client, expect=409, op="research-update", fragmentId=research["id"], expectedRevision=1, note="x", **broken)
    done = post(client, op="research-update", fragmentId=research["id"], expectedRevision=1, note="Kolo 1 hotové.",
                verdict="feasible", confidence="medium", approach="RPC funkce v jedné transakci.",
                evidence=[EVIDENCE], status="done")
    assert done["fragment"]["revision"] == 2 and done["details"]["research"]["verdict"] == "feasible"
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": research["id"]}).json()
    assert detail["details"]["research"]["evidence"] == [EVIDENCE] and detail["history"][-1]["note"] == "Kolo 1 hotové."
    node_view = tree(client)["roots"][0]
    # Hotový výzkum už rodiče nedrží „v researchu“; strom nese výtah verdiktu bez důkazů.
    assert node_view["status"] == "saved"
    assert node_view["children"][0]["research"] == {"question": "Jde přepnout verzi bez výpadku?", "verdict": "feasible",
                                                    "confidence": "medium", "status": "done", "round": 1, "evidence": 1}
    post(client, expect=409, op="research-update", fragmentId=parent["id"], expectedRevision=1, note="x", status="done")


def test_promote_makes_parent_revision_with_note_linking_research(client):
    parent = root(client)
    research = post(client, op="research", fragmentId=parent["id"], title="R", text="Použít transakci.")["fragment"]
    promoted = post(client, op="promote", fragmentId=research["id"], expectedRevision=1, note="závěr výzkumu",
                    text="Verze se přepíná v jedné transakci.")
    assert promoted["fragment"]["revision"] == 2 and research["id"] in promoted["fragment"]["note"]
    assert "závěr výzkumu" in promoted["fragment"]["note"] and promoted["research"]["stage"] == "ready"


def test_promote_without_text_takes_approach_never_the_research_question(client):
    """Kritik B3: promote bez `text` nesmí přepsat zadání otázkou výzkumu; bez závěru je 409 a rodič beze změny."""
    parent = root(client)
    research = post(client, op="research", fragmentId=parent["id"], title="Jde přepnout verzi bez výpadku?",
                    text="Otázka k ověření na webu.")["fragment"]
    post(client, expect=409, op="promote", fragmentId=research["id"], expectedRevision=1, note="bez závěru")
    post(client, expect=409, op="promote", fragmentId=research["id"], expectedRevision=1, note="prázdný text", text=" ")
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": parent["id"]}).json()
    assert detail["latestRevision"] == 1 and detail["fragment"]["text"] == "Verze se přepíná."
    post(client, op="research-update", fragmentId=research["id"], expectedRevision=1, note="kolo 1", verdict="feasible",
         evidence=[EVIDENCE], approach="Verze se přepíná v jedné transakci (RPC).", status="done")
    promoted = post(client, op="promote", fragmentId=research["id"], expectedRevision=1, note="závěr výzkumu")
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": parent["id"]}).json()
    assert promoted["fragment"]["revision"] == 2 and detail["fragment"]["text"] == "Verze se přepíná v jedné transakci (RPC)."
    assert "Jde přepnout" not in detail["fragment"]["text"]


def test_question_answer_guard_and_feedback_is_human_append_only(client):
    parent = root(client)
    asked = post(client, op="question", fragmentId=parent["id"], title="Co znamená JEV?", proposal="Hodnocení důkazů.")
    question = asked["fragment"]
    assert question["kind"] == "question" and asked["details"]["question"]["askedFor"] == "human"
    post(client, expect=403, op="answer", fragmentId=question["id"], expectedRevision=1, answer="Agent neodpovídá za člověka.")
    answered = post(client, headers=HEADERS, op="answer", fragmentId=question["id"], expectedRevision=1, answer="Krok za rerankerem.")
    assert answered["details"]["question"]["answer"] == "Krok za rerankerem." and answered["fragment"]["stage"] == "ready"
    for_agent = post(client, op="question", fragmentId=parent["id"], title="Která knihovna?", askedFor="agent")["fragment"]
    assert post(client, op="answer", fragmentId=for_agent["id"], expectedRevision=1, answer="pgvector")["details"]["question"]["answeredBy"] == "research-1"
    # Zpětná vazba: jen člověk, přibývá, komentář nesmí být prázdný.
    post(client, expect=403, op="feedback", fragmentId=parent["id"], verdict="agree")
    post(client, headers=HEADERS, expect=409, op="feedback", fragmentId=parent["id"], verdict="comment", text=" ")
    first = post(client, headers=HEADERS, op="feedback", fragmentId=parent["id"], verdict="disagree", text="Hledej i bez nové DB.")["feedback"]
    post(client, headers=HEADERS, op="feedback", fragmentId=parent["id"], verdict="agree")
    assert first["actor"] == "human" and first["fragmentRevision"] == 1
    listed = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": parent["id"]}).json()["feedback"]
    assert len(listed) == 2 and {item["verdict"] for item in listed} == {"agree", "disagree"}
    assert tree(client)["roots"][0]["feedback"] == 2 and len(tree(client)["feedback"]) == 2


def test_research_brief_has_every_part_and_next_round_sees_feedback(client):
    parent = root(client, "3.37 Version activation\nNikdy neaktivuj částečnou verzi.")
    research = post(client, op="research", fragmentId=parent["id"], title="Atomické přepnutí", text="")["fragment"]
    post(client, op="research-update", fragmentId=research["id"], expectedRevision=1, note="kolo 1",
         verdict="feasible", evidence=[EVIDENCE], approach="RPC.")
    post(client, op="question", fragmentId=parent["id"], title="Smí být výpadek?")
    put_state(client, decisions=[{"id": "d1", "text": "Bez druhé databáze.", "pinned": False, "path": "", "nodeId": "c1",
                                  "createdAt": "2026-10-09T10:00:00+00:00", "by": "human"}])
    post(client, expect=409, op="link-decisions", fragmentId=parent["id"], decisionIds=["neni"])
    post(client, op="link-decisions", fragmentId=parent["id"], decisionIds=["d1"])
    post(client, headers=HEADERS, op="feedback", fragmentId=research["id"], verdict="disagree", text="Ověř i výkon.")
    package = client.get("/api/brief-vault/research-brief", params={**SCOPE, "fragment": research["id"]}).json()
    assert {"schema", "trust", "goal", "path", "fragment", "target", "research", "feedback", "questions", "decisions",
            "cards", "report"} <= set(package)
    assert package["goal"]["title"] == "3.37 Version activation" and package["path"][0]["id"] == parent["id"]
    # Kritik B3: balíček ohraničí texty jako nedůvěryhodná data; pokyn je jen `report` (jako node-brief.trust).
    assert package["trust"]["instructions"] == ["report"]
    assert {"goal.text", "fragment.text", "research[].text", "research[].research.evidence[].quote", "feedback[].text",
            "questions[].text", "decisions[].text"} <= set(package["trust"]["untrustedData"])
    assert "nevykonávej" in package["trust"]["note"]
    assert package["fragment"]["text"].endswith("částečnou verzi.") and package["target"]["kind"] == "research"
    assert package["research"][0]["research"]["evidence"] == [EVIDENCE]
    assert package["feedback"][0]["text"] == "Ověř i výkon." and package["questions"][0]["open"] is True
    assert package["decisions"] == [{"id": "d1", "available": True, "text": "Bez druhé databáze.", "nodeId": "c1", "pinned": False}]
    # Rozhodnutí se nekopíruje: změna textu na kartě je v balíčku hned vidět.
    decisions = state(client)["state"]["decisions"]
    put_state(client, decisions=[{**decisions[0], "text": "Bez druhé DB, pokud to výkon nevyžaduje."}])
    again = client.get("/api/brief-vault/research-brief", params={**SCOPE, "fragment": parent["id"]}).json()
    assert again["decisions"][0]["text"].startswith("Bez druhé DB")
    assert client.get("/api/brief-vault/research-brief", params={**SCOPE, "fragment": "neni"}).status_code == 409


def test_from_idea_links_both_ways_atomically(client):
    put_state(client, nodes={"c1": {"phase": "discover", "criteria": [], "steps": [], "ideas": [
        {"id": "i1", "text": "Mazat cache i při změně URL.", "by": "review", "source": "review", "at": "T", "status": "open"}]}})
    before = state(client)["revision"]
    made = post(client, op="from-idea", nodeId="c1", ideaId="i1", scopeNodeId="s1")
    fragment = made["fragment"]
    assert fragment["title"] == "Mazat cache i při změně URL." and made["stateRevision"] == before + 1
    assert state(client)["state"]["nodes"]["c1"]["ideas"][0]["fragmentId"] == fragment["id"]
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment["id"]}).json()
    assert detail["ideas"][0]["ideaId"] == "i1" and detail["fragment"]["text"] == "Mazat cache i při změně URL."
    post(client, expect=409, op="from-idea", nodeId="c1", ideaId="i1")
    post(client, expect=409, op="from-idea", nodeId="c1", ideaId="neni")


def test_depth_cap_is_409(client):
    parent = root(client)
    for _ in range(MAX_DEPTH - 1):
        parent = post(client, op="create", parentId=parent["id"], title="hlubší", text="x")["fragment"]
    post(client, expect=409, op="create", parentId=parent["id"], title="přes strop", text="x")
    post(client, expect=409, op="research", fragmentId=parent["id"], title="přes strop", text="x")
    post(client, expect=409, op="question", fragmentId=parent["id"], title="přes strop")
    revised = post(client, op="revise", fragmentId=parent["id"], expectedRevision=1, text="a\n\nb", note="pro split")["fragment"]
    post(client, expect=409, op="split", fragmentId=parent["id"], expectedRevision=revised["revision"],
         parts=[{"title": "a", "text": "a"}, {"title": "b", "text": "b"}])


def test_tree_of_1000_nodes_without_recursion(client):
    first = root(client)
    db = client.app_state.service.db_for("draft")
    row = dict(db.execute("SELECT * FROM brief_fragment_revisions WHERE fragment_id=?", (first["id"],)).fetchone())
    parent = first["id"]
    for index in range(999):  # řetěz 1000 uzlů zapsaný mimo API (např. stará data nebo obnova verze)
        db.execute("INSERT INTO brief_fragment_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (row["project_id"], row["workspace_id"], f"deep{index}", 1, parent, None, 1, "brief", f"d{index}",
                    "x", "draft", "none", "", "t", "agent", 0, row["saved_at"]))
        parent = f"deep{index}"
    db.commit()
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(400)  # rekurzivní průchod by tu spadl (RecursionError)
    try:
        roots = tree(client)["roots"]
    finally:
        sys.setrecursionlimit(limit)
    depth, cursor = 1, roots[0]
    while cursor["children"]:
        depth, cursor = depth + 1, cursor["children"][0]
    assert depth == MAX_DEPTH and cursor["hidden"] == 1000 - MAX_DEPTH
    assert roots[0]["coverage"]["leaves"] == 1 and len(json.dumps(roots)) > 0


def test_changed_since_insert_counts_only_text_revisions(client):
    item = root(client)
    digest = client.get("/api/view", params=SCOPE).json()["digest"]
    planned = client.post("/api/canvas-plan", headers=AGENT, json={**SCOPE, "digest": digest, "plan": {
        "nodes": [{"ref": "k", "kind": "node", "parent": "@s1", "name": "[task] K", "fragmentRef": {"fragmentId": item["id"]}}]}})
    assert planned.status_code == 200, planned.text
    card = planned.json()["refs"]["k"]
    post(client, op="propose-mvp", fragmentIds=[item["id"]])
    post(client, op="revise", fragmentId=item["id"], expectedRevision=2, stage="ready", note="stage")
    node_view = tree(client)["roots"][0]
    assert node_view["revision"] == 3 and node_view["textRevision"] == 1 and node_view["status"] == "inserted"
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": card}).json()["fragments"]
    assert brief["changed"] == 0 and brief["items"][0]["changedSinceInsert"] is False
    post(client, op="revise", fragmentId=item["id"], expectedRevision=3, text="Nový text.", note="text")
    node_view = tree(client)["roots"][0]
    assert node_view["textRevision"] == 4 and node_view["status"] == "changed" and node_view["mvp"] == "proposed"


def test_history_lists_revisions_of_scope(client):
    item = root(client)
    post(client, op="revise", fragmentId=item["id"], expectedRevision=1, text="v2", note="druhá")
    post(client, op="create", scopeNodeId="", title="Plátno", text="p")
    items = client.get("/api/brief-vault/history", params={**SCOPE, "scope": "s1"}).json()["items"]
    assert [(entry["revision"], entry["note"]) for entry in items] == [(2, "druhá"), (1, "Vloženo do schránky.")]
    assert "text" not in items[0] and items[0]["chars"] == 2
