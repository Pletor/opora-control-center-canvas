"""Brány cyklu přes API (docs/schranka-neurony.md §3, §9 body 4 a 9): pořadí a kaskáda, CAS, append-only,
otisk vstupů, návrh → potvrzení, decided no/other, brány K4 odmítnuté, souběh dvou zápisů."""
import json
import threading
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.brief_vault.brief_vault_gate_rules import GATES, encode_gates, input_hash
from backend.editor.brief_vault.test_brief_vault_discipline import (
    AGENT,
    HEADERS,
    SCOPE,
    nodes,
    post,
    split_root,
    tree,
)
from backend.editor.node.test_removals import ORIGIN, install_graph, node

WEIGHED = {"benefit": "Rychlejší import.", "risk": "Rozbití starých dat."}
SYNTH = {"type": "SCHEMA", "done": "Tabulka existuje a test projde.",
         "prediction": {"tests": "pass", "criticRounds": 1, "risk": "migrace"}}
YES = {"verdict": "yes", "reason": "Malé a ověřitelné."}
PAYLOADS = {"weighed": WEIGHED, "synthesized": SYNTH, "decided": YES}


@contextmanager
def vault_client(tmp_path):
    """Aplikace se sektorem s1 a kartou c1 (sdílí ji testy bran, fronty a poučení)."""
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("c1", "s1")], "edges": []})
        client.app_state = app.state
        yield client


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def gate(client, fragment, name, value=True, expect=200, headers=AGENT, **extra):
    """op gate na poslední revizi fragmentu (dict s id a revision); vrací odpověď."""
    return post(client, expect=expect, headers=headers, op="gate", fragmentId=fragment["id"],
                expectedRevision=fragment["revision"], gate=name, value=value, note=f"{name}: {value}", **extra)


def walk(client, fragment, upto):
    """Zapne brány od scoped po `upto` (včetně) s payloady z PAYLOADS; vrací poslední revizi fragmentu."""
    for name in GATES[:GATES.index(upto) + 1]:
        extra = {"payload": PAYLOADS[name]} if name in PAYLOADS else {}
        fragment = gate(client, fragment, name, **extra)["fragment"]
    return fragment


def stored(client, fragment_id):
    db = client.app_state.service.db_for("draft")
    return [(row["revision"], row["text"], json.loads(row["gates"]) if row["gates"] else {}) for row in db.execute(
        "SELECT revision, text, gates FROM brief_fragment_revisions WHERE fragment_id=? ORDER BY revision", (fragment_id,))]


def force(client, fragment_id, upto, discipline="be", **payloads):
    """Zapíše revizi s platnými branami po `upto` mimo API (simulace K4 pro planned/placed)."""
    db = client.app_state.service.db_for("draft")
    row = dict(db.execute("SELECT * FROM brief_fragment_revisions WHERE fragment_id=? ORDER BY revision DESC LIMIT 1",
                          (fragment_id,)).fetchone())
    digest, revision = input_hash(row["title"], row["text"], discipline), row["revision"] + 1
    entries = {name: {"value": True, "payload": {**PAYLOADS, **payloads}.get(name), "by": "k4", "actor": "agent", "at": "T",
                      "inputHash": digest, "revision": revision} for name in GATES[:GATES.index(upto) + 1]}
    with db:
        db.execute("INSERT INTO brief_fragment_revisions(project_id,workspace_id,fragment_id,revision,parent_id,scope_node_id,ord,"
                   "kind,title,text,stage,mvp,note,by,actor,deleted,saved_at,discipline,gates)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (row["project_id"], row["workspace_id"], fragment_id, revision, row["parent_id"], row["scope_node_id"],
                    row["ord"], row["kind"], row["title"], row["text"], row["stage"], row["mvp"], "K4 simulace", "k4", "agent",
                    0, row["saved_at"], row["discipline"], encode_gates(entries)))
    return {"id": fragment_id, "revision": revision}


def root(client, discipline="be"):
    return post(client, op="create", scopeNodeId="s1", discipline=discipline, title="Import", text="Importuj CSV.")["fragment"]


