"""Validace grafu workflow: uzly mají známý typ, hrany vedou mezi existujícími porty a kind hrany sedí s porty.

Graf: `{"nodes": [{id, type, type_version, params, position, pinned_output}],
"edges": [{id, source_node, source_port, target_node, target_port, kind, label}]}`.
Záměr stránky (`kind = page_intent`) navíc musí mít aspoň jeden `intent.entry` a jeden `intent.done`.
"""

from collections import Counter

from backend.flow.catalogs.page_intent import REQUIRED_TYPES
from backend.flow.node_types import NODE_TYPES, PORT_KINDS


class FlowInvalid(ValueError):
    """Graf nebo požadavek neodpovídá kontraktu toku (HTTP 422)."""


def graph_errors(graph, registry=NODE_TYPES, kind=None):
    """Vrátí seznam chyb grafu; prázdný seznam = graf je platný."""
    if not isinstance(graph, dict):
        return ["Graf musí být objekt s nodes a edges."]
    nodes, edges = graph.get("nodes"), graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["nodes a edges musí být seznamy."]
    errors, types = [], {}
    for node in nodes:
        nid = node.get("id") if isinstance(node, dict) else None
        if not isinstance(nid, str) or not nid:
            errors.append("Uzel nemá id.")
        elif nid in types:
            errors.append(f"Uzel {nid} je v grafu dvakrát.")
        elif node.get("type") not in registry:
            errors.append(f"Uzel {nid} má neznámý typ {node.get('type')!r}.")
        else:
            types[nid] = registry[node["type"]]
    seen, usage = set(), Counter()
    for edge in edges:
        eid = edge.get("id") if isinstance(edge, dict) else None
        if not isinstance(eid, str) or not eid or eid in seen:
            errors.append(f"Hrana {eid!r} nemá jedinečné id.")
            continue
        seen.add(eid)
        kind = edge.get("kind", "main")
        if kind not in PORT_KINDS:
            errors.append(f"Hrana {eid} má neznámý kind {kind!r}.")
            continue
        ends = (("source", "out"), ("target", "in"))
        for end, direction in ends:
            node_id, port_name = edge.get(f"{end}_node"), edge.get(f"{end}_port")
            node_type = types.get(node_id)
            port = node_type.port(port_name, direction) if node_type else None
            if node_type is None:
                errors.append(f"Hrana {eid} vede na neexistující uzel {node_id!r}.")
            elif port is None:
                errors.append(f"Hrana {eid}: uzel {node_id} nemá {direction} port {port_name!r}.")
            elif port.kind != kind:
                errors.append(f"Hrana {eid} je {kind}, ale port {node_id}.{port_name} je {port.kind}.")
            else:
                usage[(node_id, port_name, direction, port.cardinality)] += 1
    for (node_id, port_name, direction, cardinality), count in usage.items():
        if cardinality == "one" and count > 1:
            errors.append(f"Port {node_id}.{port_name} ({direction}) nese jen jednu hranu, má {count}.")
    if kind == "page_intent":
        present = {t.type for t in types.values()}
        errors += [f"Záměr stránky potřebuje aspoň jeden uzel {t}." for t in REQUIRED_TYPES if t not in present]
    return errors


def check_graph(graph, registry=NODE_TYPES, kind=None):
    errors = graph_errors(graph, registry, kind)
    if errors:
        raise FlowInvalid("; ".join(errors))
