"""Čitelný popisek a dotčené uzly zápisů, které mění karty (docs/zaznam-cinnosti.md, „Stopa karty“).

Popisek je krátká česká věta pro člověka („Pořadí 12 karet“, „Návrh grafu: +3 karty, −1 vazba“,
„Ticket práce: Hero“), nejvýš `LABEL_MAX` znaků. Počítá se jen z těla požadavku nebo z uloženého
návrhu (počty, ID), nikdy z textů zadání; jediný převzatý text je první řádek „co postavit“ vydaného ticketu
(`ticket.issue` přes `POST /api/gate/requests`, karta = `cardId`). Funkce jsou čisté.
"""
from backend.canvas.canvas_plan_summary import counted

LABEL_MAX = 120
# Oddělovač popisku od technické části `summary`; technická část ho nikdy neobsahuje.
SEPARATOR = " | "
MAX_NODES = 200

CARDS = ("karta", "karty", "karet")
CARDS_OF = ("karty", "karet", "karet")  # 2. pád: pořadí 1 karty, 12 karet
EDGES = ("vazba", "vazby", "vazeb")
PAGES_OF = ("stránky", "stránek", "stránek")
NODES_OF = ("uzlu", "uzlů", "uzlů")
STEPS = ("krok", "kroky", "kroků")


def clean(text, limit=LABEL_MAX):
    """Jeden řádek bez oddělovače, zkrácený na `limit` znaků."""
    text = " ".join(str(text).split()).replace("|", "/")
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _items(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value):
    return [item for item in value if isinstance(item, str) and item] if isinstance(value, list) else []


def unique(ids):
    """ID bez opakování v pořadí výskytu, nejvýš `MAX_NODES` (strop velikosti řádku záznamu)."""
    return list(dict.fromkeys(item for item in ids if isinstance(item, str) and item))[:MAX_NODES]


def plan_nodes(plan):
    """Existující uzly, kterých se návrh grafu týká: `updateNodes`, `removeNodes`, `nodes` s ID a konce vazeb
    zapsané jako `@<id>`. Refy nových uzlů (bez `@`) ID nemají; ta doplní routa z odpovědi."""
    plan = plan if isinstance(plan, dict) else {}
    ids = [item.get("id") for item in _items(plan.get("updateNodes"))]
    ids += _strings(plan.get("removeNodes"))
    ids += [item.get("id") for item in _items(plan.get("nodes"))]
    for edge in _items(plan.get("edges")):
        ids += [end[1:] for end in (edge.get("source"), edge.get("target")) if isinstance(end, str) and end.startswith("@")]
    return unique(ids)


def _only(updates, field):
    return bool(updates) and all(set(item.get("fields") or {}) == {field} for item in updates)


def graph_label(plan):
    """Popisek návrhu grafu: pořadí, členství v oblasti, nebo počty přidaného, odebraného a upraveného."""
    plan = plan if isinstance(plan, dict) else {}
    updates = _items(plan.get("updateNodes"))
    nodes, edges = _items(plan.get("nodes")), _items(plan.get("edges"))
    removed, removed_edges = _strings(plan.get("removeNodes")), _strings(plan.get("removeEdges"))
    edge_updates = _items(plan.get("updateEdges"))
    adopt = plan.get("adoptArchitectureContext") is True
    rest = nodes or edges or removed or removed_edges or edge_updates
    tail = " a převzetí architektury" if adopt else ""
    if not rest and _only(updates, "order"):
        return clean(f"Pořadí {counted(len(updates), CARDS_OF)}{tail}")
    if not rest and _only(updates, "memberOf"):
        return clean(f"Členství v oblasti u {counted(len(updates), CARDS_OF)}{tail}")
    parts = [sign + counted(len(items), forms) for sign, items, forms in (
        ("+", nodes, CARDS), ("−", removed, CARDS), ("~", updates, CARDS),
        ("+", edges, EDGES), ("−", removed_edges, EDGES), ("~", edge_updates, EDGES)) if items]
    if adopt:
        parts.append("převzetí architektury")
    return clean("Návrh grafu" + (": " + ", ".join(parts) if parts else ""))


def changeset_nodes(changes):
    return unique(item.get("nodeId") for item in _items(changes))


