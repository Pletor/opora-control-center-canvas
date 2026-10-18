"""Fronta `/api/brief-vault/next` (docs/schranka-neurony.md §9 body 8 a 9): pořadí, vyloučení, needs a blocked."""
import pytest

from backend.editor.brief_vault.brief_vault_gate_rules import GATES, MAX_ROUNDS
from backend.editor.brief_vault.test_brief_vault_discipline import (
    HEADERS,
    SCOPE,
    nodes,
    post,
    split_root,
    tree,
)
from backend.editor.brief_vault.test_brief_vault_gates import (
    PAYLOADS,
    WEIGHED,
    gate,
    root,
    vault_client,
    walk,
)
from backend.editor.node.test_removals import install_graph, node


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def idle(**counts):
    """Prázdná fronta s rozkladem blokovaných (`blocked` = součet `blockedBy`)."""
    by = {"proposal": 0, "confirm": 0, "exhausted": 0, "plan": 0, "duel": 0, **counts}
    return {"fragment": None, "blocked": sum(by.values()), "blockedBy": by}


def next_of(client, expect=200, **params):
    response = client.get("/api/brief-vault/next", params={**SCOPE, **params})
    assert response.status_code == expect, response.text
    return response.json()


def test_empty_queue_and_bad_filter(client):
    assert next_of(client) == idle()
    next_of(client, expect=400, discipline="neni")
    next_of(client, expect=400, discipline="none")


def test_order_by_gate_then_depth_then_ord(client):
    parent, (first, second) = split_root(client)
    found = next_of(client)
    assert found["fragment"]["id"] == parent["id"] and found["gate"] == "scoped" and found["needs"] == "confirm"
    assert found["fragment"]["effectiveDiscipline"] == "be" and found["lessons"] == [] and "proposal" not in found
    parent = walk(client, parent, "scoped")
    assert next_of(client)["fragment"]["id"] == first["id"]  # scoped (brána 1) má přednost před weighed rodiče
    walk(client, first, "scoped")
    assert next_of(client)["fragment"]["id"] == second["id"]
    walk(client, second, "scoped")
    found = next_of(client)
    assert found["fragment"]["id"] == parent["id"] and found["gate"] == "weighed" and found["needs"] == "proposal"
    assert found["blocked"] == 3 and found["blockedBy"]["proposal"] == 3  # tři fragmenty čekají na návrh weighed


def test_proposal_turns_needs_into_confirm(client):
    fragment = walk(client, post(client, op="create", scopeNodeId="s1", discipline="db", title="T", text="t")["fragment"],
                    "scoped")
    post(client, op="propose", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate="weighed",
         payload=WEIGHED, note="návrh")
    found = next_of(client)
    assert found["needs"] == "confirm" and found["proposal"]["payload"] == WEIGHED and found["blocked"] == 0
    assert found["fragment"]["revision"] == fragment["revision"]
    gate(client, fragment, "weighed")
    assert next_of(client)["gate"] == "synthesized"


def test_exclusions_and_discipline_filter(client):
    parent, (first, second) = split_root(client)
    post(client, op="research", fragmentId=first["id"], title="Ověřit", text="")
    post(client, op="set-discipline", fragmentId=second["id"], expectedRevision=1, discipline="ux", note="UI")
    assert next_of(client, discipline="ux")["fragment"]["id"] == second["id"]
    assert next_of(client, discipline="db") == idle()
    dead = walk(client, first, "synthesized")
    gate(client, dead, "decided", payload={"verdict": "no", "reason": "Ne."})
    parent = walk(client, parent, "placed")  # rodič vložený na plátno: děti pokryté předkem
    assert next_of(client, discipline="ux") == idle()
    found = next_of(client)
    assert found["fragment"]["id"] == parent["id"] and found["gate"] == "verified" and found["blocked"] == 1
    post(client, headers=HEADERS, op="delete", fragmentId=parent["id"], expectedRevision=parent["revision"], note="pryč")
    assert next_of(client) == idle()


def test_planned_is_a_confirm_and_placed_is_blocked(client):
    fragment = walk(client, root(client), "decided")
    found = next_of(client)
    assert found["fragment"]["id"] == fragment["id"] and found["gate"] == "planned"
    assert found["needs"] == "confirm" and "proposal" not in found and found["blocked"] == 0
    gate(client, fragment, "planned")
    assert next_of(client) == idle(confirm=1)  # placed čeká na schválení zápisu člověkem


def test_stale_saved_plan_counts_as_plan_not_confirm(client):
    gate(client, walk(client, root(client), "decided"), "planned")
    assert next_of(client) == idle(confirm=1)
    graph = client.get("/api/view", params=SCOPE).json()["graph"]
    install_graph(client, {"nodes": [*graph["nodes"], node("c2", "s1")], "edges": graph["edges"]})
    assert next_of(client) == idle(plan=1)  # plátno se změnilo: placed by dal 409, chce nové planned


FAIL = {"actual": {"tests": "fail", "criticRounds": 2, "unexpected": False}}


def resume(client, fragment, upto):
    """Nové kolo: brány od synthesized po `upto` s payloady z PAYLOADS (plán skládá server)."""
    for name in GATES[GATES.index("synthesized"):GATES.index(upto) + 1]:
        extra = {"payload": PAYLOADS[name]} if name in PAYLOADS else {}
        fragment = gate(client, fragment, name, **extra)["fragment"]
    return fragment


def test_rounds_count_failed_verify_then_new_synthesized_and_exhaust(client):
    fragment = walk(client, root(client), "placed")
    for number in range(1, MAX_ROUNDS + 1):
        head = next_of(client)
        assert head["gate"] == "verified" and head["fragment"]["round"] == number and not head["fragment"]["exhausted"]
        fragment = gate(client, fragment, "verified", payload=FAIL)["fragment"]
        assert next_of(client)["fragment"]["round"] == number  # learned neúspěšného kola ještě patří do kola
        fragment = gate(client, fragment, "synthesized", value=False)["fragment"]  # nové kolo
        if number < MAX_ROUNDS:
            assert next_of(client)["fragment"]["round"] == number + 1
            fragment = resume(client, fragment, "placed")
    assert next_of(client) == idle(exhausted=1)
    item = nodes(tree(client))[fragment["id"]]
    assert item["round"] == MAX_ROUNDS + 1 and item["exhausted"] is True
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment["id"]}).json()
    assert detail["round"] == MAX_ROUNDS + 1 and detail["exhausted"] is True
    cards = [item for item in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"] if item["kind"] == "node"]
    assert len(cards) == 2  # c1 + jediná karta fragmentu přes tři kola placed
