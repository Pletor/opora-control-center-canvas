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
from backend.editor.brief_vault.brief_vault_plan_cards import (
    LOGIC_BLOCKS,
    MAX_STEPS,
    approach_steps,
    first_sentence,
)

SYNTH = {"type": "SCHEMA", "done": "Tabulka existuje a test projde.",
         "prediction": {"tests": "pass", "criticRounds": 1, "risk": "migrace"}}
GRAPH = {"nodes": [{"id": "s1", "kind": "sector", "parentId": None}, {"id": "c1", "kind": "node", "parentId": "s1"}],
         "edges": []}
EMPTY = {"nodes": {}}


class Vault:
    """Syntetické poslední revize fragmentů; `synth` zapne platné brány do synthesized pro platnou disciplínu."""

    def __init__(self):
        self.rows = {}

    def add(self, fid, title, parent=None, discipline=None, scope="s1", ord=1, synth=False, kind="brief", deleted=0,
            payload=None):
        effective = discipline if discipline or parent is None else self.effective(parent)
        row = {"fragment_id": fid, "revision": 1, "parent_id": parent, "scope_node_id": None if parent else scope,
               "ord": ord, "kind": kind, "title": title, "text": f"text {title}", "deleted": deleted,
               "discipline": discipline, "gates": None}
        if synth:
            digest = input_hash(row["title"], row["text"], effective)
            entries = {name: {"value": True, "payload": (payload or SYNTH) if name == "synthesized" else None, "by": "t", "actor": "agent",
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

    def plan(self, ids, graph=GRAPH, state=EMPTY, texts=None, details=None, revision=0, spec_revision=None):
        return build_plan(self.rows, graph, state, texts or {}, ids, details, revision, spec_revision)


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
    assert card["kind"] == "node" and card["parent"] == "s1" and card["name"] == "[task] 3.12 Chunks: " + SYNTH["done"]
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
    assert names == [f"[task] {title}: {SYNTH['done']}" for title in ("3.12 Chunks", "3.15 Metadata", "Druhé zadání")]
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


def test_approach_steps_and_first_sentence():
    approach = "Úvod k postupu.\n1. Přidej tabulku\n   s indexem.\n2) Napiš migraci\n- Otestuj návrat\n\n* Zapiš doklad"
    assert approach_steps(approach) == ["Přidej tabulku s indexem.", "Napiš migraci", "Otestuj návrat", "Zapiš doklad"]
    assert approach_steps("Bez seznamu\n\n druhý řádek ") == ["Bez seznamu", "druhý řádek"]
    assert approach_steps("\n".join(f"{n}. krok {n}" for n in range(1, 60)))[-1] == f"krok {MAX_STEPS}"
    assert first_sentence("Tabulka existuje. Test projde.") == "Tabulka existuje."
    assert first_sentence("v1.2 vznikne? Ano.") == "v1.2 vznikne?"
    long = first_sentence("slovo " * 40)
    assert len(long) == 80 and long.endswith("…")


def research_vault(status="done"):
    vault = Vault()
    vault.add("x", "Uložení košíku", discipline="be", synth=True)
    vault.add("r1", "Starší výzkum", parent="x", ord=1, kind="research")
    vault.add("r2", "Doklady z repa", parent="x", ord=2, kind="research")
    vault.add("r3", "Rozpracovaný", parent="x", ord=3, kind="research")
    details = {"r1": {"research": {"status": "done", "approach": "1. starý krok"}},
               "r2": {"research": {"status": status, "approach": "Postup:\n1. Přidej tabulku carts\n2. Napiš endpoint"}},
               "r3": {"research": {"status": "running", "approach": "1. nehotové"}}}
    return vault, details


def test_leaf_card_blocks_come_from_last_done_research_approach():
    vault, details = research_vault()
    card = by_ref(vault.plan(["x"], details=details)["plan"])["f1"]
    assert card["name"] == "[task] Uložení košíku: Tabulka existuje a test projde."
    assert [(block["title"], block["condition"]) for block in card["blocks"][:2]] == [
        ("Přidej tabulku carts", "Krok proveden: Přidej tabulku carts"), ("Napiš endpoint", SYNTH["done"])]
    assert [block["title"] for block in card["blocks"][2:]] == [block["title"] for block in LOGIC_BLOCKS]
    assert [block["ref"] for block in card["blocks"]] == [f"b{n}" for n in range(1, 7)]
    vault, details = research_vault(status="running")  # poslední hotový je pak r1
    assert by_ref(vault.plan(["x"], details=details)["plan"])["f1"]["blocks"][0]["title"] == "starý krok"
    assert len(by_ref(vault.plan(["x"])["plan"])["f1"]["blocks"]) == 4  # bez výzkumu jen závěrečné bloky


def card_graph(*cards):
    return {"nodes": [*GRAPH["nodes"], {"id": "s2", "kind": "sector", "parentId": None},
                      *({"id": node_id, "kind": "node", "parentId": parent} for node_id, parent in cards)], "edges": []}


def refs_state(refs, closed=()):
    return {"nodes": {node_id: {"fragmentRefs": [{"fragmentId": fid, "revision": 1}],
                                **({"done": {"confirmed": True}} if node_id in closed else {})}
                      for node_id, fid in refs.items()}}


def test_card_the_fragment_already_has_is_updated_not_duplicated():
    vault, details = research_vault()
    graph, state = card_graph(("K", "s1")), refs_state({"K": "x"})
    built = vault.plan(["x"], graph, state, details=details, revision=5, spec_revision=lambda node_id: {"K": 2}[node_id])
    fresh = by_ref(vault.plan(["x"], details=details)["plan"])["f1"]
    assert built["plan"]["nodes"] == [] and built["plan"]["edges"] == []
    assert built["plan"]["extend"] == [{"node": "@K", "expectedRevision": 5,
                                        "spec": {"expectedRevision": 2, "fields": fresh["spec"]},
                                        "fragmentRef": fresh["fragmentRef"], "blocks": fresh["blocks"],
                                        "replaceBlocks": True}]
    # Revize celého stavu do otisku nevstupuje (mění ji i souběžné smyčky, K12); stav karty ano přes scopeDigest.
    later = vault.plan(["x"], graph, state, details=details, revision=6, spec_revision=lambda node_id: 2)
    assert plan_hash(built["plan"]) == plan_hash(later["plan"]) and built["scopeDigest"] == later["scopeDigest"]
    touched = {"nodes": {"K": {**state["nodes"]["K"], "phase": "define"}, "c1": {"phase": "build"}}}
    assert vault.plan(["x"], graph, touched, details=details)["scopeDigest"] != built["scopeDigest"]
    elsewhere = {"nodes": {**state["nodes"], "c1": {"phase": "build"}}}
    assert vault.plan(["x"], graph, elsewhere, details=details)["scopeDigest"] == built["scopeDigest"]
    # Karta jiné vrstvy (mimo s1) ani karta, kde fragment není prvním odkazem, se neaktualizuje.
    assert by_ref(vault.plan(["x"], card_graph(("K", "s2")), state)["plan"])["f1"]["kind"] == "node"
    other = {"nodes": {"K": {"fragmentRefs": [{"fragmentId": "r", "revision": 1}, {"fragmentId": "x", "revision": 1}]}}}
    assert "extend" not in vault.plan(["x"], graph, other)["plan"]
    with pytest.raises(Blocked, match="víc karet") as raised:
        vault.plan(["x"], card_graph(("K", "s1"), ("L", "s1")), refs_state({"K": "x", "L": "x"}))
    assert raised.value.fragments[0]["reason"] == "duplicate-card"
    with pytest.raises(Blocked, match="uzavřená") as raised:
        vault.plan(["x"], graph, refs_state({"K": "x"}, closed={"K"}))
    assert raised.value.fragments[0]["reason"] == "card-closed"


def test_synthesized_layer_travels_to_the_existing_card_only_when_present():
    vault, details = research_vault()
    graph, state = card_graph(("K", "s1")), refs_state({"K": "x"})
    plain = vault.plan(["x"], graph, state, details=details)["plan"]["extend"][0]
    assert "layer" not in plain  # bez layer ve synthesized se vrstva karty nemění
    vault.add("x", "Uložení košíku", discipline="be", synth=True, payload={**SYNTH, "layer": "backend"})
    assert vault.plan(["x"], graph, state, details=details)["plan"]["extend"][0]["layer"] == "backend"


CHECKS = [{"id": "unit", "command": "uv run pytest backend/cart -q"}, {"id": "build", "command": "npm run build"}]


def test_synthesized_checks_make_a_goal_card_only_for_the_lead_and_not_through_extend():
    """Nová karta za fragment dostane checks + GOAL (docs/schranka-bunka.md §3 bod 2), extend existující karty ne.

    Proč extend ne: `checks` a `goal_mode` jsou chráněná pole (backend/canvas/protected_fields.py) a `apply_plan` je
    agentovi u existující karty odmítne (403) už v dryRun brány planned, takže by se smyčka zastavila. Nejde o ztrátu:
    karta nese kontroly z kola 1 a `synthesized` dalších kol je musí nést beze změny (kontroly jsou měřítko napříč
    koly, `brief_vault_cell.same_checks`; změnu dělá člověk)."""
    vault, details = research_vault()
    plain = by_ref(vault.plan(["x"], details=details)["plan"])["f1"]
    assert "checks" not in plain and "goal_mode" not in plain  # bez checks beze změny
    vault.add("x", "Uložení košíku", discipline="be", synth=True, payload={**SYNTH, "checks": CHECKS})
    card = by_ref(vault.plan(["x"], details=details)["plan"])["f1"]
    assert card["checks"] == CHECKS and card["checks"] is not CHECKS and card["goal_mode"] == "until_checks_pass"
    # Karty za děti F kontroly nedědí (patří mikrokroku F).
    parent = chunks()
    parent.add("r", "3. VRSTVA", discipline="be", synth=True, payload={**SYNTH, "checks": CHECKS})
    assert not any("checks" in node for node in parent.plan(["r"])["plan"]["nodes"])
    # Existující karta se stejnými kontrolami: chráněná pole, extend je nepřenáší (viz docstring).
    graph = card_graph(("K", "s1"))
    graph["nodes"][-1].update(checks=CHECKS, goal_mode="until_checks_pass")
    extend = vault.plan(["x"], graph, refs_state({"K": "x"}), details=details)["plan"]["extend"][0]
    assert "checks" not in extend and "goal_mode" not in extend
    # Existující karta s jinými (zde žádnými) kontrolami = 409 checks-mismatch (fail-closed, upraví člověk).
    with pytest.raises(Blocked, match="jiné kontroly než synthesized") as raised:
        vault.plan(["x"], card_graph(("K", "s1")), refs_state({"K": "x"}), details=details)
    assert raised.value.fragments[0]["reason"] == "checks-mismatch"


def test_siblings_link_only_when_one_card_is_new():
    vault = chunks()
    graph, state = card_graph(("K", "s1")), refs_state({"K": "a"})
    built = vault.plan(["r"], graph, state)
    assert [item["node"] for item in built["plan"]["extend"]] == ["@K"]
    assert built["plan"]["edges"] == [{"from": "@K", "to": "f1", "port": "next"}]
    both = vault.plan(["r"], card_graph(("K", "s1"), ("L", "s1")), refs_state({"K": "a", "L": "b"}))
    assert both["plan"]["edges"] == [] and both["plan"]["nodes"] == []


def test_synthesized_steps_come_first_and_layer_overrides_discipline():
    """K12: bloky karty F podle kroků mikrokroku (ne podle širokého approach výzkumu), poslední krok = done."""
    steps = ["Přidej sloupec cart_id", "Doplň test migrace"]
    vault, details = research_vault()
    vault.add("x", "Uložení košíku", discipline="be", synth=True, payload={**SYNTH, "steps": steps, "layer": "database"})
    card = by_ref(vault.plan(["x"], details=details)["plan"])["f1"]
    assert [(block["title"], block["condition"]) for block in card["blocks"][:2]] == [
        (steps[0], "Krok proveden: " + steps[0]), (steps[1], SYNTH["done"])]
    assert len(card["blocks"]) == 2 + len(LOGIC_BLOCKS) and card["card"]["layer"] == "database"
    # Karty za děti F kroky F nedostanou: bloky z vlastních podfragmentů (b), jinak z výzkumu (c).
    vault = chunks()
    vault.add("r", "3. VRSTVA", discipline="be", synth=True, payload={**SYNTH, "steps": steps})
    built = by_ref(vault.plan(["r"])["plan"])
    assert [block["title"] for block in built["f1"]["blocks"][:2]] == ["3.12.1 Chunk id", "3.12.2 Overlap"]
    assert built["f1"]["card"]["layer"] == "backend"


def test_step_condition_from_object_and_done_is_never_cut_mid_word():
    """K14: `{text, condition}` nese vlastní podmínku bloku; poslední blok nese celé `done` (≤500), ne oříznuté."""
    done = " ".join(["Dlouhé kritérium hotovo"] * 22)[:500]
    steps = [{"text": "Přidej sloupec", "condition": "Sloupec existuje v migraci."}, "Prostý krok",
             {"text": "Poslední", "condition": "Vlastní podmínka posledního."}]
    vault, details = research_vault()
    vault.add("x", "Uložení košíku", discipline="be", synth=True, payload={**SYNTH, "done": done, "steps": steps})
    blocks = by_ref(vault.plan(["x"], details=details)["plan"])["f1"]["blocks"]
    assert [block["condition"] for block in blocks[:3]] == [
        "Sloupec existuje v migraci.", "Krok proveden: Prostý krok", "Vlastní podmínka posledního."]
    vault.add("x", "Uložení košíku", discipline="be", synth=True, payload={**SYNTH, "done": done, "steps": ["a", "b"]})
    assert by_ref(vault.plan(["x"], details=details)["plan"])["f1"]["blocks"][1]["condition"] == done


def test_clip_words_cuts_on_word_boundary_with_ellipsis():
    from backend.editor.brief_vault.brief_vault_plan_cards import clip_words
    assert clip_words("krátké", 10) == "krátké"
    cut = clip_words("alpha beta gamma", 12)
    assert cut == "alpha beta…" and len(cut) <= 12
    assert clip_words("nesdělitelnéslovo dál", 8).endswith("…")


def test_non_goals_go_to_spec_and_travel_through_extend():
    vault, details = research_vault()
    graph, state = card_graph(("K", "s1")), refs_state({"K": "x"})
    assert "non_goals" not in by_ref(vault.plan(["x"], details=details)["plan"])["f1"]["spec"]
    vault.add("x", "Uložení košíku", discipline="be", synth=True, payload={**SYNTH, "nonGoals": ["Bez UI", "Bez migrace dat"]})
    assert by_ref(vault.plan(["x"], details=details)["plan"])["f1"]["spec"]["non_goals"] == "- Bez UI\n- Bez migrace dat"
    extend = vault.plan(["x"], graph, state, details=details)["plan"]["extend"][0]
    assert extend["spec"]["fields"]["non_goals"] == "- Bez UI\n- Bez migrace dat"
