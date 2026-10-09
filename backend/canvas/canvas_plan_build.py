"""Sestavení dávky plánu (`docs/davka-planu.md` §3) v paměti; nic neukládá.

Přeloží lokální `ref` na nová UUID a z dávky udělá nové uzly a vazby grafu, doplněk stavu
Desktop v3 (bloky s porty a podmínkou, pravidla se scope node, rozhodnutí, `agentRole`), spec
a text nových karet. Tvar a limity hlídají až stávající validátory (graf, stav, spec, text);
tady se kontroluje jen to, co jednotlivé cesty poznat nemohou: neznámý `ref`, pole navíc
a blok s portem zdroje vazby `block`.
"""

import copy

from backend.canvas.canvas_plan_extend import extend_cards
from backend.canvas.canvas_plan_fields import fail, fields, items_of, new_id, plan_ref, position_of
from backend.canvas.canvas_plan_links import blocks_of, edge_of
from backend.canvas.canvas_service import now
from backend.editor.node.node_specs import EMPTY_FIELDS

PLAN_KEYS = {"nodes", "edges", "decisions", "extend"}
NODE_FIELDS = {"ref", "kind", "parent", "name", "purpose", "sourceRef", "size", "spec", "text",
               "agentRole", "blocks", "rules", "card", "position", "criteria", "site", "design", "gateNodeId", "checks", "goal_mode", "factRefs", "scenario", "downloadsUrl", "color", "fragmentRef"}
RULE_FIELDS = {"kind", "text"}
DECISION_FIELDS = {"node", "text", "pinned"}
MAX_NODES, MAX_EDGES = 200, 600
# Bloky, pravidla a role patří kartě (uzel, sektor); komentář ani oblast je nenesou.
CARD_KINDS = ("node", "sector")


class Built:
    """Výsledek sestavení: nové položky, doplněný stav, spec/text a jmenovky pro chyby."""

    def __init__(self, graph, state):
        self.graph, self.state = copy.deepcopy(graph), copy.deepcopy(state)
        self.state_changed = False
        self.nodes, self.edges = [], []
        self.inside = {}  # id nové karty → id oblasti, do které se položí
        self.positions = {}  # explicit catalog drop points; absent means existing auto-layout
        self.specs, self.texts = {}, {}
        self.refs, self.blocks = {}, {}
        self.labels = {}  # nové id → jméno položky v dávce (pro hlášení chyb)
        self.extend_revisions, self.documents = [], []
        self.spec_revisions, self.text_revisions = {}, {}
        self.layout_moves = {}
        # id karty → `fragmentRef` z dávky; proti schránce ho ověří `brief_vault_refs.resolve_plan_refs`.
        self.fragment_refs = {}

    def new_graph(self):
        return {"nodes": [*self.graph["nodes"], *self.nodes], "edges": [*self.graph["edges"], *self.edges]}


def build(plan, graph, state):
    """Sestaví dávku nad současným grafem a stavem; uzly zatím stojí na (0, 0)."""
    if not isinstance(plan, dict) or not set(plan) <= PLAN_KEYS:
        raise ValueError("Neplatný formát dávky plánu (nodes, edges, decisions).")
    nodes_in = items_of(plan.get("nodes", []), "plan", "nodes")
    edges_in = items_of(plan.get("edges", []), "plan", "edges")
    decisions_in = items_of(plan.get("decisions", []), "plan", "decisions")
    extensions = items_of(plan.get("extend", []), "plan", "extend")
    if len(extensions) > MAX_NODES:
        raise ValueError("Dávka má nejvýše 200 rozšíření.")
    if len(nodes_in) > MAX_NODES or len(edges_in) > MAX_EDGES:
        raise ValueError(f"Dávka plánu má nejvýš {MAX_NODES} uzlů a {MAX_EDGES} vazeb.")
    if not (nodes_in or edges_in or decisions_in or extensions):
        raise ValueError("Dávka plánu je prázdná.")
    built = Built(graph, state)
    existing = {node["id"]: node for node in built.graph["nodes"]}
    for index, item in enumerate(nodes_in):
        fields(item, NODE_FIELDS, {"ref", "kind", "name"}, f"nodes[{index}]")
        ref = plan_ref(item["ref"], f"nodes[{index}]")
        if ref in built.refs:
            fail(ref, "duplicitní ref.")
        built.refs[ref] = new_id()
        built.labels[built.refs[ref]] = ref
    kinds = {key: node["kind"] for key, node in existing.items()}
    kinds.update({built.refs[item["ref"]]: item["kind"] for item in nodes_in})

    def resolve(value, label):
        if isinstance(value, str) and value.startswith("@"):
            if value[1:] not in existing:
                fail(label, f"neznámý uzel {value}.")
            return value[1:]
        if isinstance(value, str) and value in built.refs:
            return built.refs[value]
        fail(label, f"neznámý ref {value!r}.")

    parents = {built.refs[item["ref"]]: None if item.get("parent") is None else resolve(item["parent"], item["ref"])
               for item in nodes_in}
    for item in nodes_in:
        _node(built, item, parents, kinds, existing)
    for item, node in zip(nodes_in, built.nodes, strict=True):
        if "gateNodeId" in item:
            node["gateNodeId"] = resolve(item["gateNodeId"], item["ref"])
    extend_cards(built, extensions, existing)
    if built.layout_moves:
        from backend.canvas.canvas_layout import arrange
        for area, move in built.layout_moves.items():
            built.graph = arrange(built.graph, area, move["order"], move["columns"])
    for index, item in enumerate(edges_in):
        edge_of(built, item, f"edges[{index}]", resolve)
    for index, item in enumerate(decisions_in):
        label = f"decisions[{index}]"
        fields(item, DECISION_FIELDS, {"text"}, label)
        node = item.get("node")
        decision_id = new_id()
        built.labels[decision_id] = label
        built.state["decisions"].append({
            "id": decision_id, "text": item["text"], "pinned": item.get("pinned", False), "path": "",
            "nodeId": "" if node in (None, "") else resolve(node, label), "createdAt": now(), "by": "agent",
        })
        built.state_changed = True
    return built