def test_order_cascade_and_tree(client):
    fragment = root(client)
    assert nodes(tree(client))[fragment["id"]]["gateStep"] == 0
    gate(client, fragment, "weighed", expect=400, payload=WEIGHED)
    fragment = walk(client, fragment, "decided")
    found = nodes(tree(client))[fragment["id"]]
    assert found["gateStep"] == 4 and found["gatesStale"] is False and found["gates"]["decided"] is True
    assert set(found["gates"]) == {*GATES, "predictionError"} and found["gates"]["predictionError"] is None
    for name in ("planned", "placed"):
        assert "K4" in gate(client, fragment, name, expect=400)["error"]
        gate(client, fragment, name, value=False, expect=400)
    off = gate(client, fragment, "weighed", value=False)
    assert off["gateStep"] == 1 and off["gates"]["synthesized"] is False and off["gates"]["decided"] is False
    history = stored(client, fragment["id"])
    assert history[3][2]["synthesized"]["payload"] == SYNTH  # payload vypnuté brány zůstává v historii revizí
    assert all(history[-1][2][name]["value"] is False for name in GATES[1:])
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment["id"]}).json()
    assert detail["gateStep"] == 1 and detail["gateDetail"]["scoped"]["valid"] is True


def test_cas_append_only_and_no_ops(client):
    fragment = root(client)
    first = gate(client, fragment, "scoped")["fragment"]
    gate(client, fragment, "weighed", expect=409, payload=WEIGHED)  # stará revize
    gate(client, first, "scoped", expect=409)  # už zapnutá
    gate(client, first, "weighed", value=False, expect=409)  # není co vypnout
    post(client, expect=409, op="gate", fragmentId=first["id"], expectedRevision=first["revision"], gate="weighed",
         value=True, note="", payload=WEIGHED)
    for broken in ({"value": "yes"}, {"gate": "nope"}, {"value": False, "payload": WEIGHED}):
        post(client, expect=400, **{"op": "gate", "fragmentId": first["id"], "expectedRevision": first["revision"],
                                    "gate": "weighed", "value": True, "note": "x", **broken})
    gate(client, first, "scoped", value=False, expect=200)
    assert [text for _, text, _ in stored(client, fragment["id"])] == ["Importuj CSV."] * 3
    assert nodes(tree(client))[fragment["id"]]["title"] == "Import"


def test_input_hash_invalidates_after_revise_and_ancestor_discipline(client):
    parent, (child, _) = split_root(client)
    child = walk(client, child, "weighed")
    parent = walk(client, parent, "scoped")
    revised = post(client, op="revise", fragmentId=parent["id"], expectedRevision=parent["revision"], text="nový text",
                   note="upřesnění")["fragment"]
    found = nodes(tree(client))
    assert found[parent["id"]]["gatesStale"] is True and found[parent["id"]]["gateStep"] == 0
    assert found[child["id"]]["gateStep"] == 2  # revize rodiče dítě nezneplatní (jiný text)
    post(client, op="set-discipline", fragmentId=parent["id"], expectedRevision=revised["revision"], discipline="ux",
         note="Obrazovka.")
    found = nodes(tree(client))
    assert found[child["id"]]["gatesStale"] is True and found[child["id"]]["gates"]["scoped"] is False
    gate(client, child, "weighed", expect=400, payload=WEIGHED)  # zneplatněné = vypnuté, pořadí od scoped
    again = gate(client, child, "scoped")
    assert again["gateStep"] == 1 and again["gatesStale"] is False  # zneplatněné záznamy nová revize nepřevezme


def test_propose_then_gate_without_payload(client):
    fragment = walk(client, root(client), "scoped")
    assert "chybí návrh" in gate(client, fragment, "weighed", expect=400)["error"]
    post(client, expect=400, op="propose", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate="scoped",
         payload=None, note="x")
    post(client, expect=400, op="propose", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate="weighed",
         payload={"benefit": "b"}, note="x")
    post(client, expect=409, op="propose", fragmentId=fragment["id"], expectedRevision=1, gate="weighed",
         payload=WEIGHED, note="x")
    proposal = post(client, op="propose", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate="weighed",
                    payload=WEIGHED, note="Přínos a riziko.")["proposal"]
    assert proposal["revision"] == fragment["revision"] and proposal["by"] == "discipline-1"
    assert stored(client, fragment["id"])[-1][0] == fragment["revision"]  # návrh revizi nepřidá
    done = gate(client, fragment, "weighed")
    assert done["gateStep"] == 2 and stored(client, fragment["id"])[-1][2]["weighed"]["payload"] == WEIGHED
    off = gate(client, done["fragment"], "weighed", value=False)["fragment"]
    assert "chybí návrh" in gate(client, off, "weighed", expect=400)["error"]  # návrh před vypnutím už neplatí
    post(client, op="propose", fragmentId=fragment["id"], expectedRevision=off["revision"], gate="weighed",
         payload=WEIGHED, note="znovu")
    revised = post(client, op="revise", fragmentId=fragment["id"], expectedRevision=off["revision"], text="jiný",
                   note="změna")["fragment"]
    revised = gate(client, revised, "scoped")["fragment"]
    assert "chybí návrh" in gate(client, revised, "weighed", expect=400)["error"]  # jiný otisk vstupů


