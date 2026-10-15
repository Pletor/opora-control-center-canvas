"""`placed` hlídá jen kontejner plánu, ne celé plátno (docs/schranka-neurony.md §9 bod 2, §12; K12).

Souběžné smyčky jiných disciplín mění plátno i stav Desktop v3; `placed` fragmentu B po `planned` B smí shodit jen
skutečná změna toho, co plán B čte nebo mění (vrstva, oblast skupiny, sektor disciplíny, karta fragmentu a jejich stav)."""
import pytest

from backend.editor.brief_vault.test_brief_vault_discipline import HEADERS, SCOPE, post
from backend.editor.brief_vault.test_brief_vault_gates import gate, root, stored, vault_client, walk
from backend.editor.brief_vault.test_brief_vault_placement import kinds, state, view
from backend.editor.node.test_removals import install_graph

SYNTH = {"type": "SCHEMA", "done": "Import odmítne vadný řádek.", "prediction": {"tests": "pass", "criticRounds": 1,
                                                                                    "risk": "kódování"}}


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def touch_state(client, node_id, phase="define"):
    """Zápis stavu Desktop v3 mimo plán (jiná smyčka): zvedne revizi stavu."""
    current = state(client)
    nodes = dict(current["state"].get("nodes") or {})
    nodes[node_id] = {**(nodes.get(node_id) or {"criteria": [], "steps": []}), "phase": phase}
    saved = client.post("/api/desktop-v3/state", headers=HEADERS, json={
        **SCOPE, "expectedRevision": current["revision"], "state": {**current["state"], "nodes": nodes}})
    assert saved.status_code == 200, saved.text


def second_round(client, fragment):
    """Kolo 2 po `placed`: neúspěšné verified, nové synthesized, decided; vrací revizi připravenou na planned."""
    fragment = gate(client, fragment, "verified", payload={"actual": {"tests": "fail", "criticRounds": 2,
                                                                     "unexpected": False}})["fragment"]
    fragment = gate(client, fragment, "synthesized", value=False)["fragment"]
    fragment = gate(client, fragment, "synthesized", payload=SYNTH)["fragment"]
    return gate(client, fragment, "decided", payload={"verdict": "yes", "reason": "Řeší výtku."})["fragment"]


def test_second_round_placed_survives_unrelated_writes(client):
    """Reprodukce 409 z kol 2–3: mezi planned a placed zapíše jiná smyčka stav jiné karty a vloží svou kartu."""
    fragment = second_round(client, walk(client, root(client), "placed"))
    fragment = gate(client, fragment, "planned")["fragment"]
    assert stored(client, fragment["id"])[-1][2]["planned"]["payload"]["plan"]["extend"]
    touch_state(client, "c1")  # stav cizí karty → jiná revize stavu
    other = walk(client, root(client, discipline="infra"), "planned")
    gate(client, other, "placed")  # karta jiné disciplíny v jiné oblasti → jiný digest plátna
    done = gate(client, fragment, "placed")
    assert done["gates"]["placed"] is True and done["placement"]["refs"] == {}


def test_state_write_elsewhere_alone_does_not_break_second_round(client):
    """Jen revize celého stavu (zápis cizí karty) dřív měnila otisk položky `extend` → 409."""
    fragment = gate(client, second_round(client, walk(client, root(client), "placed")), "planned")["fragment"]
    touch_state(client, "c1")
    assert gate(client, fragment, "placed")["gates"]["placed"] is True


def test_placed_a_between_planned_b_and_placed_b_does_not_break_b(client):
    """Dva souběžné fragmenty různých disciplín téže skupiny: placed A mezi planned B a placed B B neshodí."""
    first = gate(client, walk(client, root(client), "planned"), "placed")  # oblast Logika + sektor Backend
    assert first["gates"]["placed"] is True
    a = walk(client, root(client, discipline="db"), "planned")
    b = walk(client, root(client, discipline="api"), "planned")
    gate(client, a, "placed")
    done = gate(client, b, "placed")
    assert done["gates"]["placed"] is True
    assert len(kinds(client)["area"]) == 1 and len(kinds(client)["sector"]) == 4  # s1 + be, db, api


def test_real_change_of_the_card_still_rejects_placed(client):
    fragment = second_round(client, walk(client, root(client), "placed"))
    [card_id] = [item["id"] for item in kinds(client)["node"] if item["id"] != "c1"]
    fragment = gate(client, fragment, "planned")["fragment"]
    touch_state(client, card_id)  # stav karty fragmentu se změnil
    assert "plán se změnil" in gate(client, fragment, "placed", expect=409)["error"]


def test_real_change_of_the_container_still_rejects_placed(client):
    first = gate(client, walk(client, root(client), "planned"), "placed")["placement"]["refs"]
    other = walk(client, post(client, op="create", scopeNodeId="s1", discipline="be", title="Export",
                              text="Exportuj CSV.")["fragment"], "planned")
    graph = view(client)["graph"]
    moved = [{**item, "name": "Backend v2"} if item["id"] == first["s1"] else item for item in graph["nodes"]]
    install_graph(client, {"nodes": moved, "edges": graph["edges"]})  # sektor disciplíny se změnil
    assert "plán se změnil" in gate(client, other, "placed", expect=409)["error"]


def test_new_sector_of_same_discipline_in_layer_rejects_placed(client):
    """Souběžná smyčka téže skupiny založí oblast dřív: plán B by dnes vypadal jinak (oblast už existuje)."""
    a = walk(client, root(client), "planned")
    b = walk(client, root(client, discipline="db"), "planned")
    gate(client, a, "placed")
    assert "plán se změnil" in gate(client, b, "placed", expect=409)["error"]
