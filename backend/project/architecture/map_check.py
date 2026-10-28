"""Kontrola mapy architektury bez modelu (`docs/architektura-pro-agenty.md` §5).

Čistá funkce nad přijatým grafem (prosté slovníky). Nová pole kontraktu (`site.goal`, `site.sections`,
`card.section`, `card.states`, `carries`) se čtou jen jako nepovinné klíče; tvar ověřuje validátor grafu, ne
tento modul. Chybějící pole znamená „neurčeno“ a nic se nedoplňuje.

Pod stránkou: komponenta je uzel, jehož nejbližší stránka mezi předky (`parentId` řetěz, kontrakt §3.3)
existuje. Řetěz předků dává `ancestor_ids`; geometrická oblast (`areas.area_of`) členstvím ve stránce
není (§3.5).

Výklad pravidel:
- `page.no-goal`: stránka bez neprázdného `site.goal`.
- `section.unrealized`: sekce stránky (`site.sections[].id`), na kterou se neodvolává `card.section` žádné
  komponenty pod touto stránkou. Nález nese `nodeId` stránky, sekci jmenuje zpráva.
- `section.unknown`: karta s `card.section`, kterou její nejbližší stránka nemá (sekci někdo smazal nebo
  přejmenoval), nebo karta s `card.section` mimo stránku. Nález nese `nodeId` karty. Uložení grafu tohle
  nehlídá (smazání sekce nesmí zablokovat mapu), proto to hlásí kontrola.
- Odesílatel je uzel pod stránkou nebo uzel s `card.states`, ze kterého vede aspoň jedna hrana
  `carries == "command"`.
- `command.no-receiver`: odesílatel, jehož žádná hrana `command` nemíří na uzel přítomný v grafu
  („vazba nikam nevede“, doslova). Stav bez hrany `command` se jako odesílání neodhaduje.
- `state.no-error`: odesílatel, jehož `card.states` nemá stav chyby (`chyba`, `error`, `selhání`,
  bez ohledu na velikost písmen a okolní mezery); chybějící `card.states` se počítá jako bez chyby.
- `edge.carries-unset`: hrana s portem `next` (nebo bez portu) mezi dvěma komponentami téže stránky
  bez neprázdného `carries`.
- `journey.broken`: cesta zákazníka (`site.journeys` aplikace), jejímuž kroku chybí stránka (smazaná nebo
  z jiné aplikace). Nález nese `journeyId`, zpráva jmenuje cestu a důvod z `journeys.derive_journeys`.
- `journey.unrealized`: přechod mezi dvěma kroky cesty (segment), který mapa vazbami nerealizuje. Cestu
  nerozbíjí (přechod člověk deklaroval), je to práce pro agenty. Nález za každý takový segment, nese `journeyId`.
- `journey.via-unknown`: krok cesty, jehož signál přechodu `via.section` míří na sekci, kterou stránka
  předchozího kroku (`after`, jinak předchozí v seznamu) nemá; menu (`"nav"`) sekce nemá nikdy. Krok, jehož
  předchozí stránka chybí, se nehodnotí (to hlásí `journey.broken`). Uložení grafu existenci sekce nehlídá
  (smazání stránky ani sekce nesmí zablokovat mapu), proto to hlásí kontrola. Nález nese `journeyId`.
- `journey.unverified` (`docs/brana-cesty.md` §4): nerozbitá cesta bez `lastRun`, se zastaralým (`stale`, mapa se
  od běhu změnila) nebo neprošlým dokladem; zpráva jmenuje první neúspěšný přechod. Jeden nález za cestu, nese
  `journeyId`. Práce pro agenty, ne chyba mapy. Doklady nejsou v grafu: `check_map` je dostane argumentem `runs`
  (`{(applicationId, journeyId): poslední doklad}`, načte je `map_check`); bez `runs` (`None`) pravidlo nehlásí nic,
  takže kontrola dávky plánu, návrhu změny i `gaps` v briefu se nemění (nález na kartu ani hranu nemíří).
  Pořadí pravidel cest: aplikace podle id, cesty v pořadí, v jakém je zadal člověk, segmenty a kroky v pořadí kroků.

Pořadí nálezů: podle pořadí pravidel, pak podle id (sekce stejné stránky v pořadí stránky).

Místo řešení (`check_map(..., locate=True)`, §5.1): každý nález navíc nese `solverId`, kartu, na které se díra řeší.
Nález na kartu = ta karta, nález na hranu = zdroj hrany, nález cesty = stránka zdroje přechodu: `journey.unrealized`
stránka kroku `from`, `journey.via-unknown` stránka předchozího kroku, `journey.unverified` stránka zdroje prvního
neprošlého přechodu. Kde přechod nevychází ze stránky (zdroj je menu `"nav"`), nebo nález žádný přechod nemá
(`journey.broken`, `journey.unverified` bez neprošlého přechodu), je místem řešení aplikace, která cestu nese
(cesty se upravují na ní). Bez `locate` výstup `solverId` nemá (`GET …/map-check`, dávka plánu, návrh změny).
"""

