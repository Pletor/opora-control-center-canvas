"""Vazby kódu mezi kartami z mapy Graphify (`graphify-out/graph.json` hlavního checkoutu).

Graphify zná symboly a jejich soubory (`source_file`). Z jeho vazeb `imports`, `imports_from` a
`calls` vzniknou dvojice souborů; soubor patří kartě, jejíž cesta zdroje (`sourceRef.path`, soubor
nebo složka) ho pokrývá, a když ho pokrývá víc karet, vyhrává nejkonkrétnější (nejdelší) cesta.
Vazba kódu mezi kartou A a B existuje, když soubor karty A odkazuje na soubor karty B. Čisté
funkce, žádný model, žádné čtení disku (to dělá `plan_lens_source.py`)."""
from backend.canvas.plan_lens_cards import clean_path

RELATIONS = ("imports", "imports_from", "calls")


def _relative(value, root):
    """`source_file` jako cesta relativní k repozitáři; absolutní uvnitř kořene se zkrátí."""
    if not isinstance(value, str) or not value:
        return None
    path = value.replace("\\", "/")
    if root:
        prefix = root.replace("\\", "/").rstrip("/") + "/"
        if path.lower().startswith(prefix.lower()):
            path = path[len(prefix):]
    return clean_path(path)


def file_links(graph, root=None):
    """Setříděné dvojice (soubor, soubor) z vazeb Graphify; stejný soubor sám na sebe se vynechá."""
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    links = graph.get("links", graph.get("edges")) if isinstance(graph, dict) else None
    if not isinstance(nodes, list) or not isinstance(links, list):
        return []
    files = {}
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            path = _relative(node.get("source_file"), root)
            if path:
                files[node["id"]] = path
    pairs = set()
    for link in links:
        if not isinstance(link, dict) or link.get("relation") not in RELATIONS:
            continue
        source, target = files.get(link.get("source")), files.get(link.get("target"))
        if source and target and source != target:
            pairs.add((source, target))
    return sorted(pairs)


def owners(cards):
    """Cesta → karta; jednu cestu nese-li víc karet, vyhrává nejmenší id (deterministicky)."""
    result = {}
    for card_id, path in sorted(cards.items()):
        if path and path not in result:
            result[path] = card_id
    return result


def owner_of(path, by_path):
    """Karta s nejkonkrétnější cestou, která soubor pokrývá (soubor sám, pak složky nahoru)."""
    parts = path.split("/")
    for size in range(len(parts), 0, -1):
        found = by_path.get("/".join(parts[:size]))
        if found is not None:
            return found
    return None


def code_edges(cards, links):
    """Setříděné dvojice (karta, karta) s vazbou v kódu; `cards` = {id karty: cesta zdroje}."""
    by_path = owners(cards)
    pairs = set()
    for source, target in links:
        a, b = owner_of(source, by_path), owner_of(target, by_path)
        if a is not None and b is not None and a != b:
            pairs.add((a, b))
    return sorted(pairs)
