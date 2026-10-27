"""Cesty zákazníka jako trychtýř stránek: přechody odvozené z mapy (`docs/architektura-pro-agenty.md` §6).

`derive_journeys` je čistá funkce nad grafem (prosté slovníky), bez modelu a bez I/O; `project_journeys` k ní jen
přečte přijatý graf projektu (stejně jako kontrola mapy). Člověk zadává cestu jako proměnu zákazníka (`actor`,
`pointA`, `pointB`) a kroky trychtýře (`site.journeys` aplikace: `steps[].page` = id stránky, u prvního kroku smí
být `"nav"`, role `label`, posun `shift`, námitka `objection`, signál přechodu `via` a odbočka `after`); vazby mezi
kroky se nikde neukládají, počítají se při každém čtení ze stejného grafu. Kroky i cesta se předávají beze změny.

Přechod (segment): každý krok kromě prvního navazuje na krok `after`, bez něj na předchozí krok v seznamu.
Segment `from → to` se hledá po mapě (níže). Segment, který mapa vazbami nerealizuje, cestu nerozbije: přechod
člověk deklaroval, chybějící vazba je práce pro agenty (`journey.unrealized` v kontrole mapy). Rozbitá
(`broken`) je cesta jen tehdy, když chybí stránka kroku (smazaná, nebo patří jiné aplikaci).

Pojmy:
- Stránka aplikace: uzel se `site.kind == "page"`, jehož nejbližší aplikace (`site.kind == "application"`)
  v řetězu `parentId` je tato aplikace.
- Stránka v menu: stránka aplikace, mezi kterou a aplikací v řetězu `parentId` neleží jiná stránka
  (stejně jako `parentPageId == null` v `specification.navigation`).
- Komponenta: uzel pod stránkou (nejbližší stránka přes `nearest_page`), který sám není stránka ani aplikace,
  oblast ani komentář. Komponenta se sekcí: `card.section` míří na existující sekci nejbližší stránky
  (`card_section_error` je None).
- Prochodný uzel: každý uzel kromě oblastí a komentářů.

Pohyb (orientované kroky, z nichž se skládá realizace segmentu):
1. Hrana s `carries ∈ {navigation, command, data}` vede ze `source` do `target` (jen po směru hrany, oba konce
   musí být prochodné uzly). `event` cestu nenese: událost není krok zákazníka ani jeho dat.
2. Stránka → její komponenta se sekcí: zákazník na stránce použije sekci (formulář, CTA…). Do komponenty
   bez sekce se ze stránky nevstupuje: nic neříká, kterou část stránky zákazník vidí. Po hraně (bod 1) ji
   cesta projít smí: backendové uzly (API, databáze) sekci mít nemohou, pokud leží pod stránkou.
3. Komponenta → její stránka (s i bez sekce): výsledek, který dorazí do komponenty, zákazník vidí na její stránce.
Menu (`"nav"`) je jen začátek: z menu se vstoupí na kteroukoli stránku v menu, zpět do menu se cesta nevrací
(jinak by každý přechod na stránku v menu prošel vždy a nic by netestoval). Stránka, která sama je v menu, je
z menu dosažitelná jedním krokem (`nav → /kontakt`).

Hledání: nejkratší řada podle počtu kroků (BFS). Startovní uzly i sousedé se procházejí vzestupně podle id
a každý uzel si pamatuje prvního předchůdce, takže remízu vyhrává řada s menšími id dříve.

Popisky (§4): stránka = `site.path`, komponenta se sekcí = `/path[sectionId]` (path její stránky), ostatní
uzly = název (bez názvu id), menu = `nav`. `line` segmentu je jeho realizace spojená „ → “; stránka, hned za níž
následuje její komponenta se sekcí, se do ní nepíše samostatně (`nav → /kontakt[form]`, ne `nav → /kontakt →
/kontakt[form]`), stejně stránka hned po své komponentě se sekcí, pokud to není cíl segmentu. Nerealizovaný
segment má `line` jen z popisků obou kroků. `line` celé cesty jsou popisky kroků (`path`) v pořadí, v jakém je
zadal člověk (`nav → /pestovani → /novinky`).
"""

