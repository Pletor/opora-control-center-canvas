"""Plán struktury Schránky bez databáze (docs/schranka-neurony.md §4, §9 body 1, 2 a 7): oblast → sektor → karty,
značky `briefGroup`/`briefDiscipline`, tvar karty převzatý z dřívějšího `vault-plan.ts` (název, vrstva, bloky 36 + 4,
`fragmentRef`), `spec` ze `synthesized`, vazby `next`, normalizace výběru, 409 s výčtem, strop dávky a otisk."""
import pytest

from backend.editor.brief_vault.brief_vault_gate_rules import encode_gates, input_hash
from backend.editor.brief_vault.brief_vault_model import Blocked
from backend.editor.brief_vault.brief_vault_plan import (
    MAX_PLAN_NODES,
    area_size,
    build_plan,
    plan_hash,
)
from backend.editor.brief_vault.brief_vault_plan_cards import LOGIC_BLOCKS

SYNTH = {"type": "SCHEMA", "done": "Tabulka existuje a test projde.",
         "prediction": {"tests": "pass", "criticRounds": 1, "risk": "migrace"}}
GRAPH = {"nodes": [{"id": "s1", "kind": "sector", "parentId": None}, {"id": "c1", "kind": "node", "parentId": "s1"}],
         "edges": []}
EMPTY = {"nodes": {}}


class Vault:
    """Syntetické poslední revize fragmentů; `synth` zapne platné brány do synthesized pro platnou disciplínu."""

    def __init__(self):
        self.rows = {}

    def add(self, fid, title, parent=None, discipline=None, scope="s1", ord=1, synth=False, kind="brief", deleted=0):
        effective = discipline if discipline or parent is None else self.effective(parent)
        row = {"fragment_id": fid, "revision": 1, "parent_id": parent, "scope_node_id": None if parent else scope,
               "ord": ord, "kind": kind, "title": title, "text": f"text {title}", "deleted": deleted,
               "discipline": discipline, "gates": None}
        if synth:
            digest = input_hash(row["title"], row["text"], effective)
            entries = {name: {"value": True, "payload": SYNTH if name == "synthesized" else None, "by": "t", "actor": "agent",
                              "at": "T", "inputHash": digest, "revision": 1} for name in ("scoped", "weighed", "synthesized")}
            row["gates"] = encode_gates(entries)
        self.rows[fid] = row
        return row

    def effective(self, fid):
        while fid is not None:
            if self.rows[fid]["discipline"]:
                return self.rows[fid]["discipline"]
            fid = self.rows[fid]["parent_id"]
        return None

    def plan(self, ids, graph=GRAPH, state=EMPTY, texts=None):
        return build_plan(self.rows, graph, state, texts or {}, ids)


def chunks():
    vault = Vault()
    vault.add("r", "3. VRSTVA", discipline="be", synth=True)
    vault.add("a", "3.12 Chunks", parent="r", ord=1)
    vault.add("a1", "3.12.1 Chunk id", parent="a", ord=1)
    vault.add("a2", "3.12.2 Overlap", parent="a", ord=2)
    vault.add("q", "Ověřit", parent="a", ord=3, kind="research")
    vault.add("b", "3.15 Metadata", parent="r", ord=2)
    return vault


def by_ref(plan):
    return {node["ref"]: node for node in plan["nodes"]}


def test_area_sector_and_one_card_per_direct_child():
    built = chunks().plan(["r"], texts={"a": 3})
    nodes = by_ref(built["plan"])
    assert [node["ref"] for node in built["plan"]["nodes"]] == ["a1", "s1", "f1", "f2"]
    assert nodes["a1"] == {"ref": "a1", "kind": "area", "parent": "@s1", "name": "Logika", "size": area_size("logika"),
                           "briefGroup": "logika"}
    assert nodes["s1"] == {"ref": "s1", "kind": "sector", "parent": "a1", "name": "Backend", "briefDiscipline": "be"}
    card = nodes["f1"]
    assert card["kind"] == "node" and card["parent"] == "s1" and card["name"] == "[task] 3.12 Chunks"
    assert card["card"] == {"status": "draft", "layer": "backend"}
    assert card["fragmentRef"] == [{"fragmentId": "a"}, {"fragmentId": "a1"}, {"fragmentId": "a2"}]
    assert [block["title"] for block in card["blocks"]] == ["3.12.1 Chunk id", "3.12.2 Overlap",
                                                           *(block["title"] for block in LOGIC_BLOCKS)]
    assert card["purpose"] == "Zadání ze schránky: 3. VRSTVA › 3.12 Chunks"
    # Text zadání se nekopíruje: karta říká, kde ho agent najde a ze které revize textu vznikla.
    assert "r3" in card["text"] and "node-brief" in card["text"] and "2 podfragmentů" in card["text"]
    assert card["spec"] == {"goal": SYNTH["done"], "acceptance": "SCHEMA: " + SYNTH["done"]}
    assert built["plan"]["edges"] == [{"from": "f1", "to": "f2", "port": "next"}]
    assert built["scopes"] == ["s1"] and set(built["sourceRevisions"]) == {"r", "a", "a1", "a2", "b"}