from backend.canvas.site_metadata import JOURNEY_FROM_NAV, card_section_error
from backend.editor.agent_packet.desktop_v3_packets import ancestor_ids
from backend.project.architecture.journey_runs import last_runs, latest_journey_runs
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.work_status import architecture_graph

RULES = ("journey.broken", "journey.unrealized", "journey.via-unknown", "journey.unverified", "page.no-goal", "section.unrealized", "section.unknown", "command.no-receiver",
         "state.no-error", "edge.carries-unset")
ERROR_STATES = frozenset({"chyba", "error", "selhání"})


def _site_kind(node):
    site = node.get("site")
    return site.get("kind") if isinstance(site, dict) else None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _section(node):
    card = node.get("card")
    return card.get("section") if isinstance(card, dict) else None


def _states(node):
    card = node.get("card")
    states = card.get("states") if isinstance(card, dict) else None
    return [s for s in states if isinstance(s, str)] if isinstance(states, list) else None


def page_of(by_id, node_id):
    """Id nejbližší stránky mezi předky uzlu, nebo None."""
    return next((i for i in ancestor_ids(by_id, node_id) if _site_kind(by_id[i]) == "page"), None)


def _components(nodes, by_id):
    """{id komponenty: id stránky} pro uzly pod stránkou (stránka sama komponentou není)."""
    result = {}
    for node in nodes:
        if node.get("kind") in ("area", "comment") or _site_kind(node) is not None:
            continue
        page = page_of(by_id, node["id"])
        if page is not None:
            result[node["id"]] = page
    return result


def _finding(rule, key, item_id, message, solver=None):
    """Nález; `solver` (jen u cest) je místo řešení, které `check_map` vydá jako `solverId` při `locate`."""
    return {"rule": rule, key: item_id, "message": message, **({"solverId": solver} if solver else {})}


def _page_or(page, application):
    """Stránka zdroje přechodu, u menu (`"nav"`) aplikace cesty."""
    return application if page in (None, JOURNEY_FROM_NAV) else page


def _page_rules(pages, components, nodes):
    goals, sections = [], []
    realized = {(components[n["id"]], _section(n)) for n in nodes if n["id"] in components}
    for page in pages:
        site = page["site"]
        if not _text(site.get("goal")):
            goals.append(_finding("page.no-goal", "nodeId", page["id"], "Stránka nemá cíl (goal)."))
        sections_list = site.get("sections")
        for section in sections_list if isinstance(sections_list, list) else []:
            section_id = section.get("id") if isinstance(section, dict) else None
            if isinstance(section_id, str) and (page["id"], section_id) not in realized:
                sections.append(_finding("section.unrealized", "nodeId", page["id"],
                                         f"Sekce {section_id} nemá žádnou komponentu."))
    return goals, sections


def _unknown_sections(nodes, by_id):
    findings = []
    for node in nodes:
        if not isinstance(_section(node), str):
            continue
        error = card_section_error(by_id, node["id"])
        if error:
            findings.append(_finding("section.unknown", "nodeId", node["id"], f"Karta odkazuje na neznámou sekci: {error}"))
    return findings


def _command_rules(nodes, edges, components):
    present = {n["id"] for n in nodes}
    commands = {}
    for edge in edges:
        if edge.get("carries") == "command":
            commands.setdefault(edge["source"], []).append(edge["target"])
    receivers, errors = [], []
    for node in nodes:
        targets = commands.get(node["id"])
        states = _states(node)
        if not targets or (node["id"] not in components and states is None):
            continue
        if not any(target in present for target in targets):
            receivers.append(_finding("command.no-receiver", "nodeId", node["id"],
                                      "Komponenta odesílá, ale vazba nikam nevede."))
        if not any(state.strip().casefold() in ERROR_STATES for state in states or []):
            errors.append(_finding("state.no-error", "nodeId", node["id"],
                                   "Komponenta odesílá, ale nemá stav chyby."))
    return receivers, errors


def _edge_rules(edges, components):
    findings = []
    for edge in sorted(edges, key=lambda e: e["id"]):
        if edge.get("port", "next") != "next" or _text(edge.get("carries")):
            continue
        source, target = components.get(edge["source"]), components.get(edge["target"])
        if source is not None and source == target:
            findings.append(_finding("edge.carries-unset", "edgeId", edge["id"], "Vazba neříká, co nese (carries)."))
    return findings


def _sections_of(by_id, page_id):
    sections = (by_id.get(page_id) or {}).get("site", {}).get("sections")
    return {item.get("id") for item in sections if isinstance(item, dict)} if isinstance(sections, list) else set()