from collections import deque

from backend.canvas.site_metadata import JOURNEY_FROM_NAV, card_section_error, nearest_page
from backend.project.architecture.work_status import architecture_graph

MOVING_CARRIES = frozenset({"navigation", "command", "data"})
NAV_LABEL = "nav"
JOURNEY_FIELDS = ("purpose", "actor", "pointA", "pointB")
STEP_FIELDS = ("label", "shift", "objection", "via", "after")


def _site(node):
    site = node.get("site")
    return site if isinstance(site, dict) else {}


def _walkable(node):
    return node.get("kind") not in ("area", "comment")


def _pages(nodes, by_id):
    """{id stránky: (id aplikace, v menu)} pro stránky, které pod nějakou aplikací leží."""
    result = {}
    for node in nodes:
        if _site(node).get("kind") != "page":
            continue
        seen, current, crossed = {node["id"]}, node.get("parentId"), False
        while current is not None and current in by_id and current not in seen:
            seen.add(current)
            kind = _site(by_id[current]).get("kind")
            if kind == "application":
                result[node["id"]] = (current, not crossed)
                break
            crossed = crossed or kind == "page"
            current = by_id[current].get("parentId")
    return result


def components_of(nodes, by_id):
    """{id komponenty: id stránky} pro prochodné uzly bez `site` pod nějakou stránkou."""
    result = {}
    for node in nodes:
        if not _walkable(node) or _site(node).get("kind") is not None:
            continue
        page = nearest_page(by_id, node["id"])
        if page is not None:
            result[node["id"]] = page["id"]
    return result


def section_of(by_id, node_id):
    """Sekce, kterou komponenta realizuje, když existuje na její nejbližší stránce; jinak None."""
    card = by_id[node_id].get("card")
    section = card.get("section") if isinstance(card, dict) else None
    return section if isinstance(section, str) and card_section_error(by_id, node_id) is None else None


def _moves(nodes, edges, by_id, components):
    moves = {}
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if (edge.get("carries") in MOVING_CARRIES and source in by_id and target in by_id
                and _walkable(by_id[source]) and _walkable(by_id[target])):
            moves.setdefault(source, set()).add(target)
    for component, page in components.items():
        moves.setdefault(component, set()).add(page)
        if section_of(by_id, component) is not None:
            moves.setdefault(page, set()).add(component)
    return {key: sorted(value) for key, value in moves.items()}


def _shortest(starts, target, moves):
    parents = {start: None for start in starts}
    queue = deque(starts)
    while queue:
        current = queue.popleft()
        if current == target:
            path = []
            while current is not None:
                path.append(current)
                current = parents[current]
            return path[::-1]
        for following in moves.get(current, ()):
            if following not in parents:
                parents[following] = current
                queue.append(following)
    return None


def _page_label(page):
    path = _site(page).get("path")
    return path if isinstance(path, str) and path else page.get("name") or page["id"]


def _label(by_id, components, node_id):
    node = by_id[node_id]
    if _site(node).get("kind") == "page":
        return _page_label(node)
    section = section_of(by_id, node_id) if node_id in components else None
    if section is not None:
        return f"{_page_label(by_id[components[node_id]])}[{section}]"
    return node.get("name") or node_id


def _steps(path, by_id, components):
    """Kroky cesty: stránka sousedící s vlastní komponentou se sekcí se slije do kroku komponenty."""
    def sectioned_on(index, page_id):
        if not 0 <= index < len(path):
            return False
        other = path[index]
        return components.get(other) == page_id and section_of(by_id, other) is not None

    merged, steps = {}, []
    for index, node_id in enumerate(path):
        if _site(by_id[node_id]).get("kind") == "page":
            if sectioned_on(index + 1, node_id):
                merged[path[index + 1]] = node_id
                continue
            if index < len(path) - 1 and sectioned_on(index - 1, node_id):
                continue
        steps.append({"nodeId": node_id, "label": _label(by_id, components, node_id),
                      **({"pageId": merged[node_id]} if node_id in merged else {})})
    return steps