def test_leaf_is_one_card_and_layers_follow_the_discipline():
    vault = Vault()
    vault.add("x", "Obrazovka košíku", discipline="ux", synth=True)
    vault.add("o", "Provoz", discipline="devops", synth=True, ord=2)
    built = vault.plan(["x", "o"])
    cards = [node for node in built["plan"]["nodes"] if node["kind"] == "node"]
    assert [card["card"] for card in cards] == [{"status": "draft", "layer": "frontend"}, {"status": "draft"}]
    assert [card["blocks"] for card in cards] == [[], []]  # list bez podfragmentů, disciplíny bez závěrečných bloků
    areas = [node["briefGroup"] for node in built["plan"]["nodes"] if node["kind"] == "area"]
    assert areas == ["kresleni", "provoz"] and built["plan"]["edges"] == []


def test_logic_card_has_at_most_36_sub_blocks_plus_four_closing_ones():
    vault = Vault()
    vault.add("r", "Výpočet ceny", discipline="be", synth=True)
    vault.add("k", "Pravidla", parent="r")
    for index in range(50):
        vault.add(f"p{index}", f"Pravidlo {index}", parent="k", ord=index)
    card = by_ref(vault.plan(["r"])["plan"])["f1"]
    assert len(card["blocks"]) == 40 and all(block["title"].startswith("Pravidlo") for block in card["blocks"][:36])
    assert [[block["ref"], block["title"], block["condition"]] for block in card["blocks"][36:]] == [
        ["b37", "Funkce a metody", "Podpisy a odpovědnost každé funkce jsou zapsané."],
        ["b38", "Spolupráce", "Tok dat mezi funkcemi je popsaný."],
        ["b39", "Test částí", "Testy jednotlivých částí prošly."],
        ["b40", "Komponenta", "Komponenta funguje jako celek a test celku prošel."]]
    assert card["blocks"][39]["ports"] == [{"ref": "frontend", "label": "Komponenta hotová → frontend"}]
    assert not any("ports" in block for block in card["blocks"][:39]) and len(card["fragmentRef"]) == 50
    vault.add("r", "Výpočet ceny", discipline="ux", synth=True)  # bez závěrečných bloků zůstane 40 podfragmentů
    assert [block["title"] for block in by_ref(vault.plan(["r"])["plan"])["f1"]["blocks"]][-1] == "Pravidlo 39"


def test_child_with_other_discipline_goes_to_its_own_sector():
    vault = chunks()
    vault.rows["b"]["discipline"] = "ux"
    built = vault.plan(["r"])
    nodes = by_ref(built["plan"])
    assert [(node["ref"], node.get("briefGroup") or node.get("briefDiscipline")) for node in built["plan"]["nodes"]
            if node["kind"] != "node"] == [("a1", "logika"), ("s1", "be"), ("a2", "kresleni"), ("s2", "ux")]
    assert nodes["f1"]["parent"] == "s1" and nodes["f2"]["parent"] == "s2" and nodes["f2"]["card"]["layer"] == "frontend"


def test_existing_marks_are_reused_by_state_not_by_name():
    area = {"kind": "area", "parentId": "s1", "x": 0, "y": 0, "size": {"w": 2000, "h": 1000}}
    graph = {"nodes": [*GRAPH["nodes"], {"id": "A", **area}, {"id": "B", **area, "x": 3000},
                       {"id": "S", "kind": "sector", "parentId": "s1", "x": 100, "y": 100}], "edges": []}
    vault = chunks()
    state = {"nodes": {"A": {"briefGroup": "logika"}}}
    nodes = vault.plan(["r"], graph, state)["plan"]["nodes"]
    assert nodes[0] == {**nodes[0], "kind": "sector", "parent": "@A"}  # oblast podle značky, nový sektor uvnitř
    state = {"nodes": {"A": {"briefGroup": "logika"}, "S": {"briefDiscipline": "be"}}}
    nodes = vault.plan(["r"], graph, state)["plan"]["nodes"]
    assert [node["parent"] for node in nodes] == ["@S", "@S"]  # sektor v oblasti znovu použitý
    # Označený sektor mimo oblast své skupiny (jiná oblast, nebo oblast chybí) = 409, ne druhý sektor.
    for marks in ({"B": {"briefGroup": "logika"}, "S": {"briefDiscipline": "be"}}, {"S": {"briefDiscipline": "be"}}):
        with pytest.raises(ValueError, match="mimo oblast skupiny Logika"):
            vault.plan(["r"], graph, {"nodes": marks})
    with pytest.raises(ValueError, match="briefGroup=logika"):
        vault.plan(["r"], graph, {"nodes": {"A": {"briefGroup": "logika"}, "B": {"briefGroup": "logika"}}})