def test_decided_no_is_dead_end_and_other_returns_to_synthesized(client):
    _parent, (first, second) = split_root(client)
    dead = walk(client, first, "synthesized")
    dead = gate(client, dead, "decided", payload={"verdict": "no", "reason": "Mimo rozsah."})
    assert dead["gateStep"] == 4 and dead["deadEnd"] is True
    post(client, expect=400, op="propose", fragmentId=first["id"], expectedRevision=dead["fragment"]["revision"],
         gate="verified", payload={"actual": {"tests": "pass", "criticRounds": 0, "unexpected": False}}, note="x")
    assert nodes(tree(client))[first["id"]]["deadEnd"] is True
    other = walk(client, second, "synthesized")
    post(client, op="propose", fragmentId=second["id"], expectedRevision=other["revision"], gate="decided",
         payload={"verdict": "other", "reason": "Menší krok."}, note="jinak")
    back = gate(client, other, "decided")
    assert back["returnedTo"] == "synthesized" and back["gateStep"] == 2 and back["deadEnd"] is False
    entries = stored(client, second["id"])[-1][2]
    assert entries["decided"]["value"] is False and entries["decided"]["payload"]["verdict"] == "other"
    assert "chybí návrh" in gate(client, back["fragment"], "synthesized", expect=400)["error"]


def test_verified_stores_prediction_error(client):
    fragment = force(client, root(client)["id"], "placed")
    done = gate(client, fragment, "verified", payload={"actual": {"tests": "fail", "criticRounds": 2, "unexpected": False}})
    assert done["gateStep"] == 7 and done["gates"]["predictionError"] == 0.5
    assert stored(client, fragment["id"])[-1][2]["verified"]["payload"]["predictionError"] == 0.5
    assert nodes(tree(client))[fragment["id"]]["gates"]["predictionError"] == 0.5


def test_gates_need_a_brief_with_discipline_and_live_ancestors(client):
    parent, (first, _) = split_root(client)
    research = post(client, op="research", fragmentId=first["id"], title="Ověřit", text="")["fragment"]
    gate(client, research, "scoped", expect=400)
    post(client, headers=HEADERS, op="delete", fragmentId=parent["id"], expectedRevision=1, note="pryč")
    gate(client, first, "scoped", expect=409)


def test_covered_fragment_gates_are_human_only(client):
    parent, (first, _) = split_root(client)
    force(client, parent["id"], "placed")
    response = client.post("/api/brief-vault", headers=AGENT, json={
        **SCOPE, "op": "gate", "fragmentId": first["id"], "expectedRevision": 1, "gate": "scoped", "value": True, "note": "x"})
    assert response.status_code == 403
    assert gate(client, first, "scoped", headers=HEADERS)["gateStep"] == 1


def test_two_concurrent_gates_on_the_same_revision(client):
    fragment = root(client)
    results = []

    def run():
        results.append(client.post("/api/brief-vault", headers=AGENT, json={
            **SCOPE, "op": "gate", "fragmentId": fragment["id"], "expectedRevision": 1, "gate": "scoped", "value": True,
            "note": "souběh"}).status_code)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [200, 409] and len(stored(client, fragment["id"])) == 2


def test_old_snapshot_without_gates_and_lessons_keeps_digest_and_validates():
    from backend.editor.canvas_versions.version_content import (
        STORES,
        content_digest,
        empty_data,
        validate_records,
        with_later_stores,
    )
    row = {key: value for key, value in empty_data("briefFragments").items() if key != "gates"}
    row.update(scope_node_id="", ord=1, title="T", text="t", actor="agent", deleted=0, discipline="be")
    records = {name: [] for name in STORES if name != "briefLessons"}
    records["briefFragments"] = [{"key": ["f1"], "revision": 1, "data": row}]
    upgraded = with_later_stores(records)
    assert upgraded["briefLessons"] == [] and upgraded["briefFragments"][0]["data"]["gates"] is None
    assert content_digest({}, {}, {"records": records, "assets": []}) == content_digest({}, {}, {"records": upgraded, "assets": []})
    validate_records(upgraded, "draft", "main")
