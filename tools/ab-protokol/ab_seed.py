"""Stejný výchozí stav pro obě varianty a značky, podle kterých se měří předání kontextu."""
from __future__ import annotations

NONE = {"kind": "none", "targetId": "", "note": ""}


def graph_nodes(fix):
    sector = fix["sector"]
    nodes = [{"id": sector["id"], "parentId": None, "kind": "sector", "name": sector["name"],
              "purpose": sector["purpose"], "x": 0, "y": 0}]
    for index, card in enumerate(fix["cards"]):
        nodes.append({"id": card["id"], "parentId": sector["id"], "kind": "node", "name": card["name"],
                      "purpose": card["purpose"], "x": index * 520, "y": 0})
    return nodes


def block_id(card, index):
    return f"{card['id'][:8]}-b{index + 1}"


def desk_state(fix):
    decisions = [{"id": f"d{i}", "text": d["text"], "pinned": d["pinned"], "path": "", "nodeId": "",
                  "createdAt": "2026-10-05T00:00:00+00:00", "by": "human"} for i, d in enumerate(fix["decisions"])]
    nodes = {}
    for card in fix["cards"]:
        nodes[card["id"]] = {"phase": "discover", "criteria": [], "steps": [], "blocks": [
            {"id": block_id(card, j), "number": str(j + 1), "title": b["title"], "text": b["text"], "tags": [],
             "todos": [], "images": [], "parentBlockId": "", "ports": [],
             "state": {"status": "open", "condition": b["condition"], "onMet": NONE, "onUnmet": NONE}}
            for j, b in enumerate(card["blocks"])]}
    return {"settings": [], "rules": [], "tickets": [], "edges": {}, "decisions": decisions, "nodes": nodes}


def seed(meter, scope, fix):
    """Stejný výchozí stav pro obě varianty: sektor, tři karty, vazby `next`, bloky a zadání."""
    meter.where("setup", "seed")
    view = meter.call("human", "GET", "/api/view", params=scope).json()
    meter.call("human", "POST", "/api/graph", body={**scope, "graph": {"nodes": graph_nodes(fix), "edges": fix["edges"]},
                                                    "digest": view["digest"]})
    current = meter.call("human", "GET", "/api/desktop-v3/state", params=scope).json()
    meter.call("human", "POST", "/api/desktop-v3/state",
               body={**scope, "expectedRevision": current["revision"], "state": desk_state(fix)})
    for card in fix["cards"]:
        spec = meter.call("human", "GET", "/api/node-spec", params={**scope, "node": card["id"]}).json()
        meter.call("human", "POST", "/api/node-spec", body={**scope, "node": card["id"],
                                                            "expected_revision": spec["revision"], "fields": card["spec"]})


def markers(index):
    """Jednoznačné značky, které agent karty `index` zanechá a další karta má najít."""
    return {"decision": f"ROZHODNUTI-{index}", "handoff": f"PREDAVKA-{index}", "step": f"KROK-{index}-",
            "check": f"KONTROLA-{index}", "pr": f"https://github.com/sim/ample/pull/{100 + index}",
            "lens": f"LENS-{index}"}
