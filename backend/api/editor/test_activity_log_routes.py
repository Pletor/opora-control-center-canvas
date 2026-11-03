"""Stopa karty přes skutečnou aplikaci (docs/zaznam-cinnosti.md, docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md B):
zápisy srdce, které mění karty, nesou v záznamu činnosti `nodeIds` a čitelný popisek; `latest-by-node` vrátí
poslední změnu každé karty jedním dotazem."""
from backend.api.brain_opora.test_heart_order import human_architecture, order
from backend.api.brain_opora.test_heart_plan import heart, plan
from backend.api.brain_opora.test_heart_steps import autonomy
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import SCOPE

__all__ = ["heart"]
LOG = "/api/activity-log"


def heart_writes(client):
    entries = client.get(LOG, params={**SCOPE, "agent": "heart", "limit": 100}).json()["entries"]
    return [entry for entry in entries if entry["status"] < 300]


def test_heart_writes_carry_nodes_and_labels_and_latest_by_node_reads_them(heart):
    client, _, tmp_path = heart
    human_architecture(client)
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE)["refs"]
    autonomy(client, True)
    done = order("--nodes", f"p_home=101,p_faq=102,{refs['mvp']}=201,{refs['model']}=202")
    assert done["accepted"] is True, done

    writes = heart_writes(client)
    by_path = {}
    for entry in writes:
        by_path.setdefault(entry["path"].rsplit("/", 1)[-1] if entry["path"].endswith("/accept") else entry["path"],
                           []).append(entry)
    architecture = by_path["/api/project-architecture"][0]
    assert architecture["label"] == "Architektura: pořadí 2 stránek"
    assert sorted(architecture["nodeIds"]) == ["p_faq", "p_home"]
    proposal = by_path["/api/oporahub/graph-proposals"][0]  # nejnovější: pořadí karet prostoru
    assert proposal["label"] == "Pořadí 2 karet a převzetí architektury", proposal
    assert set(proposal["nodeIds"]) == {refs["mvp"], refs["model"]}
    accepted = by_path["accept"][0]
    assert accepted["label"].startswith("Přijetí: Pořadí 2 karet") and refs["model"] in accepted["nodeIds"], accepted
    # Plán srdce v main přidal karty dávkou: záznam nese ID nových uzlů z odpovědi a souhrn dávky jako popisek.
    added = by_path["/api/canvas-plan"][0]
    assert added["label"] == "Plán: Přidá 1 sektor, 2 karty, 1 vazbu (next 1).", added
    assert set(added["nodeIds"]) == set(refs.values()) and added["summary"] == added["label"] + " | digest,plan"
    assert all(len(entry["label"]) <= 120 for entry in writes)

    latest = client.get(f"{LOG}/latest-by-node", params=SCOPE).json()
    assert latest[refs["model"]]["label"] == accepted["label"]  # přijetí je novější než návrh
    assert (latest[refs["model"]]["actor"], latest[refs["model"]]["agent"]) == ("agent", "heart")
    assert latest["p_home"]["label"] == "Architektura: pořadí 2 stránek"
    assert set(latest[refs["cli"]]) == {"at", "actor", "agent", "label", "path"}
    assert client.get(f"{LOG}/latest-by-node", params={"project": "jiny"}).json() == {}
    assert client.get(f"{LOG}/latest-by-node").status_code == 422


def test_issued_ticket_with_card_is_labelled_by_what_to_build(heart):
    client, call, _ = heart
    body = {"essence": "Proč.", "build": "Hero | sekce\nPodrobnosti.", "doneCriteria": ["npm test projde"]}
    call("POST", "/api/gate/requests", {"kind": "ticket.issue", "body": {"body": body, "cardId": "n1"}})
    entry = heart_writes(client)[0]
    assert (entry["label"], entry["nodeIds"]) == ("Ticket práce: Hero / sekce", ["n1"])
    assert client.get(f"{LOG}/latest-by-node", params=SCOPE).json()["n1"]["label"] == "Ticket práce: Hero / sekce"