def _node(built, item, parents, kinds, existing):
    ref, node_id = item["ref"], built.refs[item["ref"]]
    parent = parents[node_id]
    cursor, seen = parent, set()
    while cursor is not None and cursor not in seen:
        seen.add(cursor)
        if built.state["nodes"].get(cursor, {}).get("done", {}).get("confirmed", False):
            fail(ref, "uzavřená karta ani její potomci nepřijímají nové komponenty; nejprve ji otevřete.")
        cursor = existing[cursor]["parentId"] if cursor in existing else parents.get(cursor)
    # Oblast není rodič (graf ji tak odmítne); karta „v oblasti“ leží na vrstvě oblasti
    # a do jejího obdélníku ji položí rozmístění.
    if parent is not None and kinds.get(parent) == "area":
        if item["kind"] == "area":
            fail(ref, "oblast nelze vložit do oblasti.")
        built.inside[node_id] = parent
        parent = existing[parent]["parentId"] if parent in existing else parents[parent]
    node = {"id": node_id, "parentId": parent, "kind": item["kind"], "name": item["name"],
            "purpose": item.get("purpose", ""), "x": 0, "y": 0}
    for key in ("sourceRef", "size", "card", "site", "design", "checks", "goal_mode", "factRefs", "scenario", "color"):
        if key in item:
            node[key] = item[key]
    if "position" in item:
        built.positions[node_id] = position_of(item["position"], ref)
    built.nodes.append(node)
    if "spec" in item:
        if not isinstance(item["spec"], dict):
            fail(ref, "spec musí být objekt.")
        built.specs[node_id] = {**EMPTY_FIELDS, **item["spec"]}
    if "text" in item:
        built.texts[node_id] = item["text"]
    card_keys = {"blocks", "rules", "agentRole", "criteria", "downloadsUrl", "fragmentRef"} & set(item)
    if card_keys and item["kind"] not in CARD_KINDS:
        fail(ref, "bloky, pravidla a role má jen uzel nebo sektor.")
    for index, rule in enumerate(items_of(item.get("rules", []), ref, "rules")):
        label = f"{ref}.rules[{index}]"
        fields(rule, RULE_FIELDS, RULE_FIELDS, label)
        rule_id = new_id()
        built.labels[rule_id] = label
        built.state["rules"].append({"id": rule_id, "text": rule["text"], "kind": rule["kind"],
                                     "scope": "node", "target": node_id})
        built.state_changed = True
    if "fragmentRef" in item:
        built.fragment_refs[node_id] = item["fragmentRef"]
    if {"blocks", "agentRole", "criteria", "downloadsUrl", "fragmentRef"} & set(item):
        criteria = []
        for index, text in enumerate(items_of(item.get("criteria", []), ref, "criteria")):
            criterion_id = new_id()
            built.labels[criterion_id] = f"{ref}.criteria[{index}]"
            criteria.append({"id": criterion_id, "text": text, "checked": False})
        state_node = {"phase": "discover", "criteria": criteria, "steps": [],
                      "blocks": blocks_of(built, ref, node_id, items_of(item.get("blocks", []), ref, "blocks"))}
        if "agentRole" in item:
            state_node["agentRole"] = item["agentRole"]
        if "downloadsUrl" in item:
            from backend.editor.agent_memory.input_security import security_block
            state_node["downloadsUrl"] = item["downloadsUrl"]
            if item["downloadsUrl"]:
                state_node["blocks"].append(security_block(len(state_node["blocks"]) + 1))
        built.state["nodes"][node_id] = state_node
        built.state_changed = True
