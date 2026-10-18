"""Architektura a obsah jednoho plátna: rozdělení, složení a hledání odkazů (`docs/domeny-a-worktree.md` §4).

Architektura = uzly se `site` (domény a stránky) a všichni jejich předkové (strukturní sektory mezi
nimi), hrany mezi dvěma uzly architektury. Všechno ostatní je obsah pracovního prostoru. Uzel, který
`site` ztratí a nikomu se `site` už není předkem, se při dalším uložení vrátí do obsahu.

Funkce jsou čisté: nic nečtou ani nepíšou, grafy na vstupu nemění (bývají sdílené z cache čtení).
"""

EMPTY_REMOVED = {"nodes": [], "edges": []}


def check_shape(value):
    """Hrubý tvar grafu obsahu před skládáním; úplnou validaci dělá `validate_graph` nad složeným grafem."""
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("nodes"), list)
        or not isinstance(value.get("edges"), list)
        or not all(isinstance(n, dict) and isinstance(n.get("id"), str) for n in value["nodes"])
        or not all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in value["edges"])
    ):
        raise ValueError("Neplatný formát grafu.")
    return value


def architecture_ids(graph):
    """ID uzlů architektury: uzly se `site` a celý řetěz jejich předků."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    owned = set()
    for node in graph["nodes"]:
        if "site" not in node:
            continue
        cursor = node["id"]
        while cursor is not None and cursor in by_id and cursor not in owned:
            owned.add(cursor)
            cursor = by_id[cursor].get("parentId")
    return owned


def split(graph):
    """(architektura, obsah) ze složeného grafu; pořadí uzlů a hran zůstává."""
    owned = architecture_ids(graph)
    arch_edges = [e for e in graph["edges"] if e["source"] in owned and e["target"] in owned]
    arch_edge_ids = {e["id"] for e in arch_edges}
    return (
        {"nodes": [n for n in graph["nodes"] if n["id"] in owned], "edges": arch_edges},
        {
            "nodes": [n for n in graph["nodes"] if n["id"] not in owned],
            "edges": [e for e in graph["edges"] if e["id"] not in arch_edge_ids],
        },
    )


def visible_content(architecture, removed, content, *, legacy):
    """(obsah bez kopií architektury, konflikty).

    Uzel obsahu se stejným ID jako uzel architektury se skryje (vyhrává architektura); liší-li se,
    vrátí se jako konflikt, ať ho UI ukáže. Smazaná ID architektury (`removed`) se skryjí také, aby
    se doména ze staré kopie nevrátila. U starého grafu z repa (`legacy`: Git HEAD nebo převzatý
    `opora-canvas.json`) se kopie skrývají potichu a osiřelé uzly a hrany se vypustí.
    """
    arch_by_id = {n["id"]: n for n in architecture["nodes"]}
    arch_edge_ids = {e["id"] for e in architecture["edges"]}
    gone_nodes, gone_edges = set(removed["nodes"]), set(removed["edges"])
    conflicts, nodes = [], []
    for node in content["nodes"]:
        twin = arch_by_id.get(node["id"])
        if twin is not None:
            if not legacy and twin != node:
                conflicts.append({"id": node["id"], "name": str(node.get("name", "")), "reason": "architecture"})
            continue
        if node["id"] in gone_nodes:
            if not legacy:
                conflicts.append({"id": node["id"], "name": str(node.get("name", "")), "reason": "removed"})
            continue
        nodes.append(node)
    edges = [e for e in content["edges"] if e["id"] not in arch_edge_ids and e["id"] not in gone_edges]
    if legacy:
        present = set(arch_by_id)
        changed = True
        while changed:
            ids = present | {n["id"] for n in nodes}
            kept = [n for n in nodes if n.get("parentId") is None or n.get("parentId") in ids]
            changed = len(kept) != len(nodes)
            nodes = kept
        ids = present | {n["id"] for n in nodes}
        edges = [e for e in edges if e.get("source") in ids and e.get("target") in ids]
    return {"nodes": nodes, "edges": edges}, conflicts


def compose(architecture, removed, content, *, legacy=False):
    """(složený graf, konflikty): architektura a za ní viditelný obsah prostoru."""
    visible, conflicts = visible_content(architecture, removed, content, legacy=legacy)
    return {
        "nodes": [*architecture["nodes"], *visible["nodes"]],
        "edges": [*architecture["edges"], *visible["edges"]],
    }, conflicts


def missing_links(architecture, content):
    """Uzly a hrany obsahu, které míří na neexistující uzel (typicky smazanou architekturu)."""
    ids = {n["id"] for n in architecture["nodes"]} | {n["id"] for n in content["nodes"]}
    names = [n.get("name") or n["id"] for n in content["nodes"] if n.get("parentId") is not None and n["parentId"] not in ids]
    names += [e["id"] for e in content["edges"] if e.get("source") not in ids or e.get("target") not in ids]
    return names


def references(content, removed, hidden=()):
    """Odkazuje obsah prostoru na některý z odebíraných uzlů architektury?

    Kopie samotných odebíraných uzlů (stejné ID) ani kopie jiných uzlů architektury (`hidden`)
    se nepočítají; odkaz je jen potomek přes `parentId` nebo hrana, jejíž druhý konec zůstává.
    """
    removed, hidden = set(removed), set(hidden)
    for node in content["nodes"]:
        if node["id"] in removed or node["id"] in hidden:
            continue
        if node.get("parentId") in removed:
            return True
    for edge in content["edges"]:
        ends = (edge.get("source") in removed, edge.get("target") in removed)
        if any(ends) and not all(ends):
            return True
    return False


def _normalized(items):
    rows = []
    for item in items:
        if "x" in item and "y" in item:
            item = {**item, "x": round(item["x"]), "y": round(item["y"])}
        rows.append(item)
    return sorted(rows, key=lambda item: item["id"])


def same_content(current_content, new_content, moved_ids=()):
    """Je nový obsah stejný jako dosavadní (bez uzlů a hran, které se právě přesunuly do architektury)?

    Pořadí se nepočítá a pozice se porovnávají zaokrouhlené stejně jako při zápisu."""
    moved = set(moved_ids)
    before = {
        "nodes": [n for n in current_content["nodes"] if n["id"] not in moved],
        "edges": [e for e in current_content["edges"] if e["id"] not in moved],
    }
    return all(_normalized(before[key]) == _normalized(new_content[key]) for key in ("nodes", "edges"))


def ids(graph):
    return {n["id"] for n in graph["nodes"]}, {e["id"] for e in graph["edges"]}
