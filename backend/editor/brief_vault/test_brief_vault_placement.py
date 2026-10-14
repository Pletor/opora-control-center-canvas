"""Plán a vložení přes API (docs/schranka-neurony.md §4, §9 body 1, 2, 3 a 6): `POST /api/brief-vault/plan` jen čte,
`planned` uloží neměnný plán, `placed` ho atomicky vloží (selhání = nic), konflikt plátna nebo zadání = 409,
dvojí `placed` = 409, vypnutí karty nemaže a znovu vložit jde až po novém `planned`; značky v canvas-plan."""
import pytest

from backend.editor.brief_vault import brief_vault_placement
from backend.editor.brief_vault.brief_vault_plan import plan_hash
from backend.editor.brief_vault.test_brief_vault_discipline import (
    HEADERS,
    SCOPE,
    nodes,
    post,
    split_root,
    tree,
)
from backend.editor.brief_vault.test_brief_vault_gates import gate, root, stored, vault_client, walk
from backend.editor.node.test_removals import install_graph, node


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def view(client):
    return client.get("/api/view", params=SCOPE).json()


def state(client):
    return client.get("/api/desktop-v3/state", params=SCOPE).json()


def plan(client, ids, expect=200):
    response = client.post("/api/brief-vault/plan", headers=HEADERS, json={**SCOPE, "fragmentIds": ids})
    assert response.status_code == expect, response.text
    return response.json()


def kinds(client):
    graph = view(client)["graph"]
    return {kind: [item for item in graph["nodes"] if item["kind"] == kind] for kind in ("area", "sector", "node")}


def test_plan_endpoint_only_reads_and_feeds_canvas_plan(client):
    fragment = walk(client, root(client), "synthesized")
    before = (view(client)["digest"], state(client)["revision"], len(stored(client, fragment["id"])))
    found = plan(client, [fragment["id"]])
    assert found["summary"] == "Přidá 1 oblast, 1 sektor, 1 kartu, 4 bloky, 1 port, text u 1 karty."
    assert len(found["hash"]) == 64 and found["hash"] == plan_hash(found["plan"]) and found["skipped"] == 0
    assert (view(client)["digest"], state(client)["revision"], len(stored(client, fragment["id"]))) == before
    decided = gate(client, fragment, "decided", payload={"verdict": "yes", "reason": "Malé."})["fragment"]
    assert plan(client, [fragment["id"]])["hash"] == found["hash"]  # zápis brány plán nemění
    plan(client, [fragment["id"], "neni"], expect=409)
    assert client.post("/api/brief-vault/plan", headers=HEADERS, json=SCOPE).status_code == 400
    plan(client, [post(client, op="create", scopeNodeId="s1", discipline="be", title="B", text="b")["fragment"]["id"]],
         expect=409)  # bez synthesized
    # Tlačítka UI pošlou dávku na /api/canvas-plan se schválením jako dřív.
    written = client.post("/api/canvas-plan", headers=HEADERS, json={**SCOPE, "digest": view(client)["digest"],
                                                                     "plan": found["plan"]})
    assert written.status_code == 200, written.text
    item = nodes(tree(client))[fragment["id"]]
    assert item["inserted"] is True and item["changedSinceInsert"] is False
    gate(client, decided, "decided", value=False)  # další zápis brány „zadání se změnilo“ nehlásí
    assert nodes(tree(client))[fragment["id"]]["changedSinceInsert"] is False
    other = walk(client, post(client, op="create", scopeNodeId="s1", discipline="db", title="C", text="c")["fragment"],
                 "synthesized")
    again = plan(client, [other["id"]])["plan"]["nodes"]
    sector = kinds(client)["sector"]
    area = next(item for item in kinds(client)["area"])
    assert [item["kind"] for item in again] == ["sector", "node"] and again[0]["parent"] == "@" + area["id"]
    assert len(sector) == 2  # s1 + sektor Backend; db dostane nový sektor v téže oblasti Logika


