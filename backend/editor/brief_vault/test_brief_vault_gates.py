"""Brány cyklu přes API (docs/schranka-neurony.md §3, §9 body 4 a 9): pořadí a kaskáda, CAS, append-only,
otisk vstupů, návrh → potvrzení, decided no/other, payload planned/placed jen od serveru, souběh dvou zápisů."""
import json
import threading
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.brief_vault.brief_vault_gate_rules import GATES
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
    """Zapne brány od scoped po `upto` (včetně) s payloady z PAYLOADS (planned a placed bez payloadu, plán
    skládá server); vrací poslední revizi fragmentu."""
    for name in GATES[:GATES.index(upto) + 1]:
        extra = {"payload": PAYLOADS[name]} if name in PAYLOADS else {}
        fragment = gate(client, fragment, name, **extra)["fragment"]
    return fragment


def stored(client, fragment_id):
    db = client.app_state.service.db_for("draft")
    return [(row["revision"], row["text"], json.loads(row["gates"]) if row["gates"] else {}) for row in db.execute(
        "SELECT revision, text, gates FROM brief_fragment_revisions WHERE fragment_id=? ORDER BY revision", (fragment_id,))]


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
    gate(client, fragment, "placed", expect=400)  # placed až po planned
    for name in ("planned", "placed"):
        gate(client, fragment, name, value=False, expect=409)  # není co vypnout
        gate(client, fragment, name, expect=400, payload={"plan": []})  # payload skládá server
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
    fragment = walk(client, root(client), "placed")
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
    walk(client, parent, "placed")
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


CELL_CHECKS = [{"id": "unit", "command": "uv run pytest backend/cart -q"}]


def cell_run(code, executor="builder", verifier="discipline-1"):
    return {"executor": executor, "verifier": verifier, "at": "2026-10-15T08:00:00+02:00",
            "checks": [{"checkId": "unit", "command": CELL_CHECKS[0]["command"], "exitCode": code, "durationMs": 40,
                        "outputSha256": "0" * 64}]}


def cell_actual(tests, run=None):
    return {"actual": {"tests": tests, "criticRounds": 1, "unexpected": False, **({"run": run} if run else {})}}


def test_cell_checks_reach_the_card_and_verified_needs_a_matching_run(client):
    """docs/schranka-bunka.md §3 body 1–4: karta s GOAL, run proti synthesized.checks, oddělený ověřovatel, druh poučení."""
    fragment = root(client)
    for name in GATES[:GATES.index("placed") + 1]:
        extra = {"payload": {**SYNTH, "checks": CELL_CHECKS}} if name == "synthesized" else (
            {"payload": PAYLOADS[name]} if name in PAYLOADS else {})
        fragment = gate(client, fragment, name, **extra)["fragment"]
    cards = [item for item in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"] if item.get("checks")]
    assert len(cards) == 1 and cards[0]["checks"] == CELL_CHECKS and cards[0]["goal_mode"] == "until_checks_pass"

    def propose(payload, expect=200, headers=AGENT, gate_name="verified"):
        return post(client, expect=expect, headers=headers, op="propose", fragmentId=fragment["id"],
                    expectedRevision=fragment["revision"], gate=gate_name, payload=payload, note="návrh")

    assert "run" in propose(cell_actual("pass"), expect=400)["error"]  # tvrzení bez běhu
    propose(cell_actual("pass", cell_run(1)), expect=400)  # pass s nenulovým kódem
    propose(cell_actual("pass", cell_run(0, executor="discipline-1", verifier="x")), expect=400)  # navrhuje vykonavatel
    gate(client, fragment, "verified", expect=400, payload=cell_actual("fail"))
    builder = {**HEADERS, "X-Opora-Actor": "agent; name=builder"}
    gate(client, fragment, "verified", expect=400, headers=builder, payload=cell_actual("pass", cell_run(0)))
    forged = cell_actual("pass", cell_run(0, verifier="someone-else"))  # ručně zfalšovaný run: ověřovatel jiný než podatel
    propose(forged, expect=400)
    gate(client, fragment, "verified", expect=400, payload=forged)
    propose(cell_actual("fail", cell_run(3)))
    gate(client, fragment, "verified", expect=400, headers=builder)  # potvrzení návrhu vykonavatelem = 400
    propose({**cell_actual("fail", cell_run(3)), "runTrust": "reported"}, expect=400)  # razítko počítá server
    fragment = gate(client, fragment, "verified")["fragment"]
    entry = stored(client, fragment["id"])[-1][2]["verified"]["payload"]
    assert entry["runTrust"] == "reported" and "predictionError" in entry
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment["id"]}).json()
    assert detail["gateDetail"]["verified"]["payload"]["runTrust"] == "reported"
    lesson = {"lesson": "Kontrola spadla na chybějící tabulce.", "kind": "pattern"}
    propose(lesson, expect=400, gate_name="learned")  # po neúspěchu jen antipattern
    gate(client, fragment, "learned", expect=400, payload=lesson)
    done = gate(client, fragment, "learned", payload={**lesson, "kind": "antipattern"})
    assert done["gateStep"] == 8
    fragment = done["fragment"]
    # Nové kolo: kontroly jsou měřítko napříč koly, agent je nezmění; člověk ano.
    fragment = gate(client, fragment, "learned", value=False)["fragment"]
    fragment = gate(client, fragment, "synthesized", value=False)["fragment"]
    changed = {**SYNTH, "checks": [{"id": "unit", "command": "uv run pytest backend -q"}]}
    assert "napříč koly" in propose(changed, expect=400, gate_name="synthesized")["error"]
    gate(client, fragment, "synthesized", expect=400, payload=SYNTH)  # bez checks = změna
    gate(client, fragment, "synthesized", expect=400, payload=changed)
    propose({**SYNTH, "checks": CELL_CHECKS}, gate_name="synthesized")  # stejné kontroly projdou
    assert gate(client, fragment, "synthesized", headers=HEADERS, payload=changed)["gateStep"] == 3


def test_cell_untested_without_run_and_plain_fragment_unchanged(client):
    fragment = root(client)
    for name in GATES[:GATES.index("placed") + 1]:
        extra = {"payload": {**SYNTH, "checks": CELL_CHECKS}} if name == "synthesized" else (
            {"payload": PAYLOADS[name]} if name in PAYLOADS else {})
        fragment = gate(client, fragment, name, **extra)["fragment"]
    assert gate(client, fragment, "verified", payload=cell_actual("untested"))["gateStep"] == 7
    plain = walk(client, post(client, op="create", scopeNodeId="s1", discipline="be", title="Jiný",
                              text="Bez kontrol.")["fragment"], "placed")
    gate(client, plain, "verified", expect=400, payload=cell_actual("pass", cell_run(0)))  # run bez checks
    done = gate(client, plain, "verified", payload=cell_actual("pass"))
    assert done["gateStep"] == 7 and "runTrust" not in stored(client, plain["id"])[-1][2]["verified"]["payload"]
    # Kolo 2 nesmí kontroly přidat (kolo 1 je nemělo): měřítko napříč koly, změnu dělá člověk.
    plain = gate(client, done["fragment"], "synthesized", value=False)["fragment"]
    with_checks = {**SYNTH, "checks": CELL_CHECKS}
    assert "napříč koly" in post(client, expect=400, op="propose", fragmentId=plain["id"],
                                 expectedRevision=plain["revision"], gate="synthesized", payload=with_checks,
                                 note="x")["error"]
    gate(client, plain, "synthesized", expect=400, payload=with_checks)
    assert gate(client, plain, "synthesized", payload=SYNTH)["gateStep"] == 3
