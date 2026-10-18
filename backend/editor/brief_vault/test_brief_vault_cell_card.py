"""Shoda měřítek buňky a karty napříč koly (docs/schranka-bunka.md §3 body 1–2): člověk smí v kole ≥ 2 změnit
nebo přidat `checks`, `extend` je ale na existující kartu nepřenáší. Plán proto při nesouladu kontrol karty a
`synthesized` vrátí 409 `checks-mismatch` (fail-closed); po ruční úpravě karty člověkem projde. Stejné kontroly
v dalším kole projdou beze změny. Změna karty uvnitř `placed` (po přestavbě plánu, před zápisem) neprojde: celé
`placed` drží zámek grafu a `apply_plan` porovná digest plátna z jeho začátku.

Mimo rozsah: dětské karty kontroly nenesou (checks patří jen kartě za F, `card_of` s `lead`), takže je kontrola
nesouladu nehlídá; karta fragmentu v jiné vrstvě se nehledá (`existing_card` hledá jen ve vrstvě plánu, beze změny)."""
import copy

import pytest

from backend.editor.brief_vault import brief_vault_placement
from backend.editor.brief_vault.brief_vault_gate_rules import GATES
from backend.editor.brief_vault.brief_vault_plan_update import checks_mismatch
from backend.editor.brief_vault.test_brief_vault_discipline import AGENT, HEADERS, SCOPE
from backend.editor.brief_vault.test_brief_vault_gates import PAYLOADS, SYNTH, gate, root, stored, vault_client

A = [{"id": "unit", "command": "python -m pytest -q test_a.py"}]
B = [{"id": "unit", "command": "python -m pytest -q test_b.py"}]
C = [{"id": "unit", "command": "python -m pytest -q test_c.py"}]


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def synth(checks):
    return {**SYNTH, **({"checks": checks} if checks else {})}


def first_round(client, checks):
    fragment = root(client)
    for name in GATES[:GATES.index("placed") + 1]:
        extra = {"payload": synth(checks)} if name == "synthesized" else (
            {"payload": PAYLOADS[name]} if name in PAYLOADS else {})
        fragment = gate(client, fragment, name, **extra)["fragment"]
    return fragment


def second_round(client, fragment, checks, headers):
    fragment = gate(client, fragment, "synthesized", value=False)["fragment"]
    fragment = gate(client, fragment, "synthesized", headers=headers, payload=synth(checks))["fragment"]
    return gate(client, fragment, "decided", payload=PAYLOADS["decided"])["fragment"]


def cards(client):
    return [item for item in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]
            if item["kind"] == "node" and item.get("name", "").startswith("[task] ")]


def measures(client):
    return [(card.get("checks"), card.get("goal_mode")) for card in cards(client)]


def with_card_checks(graph, checks):
    graph = copy.deepcopy(graph)
    (card,) = [item for item in graph["nodes"] if item["kind"] == "node" and item.get("name", "").startswith("[task] ")]
    card["checks"], card["goal_mode"] = copy.deepcopy(checks), "until_checks_pass"
    return graph


def human_sets_card_checks(client, checks):
    view = client.get("/api/view", params=SCOPE).json()
    graph = with_card_checks(view["graph"], checks)
    response = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("before", [A, None], ids=["A-to-B", "none-to-B"])
def test_human_changed_checks_block_plan_until_card_is_fixed(client, before):
    fragment = first_round(client, before)
    card_before = measures(client)
    fragment = second_round(client, fragment, B, HEADERS)
    revisions = len(stored(client, fragment["id"]))
    response = gate(client, fragment, "planned", expect=409)
    assert [item["reason"] for item in response["fragments"]] == ["checks-mismatch"]
    assert "jiné kontroly než synthesized" in response["error"]
    assert measures(client) == card_before
    assert len(stored(client, fragment["id"])) == revisions
    human_sets_card_checks(client, B)
    fragment = gate(client, fragment, "planned")["fragment"]
    fragment = gate(client, fragment, "placed")["fragment"]
    assert measures(client) == [(B, "until_checks_pass")]


