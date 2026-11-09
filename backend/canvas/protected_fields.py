"""Struktura, kterou mění jen člověk (upgrade-opora #30).

Brána sektoru (`gateNodeId`), předepsané kontroly karty (`checks`, `goal_mode`) a vazby `next`
mezi sektory rozhodují, kdy je práce hotová a kdy se otevře další sektor. Kdyby je směl
přepsat agent přes `/api/graph` nebo dávku plánu, obešel by tím bránu i vlastní kontroly.

Nové karty a sektory, které agent sám zakládá (plánování), smí tato pole nést hned při vzniku;
chráněná je změna u toho, co už na plátně existuje.
"""

NODE_FIELDS = ("gateNodeId", "checks", "goal_mode")


def _sector_links(graph, sectors):
    return {(edge["source"], edge["target"]) for edge in graph["edges"]
            if not edge.get("relation") and edge.get("port", "next") == "next" and edge["source"] in sectors and edge["target"] in sectors}


def protected_changes(old, new):
    """Seznam lidsky chráněných změn mezi dvěma grafy; prázdný = zápis smí kdokoli."""
    changes = []
    before = {node["id"]: node for node in old["nodes"]}
    after = {node["id"]: node for node in new["nodes"]}
    for node_id, node in after.items():
        previous = before.get(node_id)
        if previous is None:
            continue
        for field in NODE_FIELDS:
            if previous.get(field) != node.get(field):
                changes.append(f"{node_id}.{field}")
        if previous["kind"] == "sector" and node["kind"] != "sector":
            changes.append(f"{node_id}.kind")
    sectors = {node_id for node_id, node in before.items() if node["kind"] == "sector"}
    for source, target in sorted(_sector_links(old, sectors) ^ _sector_links(new, sectors)):
        changes.append(f"next {source}→{target}")
    return changes
