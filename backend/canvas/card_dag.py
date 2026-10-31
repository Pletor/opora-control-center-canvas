"""Card DAG over `next` edges (night contract §2, docs/oporahub-agent-state.md "Graf karet").

A `next` edge (port missing or `next`) says the target card follows the source card. Saving a
graph must not introduce a cycle; a legacy cycle already stored is tolerated (its cards get a
topological index after the acyclic part) so an old project still opens and can be repaired.
"""
CARD_KINDS = ("node", "sector")


class CardCycleError(ValueError):
    """409: the saved graph would make the `next` edges cyclic; `cycle` is the closed path of card ids."""

    def __init__(self, cycle):
        self.cycle = cycle
        super().__init__("Vazby next mezi kartami tvoří cyklus: " + " → ".join(cycle) + ".")


def next_edges(graph):
    """Sorted unique `(source, target)` pairs of `next` edges between cards."""
    kinds = {node["id"]: node["kind"] for node in graph.get("nodes", [])}
    return sorted({(edge["source"], edge["target"]) for edge in graph.get("edges", [])
                   if edge.get("port", "next") == "next"
                   and kinds.get(edge["source"]) in CARD_KINDS and kinds.get(edge["target"]) in CARD_KINDS})


def _successors(pairs):
    result = {}
    for source, target in pairs:
        result.setdefault(source, []).append(target)
    return result


def _path(successors, start, goal):
    """Shortest successor path start → goal (BFS, ids in sorted order), or None."""
    parents, frontier = {start: None}, [start]
    while frontier:
        following = []
        for current in frontier:
            for target in sorted(successors.get(current, [])):
                if target in parents:
                    continue
                parents[target] = current
                if target == goal:
                    path = [target]
                    while parents[path[-1]] is not None:
                        path.append(parents[path[-1]])
                    return path[::-1]
                following.append(target)
        frontier = following
    return None


def introduced_cycle(before, after):
    """The first cycle of `after` that uses a `next` edge absent from `before` ([a, b, …, a]), or None."""
    old, new = set(next_edges(before or {"nodes": [], "edges": []})), next_edges(after)
    successors = _successors(new)
    for source, target in new:
        if (source, target) in old:
            continue
        back = _path(successors, target, source)
        if back is not None:
            return [source, *back]
    return None


def check_save(before, after):
    cycle = introduced_cycle(before, after)
    if cycle is not None:
        raise CardCycleError(cycle)


def topo_order(card_ids, pairs, order=None):
    """Kahn's order; a tie (cards ready in the same step) breaks by `order[card]` (intended order, 10000 when
    absent), then by id. Edges keep precedence. Without `order` it is the plain id tie-break; cards on a
    legacy cycle follow in the same key order."""
    order = order or {}

    def key(card):
        return (order.get(card, 10000), card)

    cards = set(card_ids)
    pairs = [(s, t) for s, t in pairs if s in cards and t in cards]
    incoming = {card: 0 for card in cards}
    for _, target in pairs:
        incoming[target] += 1
    successors = _successors(pairs)
    ready, result = sorted((card for card, count in incoming.items() if count == 0), key=key), []
    while ready:
        current = ready.pop(0)
        result.append(current)
        for target in successors.get(current, []):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
        ready.sort(key=key)
    placed = set(result)
    return result + sorted(cards - placed, key=key)


def blocked_by(card_ids, pairs, satisfied):
    """`{card: [predecessor, …]}` of predecessors not yet satisfied (merged + written back, or legacy done)."""
    cards = set(card_ids)
    result = {card: set() for card in cards}
    for source, target in pairs:
        if target in cards and source not in satisfied:
            result[target].add(source)
    return {card: sorted(values) for card, values in result.items()}