def test_planned_stores_immutable_plan_and_placed_inserts_it(client):
    fragment = walk(client, root(client), "planned")
    payload = stored(client, fragment["id"])[-1][2]["planned"]["payload"]
    assert set(payload) == {"planId", "generator", "sourceRevisions", "sourceHashes", "scope", "digest", "plan", "hash",
                            "summary"}
    assert payload["generator"] == 1 and payload["scope"] == "s1" and payload["digest"] == view(client)["digest"]
    assert payload["hash"] == plan_hash(payload["plan"]) and kinds(client)["area"] == []
    done = gate(client, fragment, "placed")
    assert done["gates"]["placed"] is True and set(done["placement"]["refs"]) == {"a1", "s1", "f1"}
    refs = done["placement"]["refs"]
    current = state(client)["state"]["nodes"]
    assert current[refs["a1"]]["briefGroup"] == "logika" and current[refs["s1"]]["briefDiscipline"] == "be"
    card = current[refs["f1"]]
    assert card["fragmentRefs"][0]["fragmentId"] == fragment["id"] and len(card["fragmentRefs"][0]["contentHash"]) == 64
    assert stored(client, fragment["id"])[-1][2]["placed"]["payload"]["planId"] == payload["planId"]
    after = gate(client, done["fragment"], "verified", payload={"actual": {"tests": "pass", "criticRounds": 0,
                                                                          "unexpected": False}})
    item = nodes(tree(client))[fragment["id"]]
    assert after["gateStep"] == 7 and item["inserted"] is True and item["changedSinceInsert"] is False
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": refs["f1"]}).json()["fragments"]
    assert brief["items"][0]["changedSinceInsert"] is False and brief["changed"] == 0


@pytest.mark.parametrize("breaks", ["graph", "gate"])
def test_failed_placed_leaves_no_revision_and_no_cards(client, monkeypatch, breaks):
    fragment = walk(client, root(client), "planned")
    before = (view(client)["digest"], state(client)["revision"], len(stored(client, fragment["id"])))
    if breaks == "graph":
        def boom(*args, **kwargs):
            raise OSError("disk")
        monkeypatch.setattr(client.app_state.service, "save_graph", boom)
    else:
        def refuse(*args, **kwargs):
            raise ValueError("Schránka zadání: revize se nepodařila.")
        monkeypatch.setattr(brief_vault_placement.gates, "gate", refuse)
    response = client.post("/api/brief-vault", headers=HEADERS, json={
        **SCOPE, "op": "gate", "fragmentId": fragment["id"], "expectedRevision": fragment["revision"], "gate": "placed",
        "value": True, "note": "vložit"})
    assert response.status_code == (503 if breaks == "graph" else 409)
    monkeypatch.undo()
    assert (view(client)["digest"], state(client)["revision"], len(stored(client, fragment["id"]))) == before
    assert kinds(client)["area"] == [] and gate(client, fragment, "placed")["gates"]["placed"] is True


def test_changed_canvas_or_brief_is_409_without_side_effects(client):
    parent, (first, second) = split_root(client)
    parent = walk(client, parent, "planned")
    gate(client, first, "scoped")  # zápis brány dítěte (nová revize, stejný otisk) plán nezneplatní
    revised = post(client, op="revise", fragmentId=second["id"], expectedRevision=1, text="jiné", note="změna")
    count = len(stored(client, parent["id"]))
    conflict = gate(client, parent, "placed", expect=409)["error"]
    assert "plán se změnil, znovu planned" in conflict and second["id"] in conflict
    post(client, op="revise", fragmentId=second["id"], expectedRevision=revised["fragment"]["revision"],
         text="3.2 Obrazovka\nseznam.", note="zpět")  # stejný otisk vstupů = plán zase platí
    graph = view(client)["graph"]
    install_graph(client, {"nodes": [*graph["nodes"], node("c2", "s1")], "edges": graph["edges"]})
    assert "plátno" in gate(client, parent, "placed", expect=409)["error"]
    assert len(stored(client, parent["id"])) == count and kinds(client)["area"] == []
    post(client, op="revise", fragmentId=parent["id"], expectedRevision=parent["revision"], title="3. VRSTVA v2",
         note="nový název")
    latest = {"id": parent["id"], "revision": parent["revision"] + 1}
    assert "zadání fragmentu" in gate(client, latest, "placed", expect=409)["error"]


