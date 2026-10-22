"""Lens plánu (docs/plan-lens.md): plán z plátna jako graf PR Lens, deterministicky a bez modelu.

`build(graph, state, reality, area)` je čistá funkce: stejný graf, stav plochy a pozorovaná realita
(existující cesty v hlavním checkoutu, vazby souborů z Graphify, původ) dají bajtově stejný spec.
Bez `area` je to pohled projektu (oblasti, toky, „Nezařazeno“), s `area` pohled jedné oblasti
(karty, vazby plánu, vazby kódu, sousedé). Limity PR Lens (256 uzlů, 512 hran) se drží stabilním
řazením podle id a ořezem, o kterém mluví souhrn i čip."""
import hashlib

from backend.canvas.areas import area_of
from backend.canvas.opora_hub_store import canonical
from backend.canvas.plan_lens_cards import done_ids, is_card, label, lanes_for, lens_id, realized
from backend.canvas.plan_lens_views import area_view, project_view, standalone

SCHEMA_VERSION = "0.2.0"
GENERATOR = {"name": "opora-plan-lens", "version": "1"}
MAX_NODES, MAX_EDGES = 256, 512
NO_COMMIT = "0000000"  # plán bez gitu ani revize Graphify: PR Lens commit vyžaduje, nula = žádný


class AreaNotFound(LookupError):
    pass


def context(graph, state, reality):
    nodes = sorted(graph.get("nodes") or [], key=lambda node: node["id"])
    cards = [node for node in nodes if is_card(node)]
    areas = [node for node in nodes if node.get("kind") == "area"]
    member = {}
    for card in cards:
        home = area_of(card, nodes)
        if home is not None:
            member[card["id"]] = home["id"]
    return {"cards": cards, "areas": areas, "member": member, "state": state or {},
            "edges": sorted(graph.get("edges") or [], key=lambda item: item["id"]),
            "existing": frozenset(reality.get("existing") or ()), "done": done_ids(state),
            "links": reality.get("links") or []}


def _limit(nodes, edges):
    """Stabilní řez: uzly i hrany podle id, hrany jen mezi zachovanými uzly; vrací i počty vynechaných."""
    nodes = sorted(nodes, key=lambda item: item["id"])
    kept = nodes[:MAX_NODES]
    ids = {item["id"] for item in kept}
    edges = sorted((item for item in edges if item["from"] in ids and item["to"] in ids), key=lambda item: item["id"])
    return kept, edges[:MAX_EDGES], len(nodes) - len(kept), max(0, len(edges) - MAX_EDGES)


def _provenance(reality, project):
    sha = reality.get("sha") or NO_COMMIT
    repo = reality.get("repo") or {"owner": "opora", "name": project or "plan"}
    return {"repo": repo, "base": {"sha": sha}, "head": {"sha": sha}, "generator": dict(GENERATOR)}


def _stats(ctx, scope_cards):
    real = sum(1 for card in scope_cards if realized(card, ctx["existing"]))
    return {"areas": len(ctx["areas"]), "cards": len(scope_cards), "withCode": real,
            "planned": len(scope_cards) - real, "standalone": standalone(scope_cards, ctx["edges"]),
            "unassigned": sum(1 for card in ctx["cards"] if card["id"] not in ctx["member"])}


def _chips(stats, cut_nodes, cut_edges):
    chips = [{"label": "Karty", "value": str(stats["cards"]), "tone": "neutral"},
             {"label": "S kódem v main", "value": str(stats["withCode"]), "tone": "hero"},
             {"label": "Jen v plánu", "value": str(stats["planned"]), "tone": "added"}]
    if cut_nodes or cut_edges:
        chips.append({"label": "Vynecháno", "value": f"{cut_nodes} uzlů, {cut_edges} hran", "tone": "neutral"})
    return chips


def build(graph, state, reality, area=None, project=None, workspace=None):
    """Odpověď `GET /api/oporahub/plan-lens`: {kind, area, digest, spec, stats, graphify}."""
    ctx = context(graph, state, reality)
    if area is None:
        nodes, edges = project_view(ctx)
        scope_cards, title = ctx["cards"], "Plán projektu"
    else:
        found = next((item for item in ctx["areas"] if item["id"] == area), None)
        if found is None:
            raise AreaNotFound("Oblast na plátně neexistuje.")
        nodes, edges = area_view(ctx, found)
        scope_cards = [card for card in ctx["cards"] if ctx["member"].get(card["id"]) == area]
        title = "Oblast " + label(found, "bez názvu")
    stats = _stats(ctx, scope_cards)
    if area is not None:
        stats["areas"] = 1
    if not nodes:  # PR Lens chce aspoň jeden uzel: prázdný plán řekne, že je prázdný
        nodes = [{"id": "prazdny-plan", "label": "Prázdný plán", "kind": "other", "delta": "added", "lane": "plan",
                  "summary": "Tady zatím není žádná karta."}]
    nodes, edges, cut_nodes, cut_edges = _limit(nodes, edges)
    summary = (f"Plán z plátna bez modelu: {stats['areas']} oblastí, {stats['cards']} karet, "
               f"{stats['withCode']} s kódem v main, {stats['planned']} jen v plánu.")
    if cut_nodes or cut_edges:
        summary += f" Kvůli limitům PR Lens vynecháno {cut_nodes} uzlů a {cut_edges} hran (podle id)."
    lanes = lanes_for(nodes)
    spec = {"schemaVersion": SCHEMA_VERSION, "kind": "graph",
            "id": lens_id("opora-plan", "/".join(part for part in (project, workspace, area) if part)),
            "title": title[:120], "summary": summary, "lenses": ["architecture"],
            "provenance": _provenance(reality, project), "lanes": lanes, "nodes": nodes, "edges": edges,
            "stats": {"chips": _chips(stats, cut_nodes, cut_edges)},
            "layout": {"direction": "right", "laneOrder": [lane["id"] for lane in lanes]}}
    spec = _sorted(spec)
    return {"kind": "plan", "area": area, "digest": hashlib.sha256(canonical(spec).encode("utf-8")).hexdigest(),
            "spec": spec, "stats": stats, "graphify": dict(reality.get("graphify") or {"available": False})}


def _sorted(value):
    """Klíče všech objektů setříděné, aby i nekanonická serializace byla bajtově stejná."""
    if isinstance(value, dict):
        return {key: _sorted(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted(item) for item in value]
    return value
