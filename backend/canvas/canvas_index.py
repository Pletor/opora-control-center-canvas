"""Jednotný index plátna: karty a vazby v jednom seznamu, ze kterého čte knihovna i RLM.

Kontrakt je `docs/kontext-karet-a-index.md` §5. Čistá logika bez I/O: index se staví v paměti
při každém volání z grafu a stavu plochy (graf má nejvýše 2000 uzlů) a nic se neukládá.

- Karta (`kind` sector | node | area) nese odvozený typ (předpona názvu), vrstvu, efektivní stav, termín, cestu, adresu,
  rodiče, nejbližší sektor (u sektoru on sám), popis a cestu zdroje. Komentáře se neindexují.
- Vazba (`kind` edge) nese oba konce s názvy a adresami a zprávu na vazbě (summary, handoff,
  sentAt, due), pokud existuje.
- `text` je složený korpus pro hledání; adresa ani text nikdy nejsou klíčem, klíčem je `id`.
"""

import re

from backend.canvas.card_context import (
    card_address,
    LAYER_LABELS,
    card_chain,
    card_layer,
    effective_status,
    effective_type,
    fold,
)

INDEXED_KINDS = ("sector", "node", "area")
ENTRY_KINDS = (*INDEXED_KINDS, "edge")
DEFAULT_LIMIT = 200
MAX_LIMIT = 2000
MAX_QUERY = 1000
# Speciální slova dotazu: přesný filtr na pole záznamu místo hledání v textu.
FILTERS = {"typ": "type", "stav": "status", "druh": "kind", "vrstva": "layer"}
# `vrstva:` přijme krátký štítek i plný název; obojí se srovná na uloženou hodnotu.
LAYER_ALIASES = {
    **{fold(label): layer for layer, label in LAYER_LABELS.items()},
    **{layer: layer for layer in LAYER_LABELS},
}


def _lines(*parts):
    return "\n".join(part for part in parts if isinstance(part, str) and part)


def _card_text(entry, node_state):
    """Korpus karty: adresa, typ, štítek vrstvy, název, popis, zdroj; navíc bloky, kritéria a kroky ze stavu."""
    blocks = []
    for block in node_state.get("blocks", []):
        blocks += [block.get("title", ""), block.get("text", "")]
        blocks += [todo.get("text", "") for todo in block.get("todos", [])]
    return _lines(
        entry["address"], entry["type"] or "", LAYER_LABELS.get(entry["layer"], ""), entry["name"], entry["purpose"], entry["sourcePath"],
        *blocks,
        *(item.get("text", "") for item in node_state.get("criteria", [])),
        *(item.get("text", "") for item in node_state.get("steps", [])),
    )


def build_index(graph, state):
    """Záznamy karet v pořadí grafu, za nimi záznamy vazeb; komentáře se vynechají."""
    nodes = graph.get("nodes", [])
    by_id = {item["id"]: item for item in nodes}
    node_states = (state or {}).get("nodes", {})
    reports = (state or {}).get("edges", {})
    entries = []
    addresses = {}
    for node in nodes:
        if node["kind"] not in INDEXED_KINDS:
            continue
        node_state = node_states.get(node["id"], {})
        chain = card_chain(by_id, node)
        sector = next((item for item in reversed(chain) if item["kind"] == "sector"), None)
        card = node.get("card") or {}
        address = card_address(by_id, node)
        addresses[node["id"]] = address
        entry = {
            "id": node["id"],
            "kind": node["kind"],
            "name": node["name"],
            "type": effective_type(node) if node["kind"] == "node" else None,
            "layer": card_layer(node) if node["kind"] == "node" else None,
            "status": effective_status(node, bool(node_state.get("done", {}).get("confirmed")))
            if node["kind"] == "node" else None,
            "due": card.get("due"),
            "path": [item["name"] for item in chain],
            "address": address,
            "parentId": node["parentId"],
            "sectorId": sector["id"] if sector else None,
            "purpose": node["purpose"],
            "sourcePath": (node.get("sourceRef") or {}).get("path", ""),
        }
        entry["text"] = _card_text(entry, node_state)
        entries.append(entry)
    for edge in graph.get("edges", []):
        source, target = by_id.get(edge["source"]), by_id.get(edge["target"])
        if source is None or target is None:
            continue
        report = reports.get(edge["id"], {})
        entry = {
            "id": edge["id"],
            "kind": "edge",
            "port": edge.get("port", "next"),
            "from": edge["source"],
            "to": edge["target"],
            "fromName": source["name"],
            "toName": target["name"],
            "fromAddress": addresses.get(edge["source"]) or card_address(by_id, source),
            "toAddress": addresses.get(edge["target"]) or card_address(by_id, target),
            "summary": report.get("summary", ""),
            "handoff": report.get("handoff", ""),
            "sentAt": report.get("sentAt", ""),
            "due": report.get("due", ""),
        }
        entry["text"] = _lines(
            entry["fromAddress"], entry["toAddress"], entry["fromName"], entry["toName"],
            entry["summary"], entry["handoff"],
        )
        entries.append(entry)
    return entries


def parse_query(q):
    """Rozdělí dotaz na slova pro text a přesné filtry `typ:` / `stav:` / `druh:` / `vrstva:`."""
    words, filters = [], {}
    for raw in fold(q).split():
        key, sep, value = raw.partition(":")
        if sep and key in FILTERS:
            if value:
                field = FILTERS[key]
                filters[field] = LAYER_ALIASES.get(value, value) if field == "layer" else value
            continue
        words.append(raw)
    return words, filters


def _address_of(entry):
    return entry["fromAddress"] if entry["kind"] == "edge" else entry["address"]


def _rank(entry, words):
    """0 = všechna slova v názvu, 1 = v adrese, 2 = jinde v textu."""
    if not words:
        return 2
    if entry["kind"] != "edge" and all(word in fold(entry["name"]) for word in words):
        return 0
    address = _address_of(entry)
    if all(re.sub(r"[^a-z0-9]+", "-", word).strip("-") in address for word in words):
        return 1
    return 2


def search(entries, q="", limit=DEFAULT_LIMIT):
    """Záznamy, kde je každé slovo v `text`, a které projdou filtry; `{entries, total}`."""
    if not isinstance(q, str) or len(q) > MAX_QUERY:
        raise ValueError(f"Dotaz musí být text do {MAX_QUERY} znaků.")
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit musí být 1 až {MAX_LIMIT}.")
    words, filters = parse_query(q)
    found = []
    for entry in entries:
        if any(fold(entry.get(field) or "") != value for field, value in filters.items()):
            continue
        text = fold(entry["text"])
        if all(word in text for word in words):
            found.append(entry)
    found.sort(key=lambda entry: (_rank(entry, words), _address_of(entry), entry["id"]))
    return {"entries": found[:limit], "total": len(found)}