def test_selection_is_normalized_and_ordered_by_tree():
    vault = chunks()
    vault.add("z", "Druhé zadání", discipline="db", synth=True, ord=2)
    first = vault.plan(["z", "a1", "r"])
    assert first == vault.plan(["r", "z"])
    names = [node["name"] for node in first["plan"]["nodes"] if node["kind"] == "node"]
    assert names == ["[task] 3.12 Chunks", "[task] 3.15 Metadata", "[task] Druhé zadání"]
    with pytest.raises(ValueError, match="fragmentIds"):
        vault.plan([])
    with pytest.raises(Blocked, match="živé fragmenty druhu brief") as raised:
        vault.plan(["q"])
    assert raised.value.fragments[0]["id"] == "q" and raised.value.fragments[0]["reason"] == "not-live"


def test_missing_discipline_or_synthesized_is_409_with_list():
    vault = chunks()
    vault.add("n", "Staré zadání", synth=False, ord=3)  # kořen bez disciplíny (data z doby před stopami)
    with pytest.raises(Blocked, match="nezařazené fragmenty: „Staré zadání“ \\(n\\)") as raised:
        vault.plan(["r", "n"])
    assert raised.value.fragments == [{"id": "n", "title": "Staré zadání", "reason": "no-discipline"}]
    vault.add("m", "Bez mikrokroku", discipline="be", ord=4)
    with pytest.raises(Blocked, match="chybí platná brána synthesized .*„Bez mikrokroku“ \\(m\\)") as raised:
        vault.plan(["r", "m"])
    assert raised.value.fragments == [{"id": "m", "title": "Bez mikrokroku", "reason": "no-synthesized"}]
    with pytest.raises(Blocked, match="nezařazené") as raised:  # text jmenuje první důvod, pole nese všechny
        vault.plan(["n", "m"])
    assert [(item["id"], item["reason"]) for item in raised.value.fragments] == [("n", "no-discipline"),
                                                                                  ("m", "no-synthesized")]
    vault.rows["r"]["text"] = "změněný text"  # zneplatněná synthesized se počítá jako chybějící
    with pytest.raises(ValueError, match="„3. VRSTVA“"):
        vault.plan(["r"])


def test_scope_layer_card_and_canvas():
    vault = Vault()
    vault.add("c", "Na kartě", discipline="be", synth=True, scope="c1")
    vault.add("p", "Na plátně", discipline="be", synth=True, scope="", ord=2)
    built = vault.plan(["c", "p"])
    areas = [node for node in built["plan"]["nodes"] if node["kind"] == "area"]
    assert [area["parent"] for area in areas] == [None, "@s1"] and built["scopes"] == ["", "s1"]  # plátno, vedle karty
    vault.add("x", "Ztracená", discipline="be", synth=True, scope="pryc", ord=3)
    with pytest.raises(ValueError, match="na plátně už není"):
        vault.plan(["x"])


def test_batch_cap_reports_skipped_cards_and_hash_is_stable():
    vault = Vault()
    vault.add("r", "Vrstva", discipline="ux", synth=True)
    for index in range(MAX_PLAN_NODES + 5):
        vault.add(f"k{index}", f"k{index}", parent="r", ord=index)
    built = vault.plan(["r"])
    assert len(built["plan"]["nodes"]) == MAX_PLAN_NODES and built["skipped"] == 7  # oblast + sektor + 198 karet
    assert len(built["plan"]["edges"]) == MAX_PLAN_NODES - 3
    again = vault.plan(["r"])
    assert plan_hash(built["plan"]) == plan_hash(again["plan"]) and len(plan_hash(built["plan"])) == 64
    texts = {fid: 1 for fid in vault.rows}  # poslední změna textu (text_revisions) zůstává r1
    vault.rows["k0"]["revision"] = 7  # revize jen s branami (bez změny textu) otisk nemění
    assert plan_hash(vault.plan(["r"], texts=texts)["plan"]) == plan_hash(built["plan"])
    vault.rows["k0"]["title"] = "jiný"
    assert plan_hash(vault.plan(["r"])["plan"]) != plan_hash(built["plan"])
