"""Výřez mapy pro agenta: `node-brief.architecture` (`docs/architektura-pro-agenty.md` §4).

Čistá funkce nad stejným grafem, ze kterého se skládá node-brief; bez modelu a bez I/O. Klíč dostane jen
karta pod stránkou (nejbližší stránka přes `nearest_page`); jinak funkce vrací None a klíč v briefu chybí.
Nic se nedoplňuje: chybějící údaj = chybějící klíč, prázdný seznam se vynechá.

- `journeys`: cesty zákazníka, na kterých leží stránka karty (karta, která sama je stránka, jen ona; jinak
  nejbližší stránka): `{id, name, purpose?, actor?, pointA?, pointB?, youAre: {step, index}, label?, shift?,
  objection?, previous?, next?, lastRun?}`. Řetěz „proč“: kdo je zákazník a jeho proměna A → B (proč existuje cesta),
  posun a námitka kroku (proč existuje stránka), sousední kroky se signálem `via` (co se na stránce má stát),
  úkol komponenty je `node.purpose` v briefu (tady se neopakuje). `youAre` je id a pořadí (od 0) prvního kroku
  s touto stránkou. `previous` je krok, na který tento navazuje (`after`, jinak předchozí v seznamu), `next`
  kroky, které navazují na tento; každý soused je `{step, label?, path?, realized?, via?}`, `path` jen u existující
  stránky, `realized` jen když cesta není rozbitá (vede mezi kroky vazba na mapě, viz `journeys.py`). `via`
  souseda je signál přechodu mezi ním a tímto krokem: u `previous` jak zákazník přišel sem (akce na předchozí
  stránce, `via` tohoto kroku), u `next` co má zákazník udělat na této stránce, aby šel dál (`via` následujícího
  kroku). Pořadí jako `derive_journeys`. `lastRun` = `{passed, stale}` posledního dokladu přehrání cesty
  (`docs/brana-cesty.md` §4, `journey_runs.last_runs`), jen když cesta doklad má; doklady nejsou v grafu, funkce je
  dostane argumentem `runs` (skládá je `node_brief.py`). Bez textů, ořez ho samostatně nebere (dvě pole).
- `page`: `{path, goal?, feel?, section?}` nejbližší stránky; `section` = `{id, role, intent, moves?}` jen když karta
  má `card.section` a sekce na stránce existuje; `moves` (čím sekce posouvá zákazníka) jen když ho sekce má.
- `in` / `out`: sousední hrany karty s `carries`, v pořadí id hrany: `{carries, from}` / `{carries, to}`, kde
  `from`/`to` je název uzlu na druhé straně (bez názvu id) a `sourceRef` jeho `sourceRef.path`, jen když je.
- `states`: `card.states`, jen když jsou.
- `holes` (§5.1): `[{rule, message}]` nálezů kontroly mapy (`map_check`), které míří na kartu (`nodeId`) nebo na
  její hranu (`edgeId`), a navíc nálezů `journey.unrealized`, jejichž přechod vychází ze stránky karty (stránka
  sama, nebo nejbližší stránka komponenty; `solverId` z `check_map(locate=True)`). `section.unrealized` nese
  `nodeId` stránky, takže ho dostane jen stránka sama. Nejvýš `HOLES_LIMIT` (5), v pořadí `RULES` (uvnitř pravidla
  v pořadí kontroly mapy).
- `gaps`: pravidla všech těchto nálezů (i těch nad strop `holes`); každé pravidlo jednou, v pořadí `RULES`.
  `check_map` se volá bez dokladů: `journey.unverified` se nehodnotí, ověření cesty karta vidí v `journeys[].lastRun`.
- `model` (`docs/studio.md` §4a): cíl z MODELu domény karty, hotový od `node_model_target.read_model_target`
  (argument `model`, skládá ho `node_brief.py`); jen když na kartu váže uzel modelu. Karta, která neleží pod
  stránkou, ale cíl z MODELu má (typicky služba), dostane výřez jen s `model`.
- Strop `LIMIT_BYTES` (2,5 KiB kompaktního JSON v UTF-8). Dokud se výřez nevejde, odebírá se po celých klíčích
  (texty se nikdy nezkracují) v tomto pořadí (`docs/cesta-zakaznika-a-brief.md` §4.3, `docs/architektura-pro-agenty.md`
  §5.1):
  0. `holes` od konce, pak celé (`gaps` zůstává);
  0b. `model.links`, pak celý `model` (`docs/studio.md` §4a);
  1. cesty od konce, dokud nezbude jedna;
  2. hrany od konce, delší seznam z `in`/`out` dřív (při shodě `out`);
  3. v první cestě `purpose`;
  4. v první cestě `next` od konce kromě prvního souseda, pak `previous.via`, pak celé `previous`;
  5. `page.feel`, pak `page.goal`;
  6. v první cestě `objection`;
  7. první cesta celá (poslední záchrana).
  Nikdy se neořízne `page.section` (ani jeho `moves`); do sedmého kroku ani `actor`, `pointA`, `pointB`, `shift`
  a první `next`: to je řetěz „proč“. Ořezaný výřez nese `"truncated": true`.
"""

import json

from backend.canvas.site_metadata import nearest_page
from backend.project.architecture.journey_runs import last_runs
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.map_check import RULES, check_map

LIMIT_BYTES = 2560
HOLES_LIMIT = 5


def _size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


JOURNEY_FIELDS = ("purpose", "actor", "pointA", "pointB")
STEP_FIELDS = ("label", "shift", "objection")