def _via_unknown(item, by_id):
    """Nálezy `journey.via-unknown` jedné odvozené cesty, v pořadí kroků."""
    findings, by_step, previous = [], {step["id"]: step for step in item["steps"]}, None
    for step in item["steps"]:
        source = by_step.get(step.get("after")) or previous
        previous = step
        via = step.get("via")
        section = via.get("section") if isinstance(via, dict) else None
        if source is None or not isinstance(section, str) or "path" not in source:
            continue
        nav = source["page"] == JOURNEY_FROM_NAV
        if nav or section not in _sections_of(by_id, source["page"]):
            where = "menu" if nav else f"stránka {source['path']}"
            findings.append(_finding("journey.via-unknown", "journeyId", item["id"],
                                     f"Cesta {item['name']}: krok {step.get('label') or step['id']} čeká akci "
                                     f"v sekci {section}, kterou {where} nemá.",
                                     _page_or(source["page"], item["applicationId"])))
    return findings


def _unverified(run):
    """Důvod, proč cesta není ověřená, nebo None, když poslední doklad prošel a je aktuální."""
    if run is None:
        return "chybí ověření (doklad přehrání cesty)."
    if run["stale"]:
        return "ověření je zastaralé, mapa se od běhu změnila."
    if run["passed"]:
        return None
    failure = run.get("firstFailure")
    if failure is None:
        return "doklad nepokrývá všechny přechody cesty."
    reason = f" ({failure['reason']})" if failure.get("reason") else ""
    return f"neprošel přechod {failure['from']} → {failure['to']}{reason}."


def _journey_rules(graph, by_id, runs):
    journeys = derive_journeys(graph)
    broken = [_finding("journey.broken", "journeyId", item["id"], f"Cesta {item['name']}: {item['broken']}",
                       item["applicationId"])
              for item in journeys if "broken" in item]
    unrealized = []
    for item in journeys:
        paths = {step["id"]: step.get("path") for step in item["steps"]}
        pages = {step["id"]: step["page"] for step in item["steps"]}
        unrealized += [_finding("journey.unrealized", "journeyId", item["id"],
                                f"Cesta {item['name']}: z {paths[s['from']]} na {paths[s['to']]} nevede vazba "
                                "(navigation, command, data ani sekce stránky).",
                                _page_or(pages[s["from"]], item["applicationId"]))
                       for s in item.get("segments", []) if not s["realized"]]
    via = [finding for item in journeys for finding in _via_unknown(item, by_id)]
    unverified = []
    if runs is not None:
        latest = last_runs(graph, runs)
        for item in journeys:
            run = latest.get((item["applicationId"], item["id"]))
            reason = None if "broken" in item else _unverified(run)
            if reason:
                pages = {step["id"]: step["page"] for step in item["steps"]}
                failure = (run or {}).get("firstFailure") if run and not run["stale"] else None
                source = pages.get(failure["from"]) if failure else None
                unverified.append(_finding("journey.unverified", "journeyId", item["id"], f"Cesta {item['name']}: {reason}",
                                           _page_or(source, item["applicationId"])))
    return [*broken, *unrealized, *via, *unverified]


def _locate(findings, edges):
    """Doplní `solverId` nálezům na kartu (karta) a na hranu (zdroj hrany); nálezy cest ho už nesou."""
    sources = {edge["id"]: edge["source"] for edge in edges}
    for finding in findings:
        if "solverId" not in finding:
            finding["solverId"] = finding.get("nodeId") or sources.get(finding.get("edgeId"))


def check_map(graph, runs=None, locate=False):
    """{findings: [{rule, nodeId|edgeId|journeyId, message}], summary: {pravidlo: počet}} nad grafem `{nodes, edges}`.

    `runs` = poslední doklady cest `{(applicationId, journeyId): doklad}`; bez nich se `journey.unverified` nehodnotí.
    `locate=True` přidá každému nálezu `solverId` (místo řešení, viz docstring modulu)."""
    nodes = sorted(graph.get("nodes") or [], key=lambda n: n["id"])
    edges = graph.get("edges") or []
    by_id = {node["id"]: node for node in nodes}
    components = _components(nodes, by_id)
    pages = [node for node in nodes if _site_kind(node) == "page"]
    goals, sections = _page_rules(pages, components, nodes)
    receivers, errors = _command_rules(nodes, edges, components)
    findings = [*_journey_rules(graph, by_id, runs), *goals, *sections, *_unknown_sections(nodes, by_id), *receivers, *errors, *_edge_rules(edges, components)]
    if locate:
        _locate(findings, edges)
    else:
        for finding in findings:
            finding.pop("solverId", None)
    return {"findings": findings, "summary": {rule: sum(f["rule"] == rule for f in findings) for rule in RULES}}


def map_check(service, project):
    """Kontrola přijaté architektury projektu (`GET /api/project-architecture/map-check`)."""
    return check_map(architecture_graph(service, project), latest_journey_runs(service, project))
