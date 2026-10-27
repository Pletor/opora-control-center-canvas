"""Výřez mapy pro agenta: `node-brief.architecture` (`docs/architektura-pro-agenty.md` §4).

Čistá funkce nad stejným grafem, ze kterého se skládá node-brief; bez modelu a bez I/O. Klíč dostane jen
karta pod stránkou (nejbližší stránka přes `nearest_page`); jinak funkce vrací None a klíč v briefu chybí.
Nic se nedoplňuje: chybějící údaj = chybějící klíč, prázdný seznam se vynechá.

- `journeys`: cesty zákazníka, na kterých leží stránka karty (karta, která sama je stránka, jen ona; jinak
  nejbližší stránka): `{id, name, purpose?, youAre: {step, index}, label?, experience?, previous?, next?}`.
  `youAre` je id a pořadí (od 0) prvního kroku s touto stránkou, `label` a `experience` jsou role kroku a to, co
  člověk na stránce zažívá a jak na něj má působit (pro agenta klíčové). `previous` je krok, na který tento
  navazuje (`after`, jinak předchozí v seznamu), `next` kroky, které navazují na tento; každý soused je
  `{step, label?, path?, realized?}`, `path` jen u existující stránky, `realized` jen když cesta není rozbitá
  (vede mezi kroky vazba na mapě, viz `journeys.py`). Pořadí jako `derive_journeys`.
- `page`: `{path, goal?, feel?, section?}` nejbližší stránky; `section` = `{id, role, intent}` jen když karta má
  `card.section` a sekce na stránce existuje.
- `in` / `out`: sousední hrany karty s `carries`, v pořadí id hrany: `{carries, from}` / `{carries, to}`, kde
  `from`/`to` je název uzlu na druhé straně (bez názvu id) a `sourceRef` jeho `sourceRef.path`, jen když je.
- `states`: `card.states`, jen když jsou.
- `gaps`: pravidla kontroly mapy (`map_check`), jejichž nález míří na kartu (`nodeId`) nebo na její hranu
  (`edgeId`); každé pravidlo jednou, v pořadí `RULES`.
- Strop `LIMIT_BYTES` (2,5 KiB kompaktního JSON v UTF-8). Když se výřez nevejde, ořezává se deterministicky:
  nejdřív poslední cesty (aspoň první zůstane), pak hrany od konce, delší seznam z `in`/`out` dřív (při shodě
  `out`), nakonec i první cesta; ořezaný výřez nese `"truncated": true`.
"""

import json

from backend.canvas.site_metadata import nearest_page
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.map_check import RULES, check_map

LIMIT_BYTES = 2560


def _size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _neighbour(step, realized):
    return {"step": step["id"], **{key: step[key] for key in ("label", "path") if key in step},
            **({"realized": realized} if realized is not None else {})}


def _journeys(graph, page_id):
    result = []
    for journey in derive_journeys(graph):
        steps = journey["steps"]
        index = next((i for i, step in enumerate(steps) if step["page"] == page_id), None)
        if index is None:
            continue
        realized = {(s["from"], s["to"]): s["realized"] for s in journey.get("segments", [])}
        links = [(step.get("after") or steps[i - 1]["id"], step) for i, step in enumerate(steps) if i > 0]
        by_step = {step["id"]: step for step in steps}
        own = steps[index]
        previous = next((by_step[source] for source, step in links if step is own), None)
        following = [_neighbour(step, realized.get((own["id"], step["id"]))) for source, step in links if source == own["id"]]
        result.append({"id": journey["id"], "name": journey["name"],
                       **({"purpose": journey["purpose"]} if "purpose" in journey else {}),
                       "youAre": {"step": own["id"], "index": index},
                       **{key: own[key] for key in ("label", "experience") if key in own},
                       **({"previous": _neighbour(previous, realized.get((previous["id"], own["id"])))} if previous else {}),
                       **({"next": following} if following else {})})
    return result


def _page(page, node):
    site = page["site"]
    result = {"path": site.get("path")}
    for key in ("goal", "feel"):
        if isinstance(site.get(key), str) and site[key]:
            result[key] = site[key]
    card = node.get("card")
    section_id = card.get("section") if isinstance(card, dict) else None
    sections = site.get("sections") if isinstance(site.get("sections"), list) else []
    section = next((item for item in sections if isinstance(item, dict) and item.get("id") == section_id), None)
    if isinstance(section_id, str) and section is not None:
        result["section"] = {key: section[key] for key in ("id", "role", "intent") if key in section}
    return result


def _links(graph, by_id, node_id):
    def other(other_id, key):
        node = by_id.get(other_id, {})
        path = (node.get("sourceRef") or {}).get("path") if isinstance(node.get("sourceRef"), dict) else None
        return {key: node.get("name") or other_id, **({"sourceRef": path} if path else {})}

    incoming, outgoing = [], []
    for edge in sorted(graph.get("edges") or [], key=lambda e: e["id"]):
        if not edge.get("carries"):
            continue
        if edge["target"] == node_id:
            incoming.append({"carries": edge["carries"], **other(edge["source"], "from")})
        if edge["source"] == node_id:
            outgoing.append({"carries": edge["carries"], **other(edge["target"], "to")})
    return incoming, outgoing


def _gaps(graph, node_id):
    own_edges = {edge["id"] for edge in graph.get("edges") or [] if node_id in (edge["source"], edge["target"])}
    hit = {f["rule"] for f in check_map(graph)["findings"]
           if f.get("nodeId") == node_id or f.get("edgeId") in own_edges}
    return [rule for rule in RULES if rule in hit]


def _fit(result):
    """Ořízne výřez pod strop v pořadí z docstringu modulu."""
    while _size(result) > LIMIT_BYTES:
        journeys, incoming, outgoing = result.get("journeys", []), result.get("in", []), result.get("out", [])
        if len(journeys) > 1:
            journeys.pop()
        elif incoming or outgoing:
            (outgoing if len(outgoing) >= len(incoming) else incoming).pop()
        elif journeys:
            journeys.pop()
        else:
            break
        for key in ("journeys", "in", "out"):
            if key in result and not result[key]:
                del result[key]
        result["truncated"] = True


def node_architecture(graph, node_id):
    """Výřez mapy pro kartu `node_id`, nebo None, když karta není stránka ani neleží pod stránkou.
    Stránka je svou vlastní stránkou: i stránka přímo v menu dostane své cesty a zážitek svého kroku."""
    by_id = {node["id"]: node for node in graph.get("nodes") or []}
    if node_id not in by_id:
        return None
    node = by_id[node_id]
    is_page = (node.get("site") or {}).get("kind") == "page"
    page = node if is_page else nearest_page(by_id, node_id)
    if page is None:
        return None
    incoming, outgoing = _links(graph, by_id, node_id)
    card = node.get("card")
    states = card.get("states") if isinstance(card, dict) else None
    result = {"journeys": _journeys(graph, page["id"]), "page": _page(page, node), "in": incoming, "out": outgoing,
              **({"states": list(states)} if isinstance(states, list) and states else {}),
              "gaps": _gaps(graph, node_id)}
    result = {key: value for key, value in result.items() if value != []}
    _fit(result)
    return result
