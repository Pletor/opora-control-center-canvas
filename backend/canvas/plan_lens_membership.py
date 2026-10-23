"""Členství karty v oblasti pro Lens plánu (docs/plan-lens.md#členství-karty-v-oblasti).

Pořadí: výslovné `memberOf` (rozhodnutí člověka, H01) > značka „samostatné“ (`card.scope:
"samostatne"`, u sektoru `standalone: true`) > poloha (`areas.area_of`, magnet plátna) > dědění od
nejbližšího předka-karty, který oblast má > nezařazeno. Karta, která sama leží v oblasti B, zatímco
její rodič patří do oblasti A, je krokem procesu B; vazba rodič → dítě je pak předávka A → B a buď ji
nese tok `flow` mezi oblastmi (se zprávou předávky), nebo jde o diagnostiku „chybí předávka“.
Čisté funkce bez služby; `areas.py` se jen volá, jeho sémantika pro magnet plátna se nemění."""
from backend.canvas.areas import area_of

EXPLICIT, MARKED, GEOMETRY, INHERITED = "vyslovne", "samostatne", "poloha", "zdedeno"


def marked(card):
    """Záměrně samostatná karta (návrh E v docs/navrhy): není sirotek, nepatří nikam."""
    fields = card.get("card")
    return (isinstance(fields, dict) and fields.get("scope") == "samostatne") or card.get("standalone") is True


def _direct(card, nodes, area_ids):
    target = card.get("memberOf")
    if isinstance(target, str) and target in area_ids:
        return target, EXPLICIT
    if marked(card):
        return None, MARKED
    home = area_of(card, nodes)
    return (home["id"], GEOMETRY) if home is not None else (None, None)


def resolve(cards, nodes, areas):
    """{id karty: (id oblasti | None, zdroj | None)}; zdroj je jedna z konstant výše, None = nezařazeno."""
    by_id = {card["id"]: card for card in cards}
    area_ids = {area["id"] for area in areas}
    result = {}
    for start in sorted(by_id):
        chain, cursor = [], start
        while cursor in by_id and cursor not in result and cursor not in chain:
            chain.append(cursor)
            area, source = _direct(by_id[cursor], nodes, area_ids)
            if source is not None:
                result[cursor] = (area, source)
                chain.pop()
                break
            cursor = by_id[cursor].get("parentId")
        found = result.get(cursor, (None, None))
        inherited = (found[0], MARKED if found[1] == MARKED else INHERITED) if found[1] else (None, None)
        for item in chain:  # předci bez vlastního členství dědí to, co našel nejbližší předek
            result[item] = inherited
    return result


def crossings(cards, membership, graph_edges):
    """Karty ležící v jiné oblasti než jejich rodič: [{child, parent, source, target, flow}] podle dítěte.

    `flow` je id toku mezi oblastmi rodiče a dítěte (přednost má směr rodič → dítě), jinak None."""
    flows = {}
    for item in graph_edges:
        if (item.get("port") or "next") == "flow":
            flows.setdefault((item["source"], item["target"]), item["id"])
    found = []
    for card in cards:
        area, source = membership.get(card["id"], (None, None))
        parent = card.get("parentId")
        if source not in (EXPLICIT, GEOMETRY) or parent not in membership:
            continue
        upper = membership[parent][0]
        if upper is None or upper == area:
            continue
        flow = flows.get((upper, area)) or flows.get((area, upper))
        found.append({"child": card["id"], "parent": parent, "source": upper, "target": area, "flow": flow})
    return sorted(found, key=lambda item: item["child"])


def missing_pairs(found):
    """Dvojice oblastí (rodič → dítě) bez toku, setříděné: jeden tok se zprávou opraví celou dvojici."""
    return sorted({(item["source"], item["target"]) for item in found if item["flow"] is None})