def _journey_name(journey):
    name = journey.get("name")
    return name if isinstance(name, str) and name else journey["id"]


def _step_path(step, by_id):
    return NAV_LABEL if step["page"] == JOURNEY_FROM_NAV else _page_label(by_id[step["page"]])


def _segment(source, target, application_id, pages, by_id, components, moves):
    """{from, to, line, realized} přechodu mezi dvěma kroky, jejichž stránky existují."""
    if source["page"] == JOURNEY_FROM_NAV:
        # Stránka cíle existuje, takže aplikace má aspoň jednu stránku v menu (její nejvyšší předek).
        starts = sorted(page for page, (app, in_nav) in pages.items() if app == application_id and in_nav)
    else:
        starts = [source["page"]]
    path = _shortest(starts, target["page"], moves)
    if path is None:
        labels = [_step_path(source, by_id), _step_path(target, by_id)]
    else:
        labels = ([NAV_LABEL] if source["page"] == JOURNEY_FROM_NAV else []) + [
            item["label"] for item in _steps(path, by_id, components)]
    return {"from": source["id"], "to": target["id"], "line": " → ".join(labels), "realized": path is not None}


def _derive(journey, application_id, pages, by_id, components, moves):
    raw = [step for step in journey.get("steps") or []
           if isinstance(step, dict) and isinstance(step.get("id"), str) and isinstance(step.get("page"), str)]
    by_step = {step["id"]: step for step in raw}
    steps, links, missing, previous = [], [], None, None
    for step in raw:
        page = step["page"]
        after = step["after"] if step.get("after") in by_step else previous
        item = {"id": step["id"], "page": page,
                **{key: step[key] for key in STEP_FIELDS if key in step}}
        if page == JOURNEY_FROM_NAV or pages.get(page, (None,))[0] == application_id:
            item["path"] = _step_path(step, by_id)
        else:
            item["missing"] = True
            missing = missing or step
        steps.append(item)
        if after is not None:
            links.append((after, step["id"]))
        previous = step["id"]
    if missing is not None:
        return {"steps": steps, "broken": f"chybí stránka {missing['page']} v kroku {missing.get('label') or missing['id']}."}
    segments = [_segment(by_step[source], by_step[target], application_id, pages, by_id, components, moves)
                for source, target in links]
    return {"steps": steps, "segments": segments, "line": " → ".join(item["path"] for item in steps)}


def derive_journeys(graph):
    """[{applicationId, id, name, purpose?, actor?, pointA?, pointB?, steps, segments, line} | {…, steps, broken}]
    pro cesty všech aplikací.

    Aplikace v pořadí id, cesty i kroky v pořadí, v jakém je člověk zadal. Poškozené položky (bez id) se přeskočí;
    tvar hlídá validátor grafu, tady se čte obranně."""
    nodes = sorted(graph.get("nodes") or [], key=lambda n: n["id"])
    by_id = {node["id"]: node for node in nodes}
    pages = _pages(nodes, by_id)
    components = components_of(nodes, by_id)
    moves = _moves(nodes, graph.get("edges") or [], by_id, components)
    result = []
    for application in nodes:
        site = _site(application)
        journeys = site.get("journeys") if site.get("kind") == "application" else None
        for journey in journeys if isinstance(journeys, list) else []:
            if not isinstance(journey, dict) or not isinstance(journey.get("id"), str):
                continue
            result.append({"applicationId": application["id"], "id": journey["id"], "name": _journey_name(journey),
                           **{key: journey[key] for key in JOURNEY_FIELDS if isinstance(journey.get(key), str)},
                           **_derive(journey, application["id"], pages, by_id, components, moves)})
    return result


def project_journeys(service, project):
    """Odvozené cesty přijaté architektury projektu (`GET /api/project-architecture/journeys`)."""
    return {"journeys": derive_journeys(architecture_graph(service, project))}
