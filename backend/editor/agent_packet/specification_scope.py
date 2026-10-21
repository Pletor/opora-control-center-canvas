"""Pure, reader-specific sparse selection. This descriptor does not prove source coverage."""

from backend.canvas.areas import area_of
from backend.editor.agent_packet.specification_context import _navigation
from backend.editor.agent_packet.specification_scope_graph import ScopeGraph

SCHEMA = "opora.specification-scope/1"
SELECTOR_VERSION = 1


def select_scope(graph, node_id):
    """Select content and state reads without traversing an entire connected component.

    IDs and typed predicates are public structural metadata, never state or card text.
    Empty results are retained so a caller can re-evaluate negative dependencies.
    """
    index = ScopeGraph(graph)
    lineage = index.lineage(node_id)
    descendants = index.descendants(node_id)
    selected, cards, gating, edges, origins = set(), set(), {node_id}, set(), {}
    predicates = []

    def add(identifiers, reason, content=True):
        for identifier in identifiers:
            index.require(identifier)
            selected.add(identifier)
            origins.setdefault(identifier, set()).add(reason)
            if content:
                cards.add(identifier)

    def ancestors(identifier, reason, content=True):
        add(index.lineage(identifier), reason, content)

    add(descendants, "target-descendant")
    add(lineage, "target-ancestor")
    predicates.append({"type": "descendants", "nodeId": node_id,
                       "nodeIds": sorted(descendants - {node_id})})
    incident = [edge for edge in index.edges
                if descendants.intersection((edge["source"], edge["target"]))]
    predicates.append({"type": "incident", "nodeIds": sorted(descendants),
                       "edgeIds": sorted(edge["id"] for edge in incident)})
    for edge in incident:
        edges.add(edge["id"])
        for endpoint in (edge["source"], edge["target"]):
            ancestors(endpoint, "incident-endpoint")

    sectors = [identifier for identifier in lineage
               if index.by_id[identifier]["kind"] == "sector"]
    incoming = [edge for edge in index.edges
                if edge["target"] in sectors and edge.get("port", "next") == "next"]
    # One record per sector also witnesses an empty incoming-edge selector.
    for identifier in sorted(sectors):
        predicates.append({"type": "incoming-next", "nodeId": identifier,
                           "edgeIds": sorted(e["id"] for e in incoming
                                             if e["target"] == identifier)})
    for edge in sorted(incoming, key=lambda item: item["id"]):
        edges.add(edge["id"])
        source_id = edge["source"]
        source = index.require(source_id)
        ancestors(source_id, "predecessor")
        gating.add(source_id)
        if source["kind"] != "sector":
            continue
        members = sorted(identifier for identifier in index.descendants(source_id)
                         if index.by_id[identifier]["kind"] == "node")
        predicates.append({"type": "predecessor-sector-members", "nodeId": source_id,
                           "nodeIds": members})
        for identifier in members:
            ancestors(identifier, "predecessor-member", content=False)
        gating.update(members)
        gate_id = source.get("gateNodeId")
        predicates.append({"type": "gate", "nodeId": source_id, "gateNodeId": gate_id})
        if gate_id:
            ancestors(gate_id, "predecessor-gate", content=False)
            gating.add(gate_id)

    # Navigation reads every page in a relevant application, in persisted array order.
    domains = set()
    for identifier in sorted(selected):
        for ancestor in index.lineage(identifier):
            if (index.by_id[ancestor].get("site") or {}).get("kind") == "application":
                domains.add(ancestor)
                break
    navigation = {item["domainId"]: item["pages"] for item in _navigation(index.nodes)}
    for domain in sorted(domains):
        pages = navigation.get(domain, [])
        predicates.append({"type": "navigation", "domainId": domain, "pages": pages})
        for page in pages:
            ancestors(page["nodeId"], "navigation", content=False)

    # Compute winners against the FULL graph. Areas supply graph context, not card reads.
    actual_nodes = set(selected)
    for identifier in sorted(actual_nodes):
        node = index.by_id[identifier]
        winner = area_of(node, index.nodes)
        candidates = sorted(other["id"] for other in index.nodes
                            if other["kind"] == "area"
                            and other.get("parentId") == node.get("parentId")
                            and area_of(node, [other]) is not None
                            ) if node["kind"] != "area" else []
        predicates.append({"type": "area-winner", "nodeId": identifier,
                           "candidateIds": candidates,
                           "areaId": winner["id"] if winner else None})
        if winner:
            ancestors(winner["id"], "area", content=False)
    for identifier in sorted(selected - actual_nodes):
        predicates.append({"type": "area-winner", "nodeId": identifier,
                           "candidateIds": [], "areaId": None})
    return {"schema": SCHEMA, "selectorVersion": SELECTOR_VERSION, "targetId": node_id,
            "nodeIds": sorted(selected), "cardIds": sorted(cards),
            "gatingIds": sorted(gating), "edgeIds": sorted(edges),
            "predicates": predicates,
            "origins": {key: sorted(origins[key]) for key in sorted(origins)}}


def project_graph(graph, selection, *, redact=True):
    """Return v1 semantics; ``redact=False`` is only for a caller's private evidence digest."""
    # Local imports keep the projection's equivalence with the existing v1 reader explicit.
    from backend.editor.agent_packet.desktop_v3_packets import redact_deep
    from backend.editor.agent_packet.specification_context import _node

    expected = select_scope(graph, selection["targetId"])
    if selection != expected:
        raise ValueError("Stale or invalid specification selection")
    index = ScopeGraph(graph)
    part = {"graph": {
        "nodes": [_node(index.by_id[identifier], index.nodes)
                  for identifier in selection["nodeIds"]],
        "edges": sorted((edge for edge in index.edges if edge["id"] in selection["edgeIds"]),
                        key=lambda edge: edge["id"]),
    }}
    domains = {item["domainId"] for item in selection["predicates"]
               if item["type"] == "navigation"}
    if domains:
        part["navigation"] = [item for item in _navigation(index.nodes)
                              if item["domainId"] in domains]
    return redact_deep(part) if redact else part