def test_same_checks_in_next_round_still_plan(client):
    fragment = second_round(client, first_round(client, A), A, AGENT)
    fragment = gate(client, fragment, "planned")["fragment"]
    gate(client, fragment, "placed")
    assert measures(client) == [(A, "until_checks_pass")]


def test_card_changed_between_planned_and_placed_blocks_placed(client):
    fragment = second_round(client, first_round(client, A), A, AGENT)
    fragment = gate(client, fragment, "planned")["fragment"]
    human_sets_card_checks(client, C)
    revisions = len(stored(client, fragment["id"]))
    response = gate(client, fragment, "placed", expect=409)
    assert [item["reason"] for item in response["fragments"]] == ["checks-mismatch"]
    assert measures(client) == [(C, "until_checks_pass")]
    assert len(stored(client, fragment["id"])) == revisions


def test_card_changed_inside_placed_after_rebuild_is_not_written(client, monkeypatch):
    """Karta se změní (checks C) až po přestavbě plánu v `placed`, těsně před zápisem dávky (`checkpoint` verze
    plátna leží mezi `_stored_plan` a `apply_plan`); zápis to musí odmítnout přes digest plátna."""
    fragment = second_round(client, first_round(client, A), A, AGENT)
    fragment = gate(client, fragment, "planned")["fragment"]
    service, original = client.app_state.service, brief_vault_placement.CanvasVersions

    class ChangingVersions(original):
        def checkpoint(self, project, workspace, *args, **kwargs):
            result = super().checkpoint(project, workspace, *args, **kwargs)
            view = service.view(project, workspace)
            service.save_graph(project, workspace, with_card_checks(view["graph"], C), view["digest"])
            return result

    monkeypatch.setattr(brief_vault_placement, "CanvasVersions", ChangingVersions)
    revisions = len(stored(client, fragment["id"]))
    response = gate(client, fragment, "placed", expect=409)
    assert "Plátno se změnilo" in response["error"]
    assert measures(client) == [(C, "until_checks_pass")]
    assert len(stored(client, fragment["id"])) == revisions


def test_legacy_round_without_checks_still_plans(client):
    fragment = first_round(client, None)
    card_before = measures(client)
    assert card_before == [(None, None)]
    fragment = second_round(client, fragment, None, AGENT)
    fragment = gate(client, fragment, "planned")["fragment"]
    gate(client, fragment, "placed")
    assert measures(client) == card_before


def test_checks_mismatch():
    good = {"checks": copy.deepcopy(A), "goal_mode": "until_checks_pass"}
    assert not checks_mismatch(good, synth(A))
    assert checks_mismatch(good, synth(B))
    assert checks_mismatch(good, synth(None))  # karta s kontrolami, synthesized bez nich
    assert checks_mismatch({"checks": A}, synth(A))  # bez goal_mode
    assert checks_mismatch({"checks": A, "goal_mode": "manual"}, synth(A))
    assert checks_mismatch({}, synth(B))
    # Legacy: bez kontrol a bez goal_mode (i prázdné pole) nesoulad není.
    assert not checks_mismatch({}, synth(None))
    assert not checks_mismatch({"checks": None, "goal_mode": None}, synth(None))
    assert not checks_mismatch({"checks": []}, None)
    assert checks_mismatch({"checks": [], "goal_mode": "until_checks_pass"}, synth(None))
    assert checks_mismatch({"goal_mode": "until_checks_pass"}, None)
    # Neplatná struktura kontrol karty = nesoulad (fail-closed), i když by se po zahození položky shodovala.
    for broken in ("unit", {"id": "unit"}, [*A, "x"], [{**A[0], "extra": 1}], [{"id": "unit"}],
                   [{"id": 1, "command": A[0]["command"]}], [{"id": "unit", "command": None}]):
        assert checks_mismatch({"checks": broken, "goal_mode": "until_checks_pass"}, synth(A)), broken
        assert checks_mismatch({"checks": broken}, synth(None)), broken
