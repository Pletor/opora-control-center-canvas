"""Dva pohledy Lens plánu (docs/plan-lens.md): projekt (oblasti a toky) a oblast (karty a vazby).

Vstupem je hotový kontext z `plan_lens.py` (graf plátna, stav plochy, existující cesty, vazby kódu
z Graphify, členství karet v oblastech). Výstupem jsou nesetříděné uzly a hrany PR Lens; řazení,
limity a dokument dělá `plan_lens.py`."""
from collections import Counter

from backend.canvas.plan_lens_cards import (
    DONE,
    EDGE_KIND,
    LANE_LABEL,
    LANES,
    NEIGHBOURS,
    card_node,
    clip,
    edge,
    first_sentence,
    label,
    layer,
    lens_id,
    realized,
    report_label,
    source_path,
)
from backend.canvas.plan_lens_code import code_edges
from backend.canvas.plan_lens_membership import INHERITED, MARKED, missing_pairs

PLAN_PORTS = ("next", "action", "rule", "block")
INHERITED_BADGE, MISSING = "zděděno", "chybí předávka"


def _port(item):
    return item.get("port") or "next"


def _progress(cards, done):
    return f"{sum(1 for card in cards if card['id'] in done)}/{len(cards)} {DONE}"


def _dominant(cards):
    """Pruh oblasti v pohledu projektu: nejčastější vrstva jejích karet, remíza podle pořadí pruhů."""
    counts = Counter(layer(card) for card in cards)
    order = [key for key, _ in LANES]
    return min(counts, key=lambda key: (-counts[key], order.index(key))) if counts else "plan"


def _group_node(node_id, text, kind, lane, cards, ctx, summary=None, subtitle=None):
    real = any(realized(card, ctx["existing"]) for card in cards)
    item = {"id": node_id, "label": text, "kind": kind, "delta": "unchanged" if real else "added", "lane": lane}
    if subtitle:
        item["subtitle"] = subtitle
    if summary:
        item["summary"] = summary
    item["badges"] = [_progress(cards, ctx["done"])]
    return item


def _handoff_note(ctx, source, target):
    """Návrh pro člověka k dvojici oblastí bez toku: co by měla zpráva předávky říct."""
    names = {area["id"]: label(area, "Oblast bez názvu") for area in ctx["areas"]}
    return clip(f"Karta oblasti {names.get(target, '?')} je krokem pod kartou oblasti {names.get(source, '?')}, "
                f"ale tok mezi nimi chybí. Návrh: přidat tok (flow) {names.get(source, '?')} → "
                f"{names.get(target, '?')} se zprávou předávky, co první oblast předává druhé.", 600)


def project_view(ctx):
    """Oblasti jako moduly, toky mezi nimi jako data, karty mimo oblasti jako „Nezařazeno“ po pruzích."""
    nodes, by_area, loose = [], {area["id"]: [] for area in ctx["areas"]}, {}
    for card in ctx["cards"]:
        home = ctx["member"].get(card["id"])
        group = "samostatne" if ctx["source"].get(card["id"]) == MARKED else "nezarazeno"
        (by_area[home] if home else loose.setdefault((group, layer(card)), [])).append(card)
    missing = missing_pairs(ctx["crossings"])
    for area in ctx["areas"]:
        cards = by_area[area["id"]]
        inherited = sum(1 for card in cards if ctx["source"].get(card["id"]) == INHERITED)
        item = _group_node(lens_id("area", area["id"]), label(area, "Oblast bez názvu"), "module",
                           _dominant(cards), cards, ctx, first_sentence(area.get("purpose")),
                           f"karet: {len(cards)}" + (f", zděděno: {inherited}" if inherited else ""))
        if any(target == area["id"] for _, target in missing):
            item["badges"].append(MISSING)
        nodes.append(item)
    for (group, lane), cards in sorted(loose.items()):
        names = ", ".join(sorted(clip(card.get("name"), 40) or "?" for card in cards))
        title, note = (("Samostatné", "Záměrně samostatné karty: ") if group == "samostatne"
                       else ("Nezařazeno", "Karty mimo oblasti: "))
        nodes.append(_group_node(lens_id(group, lane), f"{title} · {LANE_LABEL[lane]}", "other", lane,
                                 cards, ctx, clip(note + names, 200), f"karet: {len(cards)}"))
    area_ids = {area["id"] for area in ctx["areas"]}
    deltas = {item["id"]: item["delta"] for item in nodes}
    edges = []
    for item in ctx["edges"]:
        if _port(item) == "flow" and item["source"] in area_ids and item["target"] in area_ids:
            source, target = lens_id("area", item["source"]), lens_id("area", item["target"])
            delta = "unchanged" if deltas[source] == deltas[target] == "unchanged" else "added"
            edges.append(edge(lens_id("flow", item["id"]), source, target, "data", delta,
                              report_label(ctx["state"], item["id"])))
    for source, target in missing:
        a, b = lens_id("area", source), lens_id("area", target)
        diagnostic = edge(lens_id("chybi", f"{source}--{target}"), a, b, "other", "added", MISSING)
        diagnostic["summary"] = _handoff_note(ctx, source, target)
        edges.append(diagnostic)
    return nodes, edges


