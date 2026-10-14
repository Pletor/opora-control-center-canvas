"""Fronta `/api/brief-vault/next` (docs/schranka-neurony.md §9 body 8 a 9): pořadí, vyloučení, needs a blocked."""
import pytest

from backend.editor.brief_vault.test_brief_vault_discipline import (
    HEADERS,
    SCOPE,
    post,
    split_root,
)
from backend.editor.brief_vault.test_brief_vault_gates import (
    WEIGHED,
    gate,
    root,
    vault_client,
    walk,
)


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def next_of(client, expect=200, **params):
    response = client.get("/api/brief-vault/next", params={**SCOPE, **params})
    assert response.status_code == expect, response.text
    return response.json()


def test_empty_queue_and_bad_filter(client):
    assert next_of(client) == {"fragment": None, "blocked": 0}
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
    assert found["blocked"] == 3  # tři fragmenty čekají na návrh weighed


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
    assert next_of(client, discipline="db") == {"fragment": None, "blocked": 0}
    dead = walk(client, first, "synthesized")
    gate(client, dead, "decided", payload={"verdict": "no", "reason": "Ne."})
    parent = walk(client, parent, "placed")  # rodič vložený na plátno: děti pokryté předkem
    assert next_of(client, discipline="ux") == {"fragment": None, "blocked": 0}
    found = next_of(client)
    assert found["fragment"]["id"] == parent["id"] and found["gate"] == "verified" and found["blocked"] == 1
    post(client, headers=HEADERS, op="delete", fragmentId=parent["id"], expectedRevision=parent["revision"], note="pryč")
    assert next_of(client) == {"fragment": None, "blocked": 0}


def test_planned_is_a_confirm_and_placed_is_blocked(client):
    fragment = walk(client, root(client), "decided")
    found = next_of(client)
    assert found["fragment"]["id"] == fragment["id"] and found["gate"] == "planned"
    assert found["needs"] == "confirm" and "proposal" not in found and found["blocked"] == 0
    gate(client, fragment, "planned")
    assert next_of(client) == {"fragment": None, "blocked": 1}  # placed čeká na schválení zápisu člověkem