def test_double_placed_off_keeps_cards_and_reinsert_needs_new_planned(client):
    fragment = walk(client, root(client), "placed")
    gate(client, fragment, "placed", expect=409)
    off = gate(client, fragment, "placed", value=False)["fragment"]
    assert len(kinds(client)["node"]) == 2  # c1 + vložená karta zůstává
    assert "nové planned" in gate(client, off, "placed", expect=409)["error"]
    off = gate(client, off, "planned", value=False)["fragment"]
    again = gate(client, gate(client, off, "planned")["fragment"], "placed")
    # Fragment už kartu má: znovu vložení ji aktualizuje (extend), nezakládá druhou (K11).
    assert again["gates"]["placed"] is True and again["placement"]["refs"] == {}
    assert len(kinds(client)["area"]) == 1 and len(kinds(client)["sector"]) == 2 and len(kinds(client)["node"]) == 2


def test_canvas_plan_validates_brief_marks(client):
    def apply(plan_nodes):
        return client.post("/api/canvas-plan", headers=HEADERS, json={**SCOPE, "digest": view(client)["digest"],
                                                                      "plan": {"nodes": plan_nodes}})
    area = {"ref": "a", "kind": "area", "parent": "@s1", "name": "Logika", "size": {"w": 600, "h": 400}}
    assert apply([{"ref": "n", "kind": "node", "name": "N", "briefGroup": "logika"}]).status_code == 409
    assert apply([{**area, "briefGroup": "design"}]).status_code == 409
    assert apply([{**area, "briefGroup": "logika"}, {**area, "ref": "b", "briefGroup": "logika"}]).status_code == 409
    assert apply([{**area, "briefGroup": "logika"}]).status_code == 200
    assert "briefGroup=logika" in apply([{**area, "briefGroup": "logika"}]).json()["error"]
    assert apply([{**area, "parent": None, "briefGroup": "logika"}]).status_code == 200  # jiný kontejner
    # Existující duplicita (oblast přesunutá člověkem do téhož kontejneru) plán odmítne s výčtem.
    marked = state(client)["state"]["nodes"]
    duplicate = next(item["id"] for item in kinds(client)["area"] if item["parentId"] is None)
    graph = view(client)["graph"]
    moved = [{**item, "parentId": "s1"} if item["id"] == duplicate else item for item in graph["nodes"]]
    install_graph(client, {"nodes": moved, "edges": graph["edges"]})
    assert marked[duplicate]["briefGroup"] == "logika"
    fragment = walk(client, root(client), "synthesized")
    assert "víc uzlů" in plan(client, [fragment["id"]], expect=409)["error"]


def test_second_placed_of_the_same_discipline_reuses_area_and_sector(client):
    first = gate(client, walk(client, root(client), "planned"), "placed")["placement"]["refs"]
    other = post(client, op="create", scopeNodeId="s1", discipline="be", title="Export", text="Exportuj CSV.")["fragment"]
    other = walk(client, other, "planned")
    plan_nodes = stored(client, other["id"])[-1][2]["planned"]["payload"]["plan"]["nodes"]
    assert [(item["kind"], item["parent"]) for item in plan_nodes] == [("node", "@" + first["s1"])]
    second = gate(client, other, "placed")["placement"]["refs"]
    assert set(second) == {"f1"} and len(kinds(client)["area"]) == 1 and len(kinds(client)["sector"]) == 2


def versions(client):
    response = client.get("/api/canvas-versions", params=SCOPE)
    assert response.status_code == 200, response.text
    return response.json()["versions"]


def placed(client, fragment):
    return client.post("/api/brief-vault", headers=HEADERS, json={
        **SCOPE, "op": "gate", "fragmentId": fragment["id"], "expectedRevision": fragment["revision"], "gate": "placed",
        "value": True, "note": "vložit"})


def test_placed_saves_canvas_version_before_writing(client):
    fragment = walk(client, root(client), "planned")
    before_graph = view(client)["graph"]
    assert versions(client) == []
    assert placed(client, fragment).status_code == 200
    [saved] = versions(client)
    assert saved["author"] == "před placed Import" and saved["coverage"] == "full"
    stored_graph = client.get("/api/canvas-versions", params={**SCOPE, "versionId": saved["id"]}).json()["graph"]
    assert stored_graph == before_graph  # verze je stav před vložením, karty plánu v ní nejsou
    assert kinds(client)["area"] != []