def _neighbour(area, ctx, note=None):
    item = {"id": lens_id("soused", area["id"]), "label": label(area, "Oblast bez názvu"), "kind": "external",
            "delta": "unchanged", "lane": NEIGHBOURS[0], "subtitle": "sousední oblast"}
    summary = note or first_sentence(area.get("purpose"))
    if summary:
        item["summary"] = summary
    return item


def area_view(ctx, area):
    """Karty oblasti po vrstvách, vazby plánu mezi nimi, vazby kódu z Graphify a sousední oblasti."""
    inside = [card for card in ctx["cards"] if ctx["member"].get(card["id"]) == area["id"]]
    ids = {card["id"] for card in inside}
    nodes = {item["id"]: item for item in (card_node(card, ctx["existing"], ctx["done"]) for card in inside)}
    for card in inside:
        if ctx["source"].get(card["id"]) == INHERITED:
            nodes[lens_id("card", card["id"])]["badges"].append(INHERITED_BADGE)
    areas = {item["id"]: item for item in ctx["areas"]}
    edges = {}

    def delta(*keys):
        return "unchanged" if all(nodes[key]["delta"] == "unchanged" for key in keys) else "added"

    for item in ctx["edges"]:
        port, source, target = _port(item), item["source"], item["target"]
        if port == "flow" and area["id"] in (source, target) and source != target:
            other = areas.get(target if source == area["id"] else source)
            if other is not None:  # tok s okolím: soused jako vnější uzel, zpráva toku má přednost
                node = _neighbour(other, ctx, report_label(ctx["state"], item["id"]))
                if node.get("summary") or node["id"] not in nodes:
                    nodes[node["id"]] = node
            continue
        if port not in PLAN_PORTS or (source not in ids and target not in ids):
            continue
        kind, text = EDGE_KIND.get(port, "other"), report_label(ctx["state"], item["id"])
        if source in ids and target in ids:
            a, b = lens_id("card", source), lens_id("card", target)
            edges[lens_id("edge", item["id"])] = edge(lens_id("edge", item["id"]), a, b, kind, delta(a, b), text)
            continue
        outside = target if source in ids else source
        home = areas.get(ctx["member"].get(outside))
        if home is None or home["id"] == area["id"]:
            continue  # karta mimo oblasti nebo na jiné vrstvě plátna: v pohledu oblasti se nekreslí
        node = _neighbour(home, ctx)
        nodes.setdefault(node["id"], node)
        card = lens_id("card", source if source in ids else target)
        a, b = (card, node["id"]) if source in ids else (node["id"], card)
        key = lens_id("hranice", f"{a}--{b}--{kind}")
        edges.setdefault(key, edge(key, a, b, kind, delta(card), text))
    _handoffs(ctx, area, nodes, edges, delta)
    paths = {card["id"]: source_path(card) for card in ctx["cards"] if source_path(card)}
    for a, b in code_edges(paths, ctx["links"]):
        if a in ids and b in ids:
            key = lens_id("kod", f"{a}--{b}")
            edges[key] = edge(key, lens_id("card", a), lens_id("card", b), "dependency", "unchanged", "kód", "muted")
    return list(nodes.values()), list(edges.values())


def _handoffs(ctx, area, nodes, edges, delta):
    """Rodič v jiné oblasti než dítě: předávka po toku (se zprávou), jinak diagnostika „chybí předávka“."""
    areas = {item["id"]: item for item in ctx["areas"]}
    for item in ctx["crossings"]:
        if area["id"] not in (item["source"], item["target"]):
            continue
        incoming = item["target"] == area["id"]  # tady leží dítě, rodič je v sousední oblasti
        other = areas[item["source"] if incoming else item["target"]]
        neighbour = _neighbour(other, ctx)
        nodes.setdefault(neighbour["id"], neighbour)
        card = lens_id("card", item["child"] if incoming else item["parent"])
        a, b = (neighbour["id"], card) if incoming else (card, neighbour["id"])
        key = lens_id("predavka", f"{item['parent']}--{item['child']}")
        if item["flow"]:
            report = report_label(ctx["state"], item["flow"])
            edges[key] = edge(key, a, b, "data", delta(card), "předávka: " + report if report else "předávka")
            continue
        edges[key] = edge(key, a, b, "other", "added", MISSING)
        edges[key]["summary"] = _handoff_note(ctx, item["source"], item["target"])
        if MISSING not in nodes[card]["badges"]:
            nodes[card]["badges"].append(MISSING)


def standalone(cards, graph_edges):
    """Karty bez jediné vazby plánu na jinou kartu (počítá se v celém grafu)."""
    linked = set()
    for item in graph_edges:
        if _port(item) in PLAN_PORTS and item["source"] != item["target"]:
            linked.update((item["source"], item["target"]))
    return sum(1 for card in cards if card["id"] not in linked)