def changeset_label(changes):
    """Návrh zadání: u jedné karty s kroky „Kroky karty: 4 kroky“, jinak počet karet."""
    changes = _items(changes)
    steps = (changes[0].get("fields") or {}).get("steps") if len(changes) == 1 else None
    if isinstance(steps, list):
        return clean(f"Kroky karty: {counted(len(steps), STEPS)}")
    return clean(f"Návrh zadání: {counted(len(changes), CARDS)}")


def ticket_label(build):
    """Popisek vydaného ticketu: první řádek `build`, jinak jen druh zápisu."""
    first = build.strip().splitlines()[0] if isinstance(build, str) and build.strip() else ""
    return clean("Ticket práce: " + first) if first else "Ticket práce"


def _issued(payload):
    """(`label`, `nodeIds`) požadavku brány `ticket.issue`; jiný druh = žádná věta."""
    issue = payload.get("body") if payload.get("kind") == "ticket.issue" else None
    if not isinstance(issue, dict):
        return "", []
    work = issue.get("body") if isinstance(issue.get("body"), dict) else {}
    card = issue.get("cardId")
    return ticket_label(work.get("build")), [card] if isinstance(card, str) and card else []


def body_label(path, payload):
    """(`label`, `nodeIds`) zápisu podle cesty a těla; prázdný popisek = zápis bez vlastní věty."""
    if path == "/api/oporahub/graph-proposals" and isinstance(payload.get("plan"), dict):
        return graph_label(payload["plan"]), plan_nodes(payload["plan"])
    if path == "/api/oporahub/changesets" and isinstance(payload.get("changes"), list):
        return changeset_label(payload["changes"]), changeset_nodes(payload["changes"])
    if path == "/api/canvas-plan" and isinstance(payload.get("plan"), dict):
        from backend.canvas.canvas_plan_summary import plan_summary
        return clean("Plán: " + plan_summary(payload["plan"])), []
    if path == "/api/gate/requests":
        return _issued(payload)
    return "", []


def proposal_trace(record):
    """(`label`, `nodeIds`) přijatého návrhu z uloženého záznamu: změny grafu (`plan`), přidání grafu
    (`additions` s ID nových uzlů) nebo návrh zadání (`changes`)."""
    record = record if isinstance(record, dict) else {}
    if isinstance(record.get("changes"), list):
        return "Přijetí: " + changeset_label(record["changes"]), changeset_nodes(record["changes"])
    if isinstance(record.get("plan"), dict):
        return clean("Přijetí: " + graph_label(record["plan"])), plan_nodes(record["plan"])
    additions = record.get("additions") if isinstance(record.get("additions"), dict) else {}
    nodes = _items(additions.get("nodes"))
    return (clean("Přijetí: " + graph_label({"nodes": nodes, "edges": _items(additions.get("edges"))})),
            unique(item.get("id") for item in nodes))


def created_nodes(result):
    """ID uzlů, které vytvořil zápis: návrh přidání grafu (`additions.nodes`) nebo dávka plánu (`refs` → ID)."""
    result = result if isinstance(result, dict) else {}
    additions = result.get("additions") if isinstance(result.get("additions"), dict) else {}
    ids = [item.get("id") for item in _items(additions.get("nodes"))]
    if result.get("dryRun") is not True and isinstance(result.get("refs"), dict):
        ids += list(result["refs"].values())
    return unique(ids)


def _without_order(node):
    return {key: value for key, value in node.items() if key != "order"}


def architecture_trace(old, new):
    """(`label`, `nodeIds`) zápisu architektury proti uložené revizi: přidané, odebrané a změněné uzly."""
    before = {node.get("id"): node for node in _items((old or {}).get("nodes"))}
    after = {node.get("id"): node for node in _items((new or {}).get("nodes"))}
    changed = [node for node in after if node not in before or after[node] != before[node]]
    changed += [node for node in before if node not in after]
    ids = unique(changed)
    if not ids:
        edges = (old or {}).get("edges") != (new or {}).get("edges")
        return ("Architektura: vazby" if edges else "Architektura beze změny uzlů"), []
    order_only = all(node in before and node in after and _without_order(after[node]) == _without_order(before[node])
                     for node in changed)
    if order_only:
        return clean(f"Architektura: pořadí {counted(len(changed), PAGES_OF)}"), ids
    return clean(f"Architektura: změna u {counted(len(changed), NODES_OF)}"), ids