def _neighbour(step, realized, via):
    return {"step": step["id"], **{key: step[key] for key in ("label", "path") if key in step},
            **({"realized": realized} if realized is not None else {}),
            **({"via": via} if isinstance(via, dict) else {})}


def _journeys(graph, page_id, runs):
    result = []
    verified = last_runs(graph, runs) if runs else {}
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
        following = [_neighbour(step, realized.get((own["id"], step["id"])), step.get("via"))
                     for source, step in links if source == own["id"]]
        result.append({"id": journey["id"], "name": journey["name"],
                       **{key: journey[key] for key in JOURNEY_FIELDS if key in journey},
                       "youAre": {"step": own["id"], "index": index},
                       **{key: own[key] for key in STEP_FIELDS if key in own},
                       **({"previous": _neighbour(previous, realized.get((previous["id"], own["id"])), own.get("via"))}
                          if previous else {}),
                       **({"next": following} if following else {}),
                       **({"lastRun": {key: run[key] for key in ("passed", "stale")}}
                          if (run := verified.get((journey["applicationId"], journey["id"]))) else {})})
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
        result["section"] = {key: section[key] for key in ("id", "role", "intent", "moves") if key in section}
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


def _holes(graph, node_id, page_id):
    """(holes, gaps) karty: nálezy na kartu, její hranu a nerealizované přechody ze stránky karty (§5.1)."""
    own_edges = {edge["id"] for edge in graph.get("edges") or [] if node_id in (edge["source"], edge["target"])}
    hits = [f for f in check_map(graph, locate=True)["findings"]
            if f.get("nodeId") == node_id or f.get("edgeId") in own_edges
            or (f["rule"] == "journey.unrealized" and f["solverId"] == page_id)]
    hits.sort(key=lambda f: RULES.index(f["rule"]))
    holes = [{"rule": f["rule"], "message": f["message"]} for f in hits[:HOLES_LIMIT]]
    return holes, [rule for rule in RULES if any(f["rule"] == rule for f in hits)]


def _cut_holes(result):
    holes = result.get("holes")
    if not holes:
        return False
    holes.pop()
    return True


def _cut_model(result):
    return _cut_key(result.get("model"), "links") or _cut_key(result, "model")


def _cut_journeys(result):
    journeys = result.get("journeys", [])
    if len(journeys) > 1:
        journeys.pop()
        return True
    return False


def _cut_edges(result):
    incoming, outgoing = result.get("in", []), result.get("out", [])
    if not incoming and not outgoing:
        return False
    (outgoing if len(outgoing) >= len(incoming) else incoming).pop()
    return True


def _cut_key(owner, key):
    if isinstance(owner, dict) and key in owner:
        del owner[key]
        return True
    return False


def _first(result):
    journeys = result.get("journeys")
    return journeys[0] if journeys else None


def _cut_neighbours(result):
    first = _first(result)
    if first is None:
        return False
    if len(first.get("next", [])) > 1:
        first["next"].pop()
        return True
    return _cut_key(first.get("previous"), "via") or _cut_key(first, "previous")


def _cut_last_journey(result):
    return _cut_key(result, "journeys") if result.get("journeys") else False


# Pořadí ořezu z docstringu modulu; každý krok odebere jednu věc a vrátí, zda měl co odebrat.
_CUTS = (
    _cut_holes,
    _cut_model,
    _cut_journeys,
    _cut_edges,
    lambda result: _cut_key(_first(result), "purpose"),
    _cut_neighbours,
    lambda result: _cut_key(result.get("page"), "feel") or _cut_key(result.get("page"), "goal"),
    lambda result: _cut_key(_first(result), "objection"),
    _cut_last_journey,
)


def _fit(result):
    """Ořízne výřez pod strop v pořadí z docstringu modulu; deterministicky, po celých klíčích."""
    while _size(result) > LIMIT_BYTES:
        if not any(cut(result) for cut in _CUTS):
            break
        for key in ("holes", "journeys", "in", "out"):
            if key in result and not result[key]:
                del result[key]
        result["truncated"] = True


def node_architecture(graph, node_id, runs=None, model=None):
    """Výřez mapy pro kartu `node_id`, nebo None, když karta není stránka ani neleží pod stránkou a nemá cíl z MODELu.
    Stránka je svou vlastní stránkou: i stránka přímo v menu dostane své cesty a posun svého kroku.
    `runs` = poslední doklady cest `{(applicationId, journeyId): doklad}` pro `journeys[].lastRun`;
    `model` = cíl z MODELu (`node_model_target.read_model_target`) nebo None."""
    by_id = {node["id"]: node for node in graph.get("nodes") or []}
    if node_id not in by_id:
        return None
    node = by_id[node_id]
    is_page = (node.get("site") or {}).get("kind") == "page"
    page = node if is_page else nearest_page(by_id, node_id)
    if page is None:
        if not model:
            return None
        result = {"model": dict(model)}
        _fit(result)
        return result
    incoming, outgoing = _links(graph, by_id, node_id)
    card = node.get("card")
    states = card.get("states") if isinstance(card, dict) else None
    holes, gaps = _holes(graph, node_id, page["id"])
    result = {"journeys": _journeys(graph, page["id"], runs), "page": _page(page, node), "in": incoming, "out": outgoing,
              **({"states": list(states)} if isinstance(states, list) and states else {}),
              "holes": holes, "gaps": gaps, **({"model": dict(model)} if model else {})}
    result = {key: value for key, value in result.items() if value != []}
    _fit(result)
    return result
