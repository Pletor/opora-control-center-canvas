"""Kontrola mapy architektury bez modelu (`docs/architektura-pro-agenty.md` §5).

Čistá funkce nad přijatým grafem (prosté slovníky). Nová pole kontraktu (`site.goal`, `site.sections`,
`section`, `card.states`, `carries`) se čtou jen jako nepovinné klíče; tvar ověřuje validátor grafu, ne
tento modul. Chybějící pole znamená „neurčeno“ a nic se nedoplňuje.

Pod stránkou: komponenta je uzel, jehož nejbližší stránka mezi předky (`parentId` řetěz, kontrakt §3.3)
existuje. Řetěz předků dává `ancestor_ids`; geometrická oblast (`areas.area_of`) členstvím ve stránce
není (§3.5).

Výklad pravidel:
- `page.no-goal`: stránka bez neprázdného `site.goal`.
- `section.unrealized`: sekce stránky (`site.sections[].id`), na kterou se neodvolává `section` žádné
  komponenty pod touto stránkou. Nález nese `nodeId` stránky, sekci jmenuje zpráva.
- Odesílatel je uzel pod stránkou nebo uzel s `card.states`, ze kterého vede aspoň jedna hrana
  `carries == "command"`.
- `command.no-receiver`: odesílatel, jehož žádná hrana `command` nemíří na uzel přítomný v grafu
  („vazba nikam nevede“, doslova). Stav bez hrany `command` se jako odesílání neodhaduje.
- `state.no-error`: odesílatel, jehož `card.states` nemá stav chyby (`chyba`, `error`, `selhání`,
  bez ohledu na velikost písmen a okolní mezery); chybějící `card.states` se počítá jako bez chyby.
- `edge.carries-unset`: hrana s portem `next` (nebo bez portu) mezi dvěma komponentami téže stránky
  bez neprázdného `carries`.
- `journey.broken` přijde s cestami zákazníka (`site.journeys`, etapa 7); dnes se nepočítá.

Pořadí nálezů: podle pořadí pravidel, pak podle id (sekce stejné stránky v pořadí stránky).
"""

from backend.editor.agent_packet.desktop_v3_packets import ancestor_ids
from backend.project.architecture.work_status import architecture_graph

RULES = ("page.no-goal", "section.unrealized", "command.no-receiver", "state.no-error", "edge.carries-unset")
ERROR_STATES = frozenset({"chyba", "error", "selhání"})


def _site_kind(node):
    site = node.get("site")
    return site.get("kind") if isinstance(site, dict) else None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


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


def _finding(rule, key, item_id, message):
    return {"rule": rule, key: item_id, "message": message}


def _page_rules(pages, components, nodes):
    goals, sections = [], []
    realized = {(components[n["id"]], n.get("section")) for n in nodes if n["id"] in components}
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


def check_map(graph):
    """{findings: [{rule, nodeId|edgeId, message}], summary: {pravidlo: počet}} nad grafem `{nodes, edges}`."""
    nodes = sorted(graph.get("nodes") or [], key=lambda n: n["id"])
    edges = graph.get("edges") or []
    by_id = {node["id"]: node for node in nodes}
    components = _components(nodes, by_id)
    pages = [node for node in nodes if _site_kind(node) == "page"]
    goals, sections = _page_rules(pages, components, nodes)
    receivers, errors = _command_rules(nodes, edges, components)
    findings = [*goals, *sections, *receivers, *errors, *_edge_rules(edges, components)]
    return {"findings": findings, "summary": {rule: sum(f["rule"] == rule for f in findings) for rule in RULES}}


def map_check(service, project):
    """Kontrola přijaté architektury projektu (`GET /api/project-architecture/map-check`)."""
    return check_map(architecture_graph(service, project))