def test_placed_without_canvas_change_reuses_existing_version(client):
    fragment = walk(client, root(client), "planned")
    manual = client.post("/api/canvas-versions", headers=HEADERS,
                         json={**SCOPE, "digest": view(client)["digest"], "author": "Martin"})
    assert manual.status_code == 200, manual.text
    assert placed(client, fragment).status_code == 200
    assert [item["author"] for item in versions(client)] == ["Martin"]  # stejný obsah už uložený, jde se k němu vrátit


@pytest.mark.parametrize("error, status", [(ValueError("Main je pouze pro čtení."), 409), (OSError("disk"), 503)])
def test_failed_version_save_blocks_placed(client, monkeypatch, error, status):
    fragment = walk(client, root(client), "planned")
    before = (view(client)["digest"], state(client)["revision"], len(stored(client, fragment["id"])))

    def broken(*args, **kwargs):
        raise error

    monkeypatch.setattr(brief_vault_placement.CanvasVersions, "checkpoint", broken)
    assert placed(client, fragment).status_code == status
    monkeypatch.undo()
    assert (view(client)["digest"], state(client)["revision"], len(stored(client, fragment["id"]))) == before
    assert kinds(client)["area"] == [] and versions(client) == []


def test_second_round_placed_updates_the_same_card(client):
    """K11: dvě kola `placed` = jedna karta; spec, bloky i fragmentRef z nového kola, otisk plánu nese update."""
    fragment = walk(client, root(client), "placed")
    [card_id] = [item["id"] for item in kinds(client)["node"] if item["id"] != "c1"]
    first_ref = state(client)["state"]["nodes"][card_id]["fragmentRefs"][0]
    fragment = gate(client, fragment, "verified", payload={"actual": {"tests": "fail", "criticRounds": 2,
                                                                     "unexpected": False}})["fragment"]
    fragment = gate(client, fragment, "synthesized", value=False)["fragment"]
    research = post(client, op="research", fragmentId=fragment["id"], title="Doklady z repa", text="")["fragment"]
    post(client, op="research-update", fragmentId=research["id"], expectedRevision=1, note="cesty k souborům",
         approach="1. Uprav backend/import.py\n2. Doplň test_import.py", status="done")
    done = "Import odmítne vadný řádek. Test to ověří."
    synth = {"type": "SCHEMA", "done": done, "prediction": {"tests": "pass", "criticRounds": 1, "risk": "kódování"}}
    fragment = gate(client, fragment, "synthesized", payload=synth)["fragment"]
    fragment = gate(client, fragment, "decided", payload={"verdict": "yes", "reason": "Řeší výtku kritika."})["fragment"]
    fragment = gate(client, fragment, "planned")["fragment"]
    stored_plan = stored(client, fragment["id"])[-1][2]["planned"]["payload"]
    assert stored_plan["plan"]["nodes"] == [] and stored_plan["plan"]["extend"][0]["node"] == "@" + card_id
    assert stored_plan["hash"] == plan_hash(stored_plan["plan"]) and "Bloky nahradí u 1" in stored_plan["summary"]
    again = gate(client, fragment, "placed")
    assert again["placement"]["refs"] == {} and [item["id"] for item in kinds(client)["node"]] == ["c1", card_id]
    current = state(client)["state"]["nodes"][card_id]
    assert [block["title"] for block in current["blocks"]][:2] == ["Uprav backend/import.py", "Doplň test_import.py"]
    assert current["blocks"][1]["state"]["condition"] == done and len(current["blocks"]) == 6
    assert [block["number"] for block in current["blocks"]] == [str(n) for n in range(1, 7)]
    ref = current["fragmentRefs"][0]
    assert ref["fragmentId"] == fragment["id"] and ref["revision"] > first_ref["revision"] and len(current["fragmentRefs"]) == 1
    spec = client.get("/api/node-spec", params={**SCOPE, "node": card_id})
    assert spec.status_code == 200, spec.text
    assert spec.json()["fields"]["goal"] == done and spec.json()["fields"]["acceptance"] == "SCHEMA: " + done
