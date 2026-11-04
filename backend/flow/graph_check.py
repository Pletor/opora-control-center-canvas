"""Validace grafu workflow: uzly mají známý typ, hrany vedou mezi existujícími porty a kind hrany sedí s porty.

Graf: `{"nodes": [{id, type, type_version, params, position, pinned_output}],
"edges": [{id, source_node, source_port, target_node, target_port, kind, label}]}`.
Záměr stránky (`kind = page_intent`) navíc musí mít aspoň jeden `intent.entry` a jeden `intent.done`.
Plátno toku (`kind = library_flow`, `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1–§2) má porty podle `params`
uzlu (`NodeType.ports_for`), výstup `error` při `onError: errorOutput`, pole uzlu z §1, `notes[]` a `groups[]`;
kontrola hlídá povinné sub-porty, pravidla skupin a odkazy `$('<id uzlu>')`, vrstvu uzlu (`layer`) a hranu
mezi vrstvami (`via`, tvar `data`; `docs/navrhy/2026-11-04-platno-procesu.md` §1–§2). Ostatní druhy pole navíc ignorují.
"""

import re
from collections import Counter

from backend.flow.catalogs.page_intent import REQUIRED_TYPES
from backend.flow.layer_check import edge_errors
from backend.flow.node_spec import LAYERS, Port
from backend.flow.node_types import NODE_TYPES, PORT_KINDS

LIBRARY = "library_flow"
NODE_REF = re.compile(r"""\$\(\s*['"]([^'"]+)['"]\s*\)""")


class FlowInvalid(ValueError):
    """Graf nebo požadavek neodpovídá kontraktu toku (HTTP 422)."""


def graph_errors(graph, registry=NODE_TYPES, kind=None):
    """Vrátí seznam chyb grafu; prázdný seznam = graf je platný."""
    if not isinstance(graph, dict):
        return ["Graf musí být objekt s nodes a edges."]
    nodes, edges = graph.get("nodes"), graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["nodes a edges musí být seznamy."]
    errors, types, ports, valid, nodes_by_id = [], {}, {}, [], {}
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
            ports[nid] = node_ports(types[nid], node, kind)
            valid.append(node)
            nodes_by_id[nid] = node
    seen, usage, links = set(), Counter(), []
    for edge in edges:
        eid = edge.get("id") if isinstance(edge, dict) else None
        if not isinstance(eid, str) or not eid or eid in seen:
            errors.append(f"Hrana {eid!r} nemá jedinečné id.")
            continue
        seen.add(eid)
        edge_kind = edge.get("kind", "main")
        if edge_kind not in PORT_KINDS:
            errors.append(f"Hrana {eid} má neznámý kind {edge_kind!r}.")
            continue
        ends, ok = (("source", "out"), ("target", "in")), 0
        for end, direction in ends:
            node_id, port_name = edge.get(f"{end}_node"), edge.get(f"{end}_port")
            port = next((p for p in ports.get(node_id, ()) if p.name == port_name and p.direction == direction), None)
            if node_id not in types:
                errors.append(f"Hrana {eid} vede na neexistující uzel {node_id!r}.")
            elif port is None:
                errors.append(f"Hrana {eid}: uzel {node_id} nemá {direction} port {port_name!r}.")
            elif port.kind != edge_kind:
                errors.append(f"Hrana {eid} je {edge_kind}, ale port {node_id}.{port_name} je {port.kind}.")
            else:
                usage[(node_id, port_name, direction, port.cardinality)] += 1
                ok += 1
        if ok == 2:
            links.append((edge["source_node"], edge["target_node"], edge_kind))
            if kind == LIBRARY:
                errors += edge_errors(edge, nodes_by_id[edge["source_node"]], nodes_by_id[edge["target_node"]], types)
    for (node_id, port_name, direction, cardinality), count in usage.items():
        if cardinality == "one" and count > 1:
            errors.append(f"Port {node_id}.{port_name} ({direction}) nese jen jednu hranu, má {count}.")
    if kind == "page_intent":
        present = {t.type for t in types.values()}
        errors += [f"Záměr stránky potřebuje aspoň jeden uzel {t}." for t in REQUIRED_TYPES if t not in present]
    if kind == LIBRARY:
        connected = {key[:3] for key in usage}
        errors += [f"Uzel {nid}: povinný port {p.name} není připojený." for nid, found in ports.items()
                   for p in found if p.required and (nid, p.name, p.direction) not in connected]
        errors += [error for node in valid for error in _node_field_errors(node, types)]
        errors += _note_errors(graph.get("notes", [])) + _group_errors(graph.get("groups", []), types, links)
    return errors


def check_graph(graph, registry=NODE_TYPES, kind=None):
    errors = graph_errors(graph, registry, kind)
    if errors:
        raise FlowInvalid("; ".join(errors))


def node_ports(node_type, node, kind):
    """Porty uzlu podle jeho `params`; plátno toku s `onError: errorOutput` má navíc výstup `error`."""
    params = node.get("params") if isinstance(node.get("params"), dict) else {}
    found = node_type.ports_for(params)
    if kind == LIBRARY and node.get("onError") == "errorOutput":
        found = (*found, Port("error", "out", label="error"))
    return found


def _number(value, low=None):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (low is None or value >= low)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (dict, list)):
        for item in value.values() if isinstance(value, dict) else value:
            yield from _strings(item)


def _node_field_errors(node, ids):
    """Pole uzlu plátna toku (§1): popis, schémata, režim, chování při chybě a odkazy `$('<id>')` v `params`."""
    nid, retry = node["id"], node.get("retry")
    layer = [f"Uzel {nid}: layer je {' | '.join(LAYERS)}."] if node.get("layer", "be") not in LAYERS else []
    errors = layer + [f"Uzel {nid}: {field} musí být objekt (JSON Schema nebo příklad)."
                      for field in ("inputSchema", "outputSchema") if field in node and not isinstance(node[field], dict)]
    if not isinstance(node.get("notes", ""), str) or not isinstance(node.get("notesInFlow", False), bool):
        errors.append(f"Uzel {nid}: notes je text a notesInFlow pravda/nepravda.")
    if node.get("mode", "perItem") not in ("perItem", "once"):
        errors.append(f"Uzel {nid}: mode je perItem nebo once.")
    if node.get("onError", "stop") not in ("stop", "continue", "errorOutput"):
        errors.append(f"Uzel {nid}: onError je stop, continue nebo errorOutput.")
    if retry is not None and not (isinstance(retry, dict) and isinstance(retry.get("maxTries"), int)
                                  and _number(retry["maxTries"], 1) and _number(retry.get("waitMs", 0), 0)):
        errors.append(f"Uzel {nid}: retry je {{maxTries ≥ 1, waitMs ≥ 0}}.")
    if node.get("type") == "custom.step":
        params = node.get("params") if isinstance(node.get("params"), dict) else {}
        if "layer" not in node:
            errors.append(f"Uzel {nid}: krok na míru (custom.step) musí mít vrstvu (layer).")
        if not isinstance(params.get("title"), str) or not params["title"].strip():
            errors.append(f"Uzel {nid}: krok na míru (custom.step) musí mít neprázdný titulek (params.title).")
        if "branches" in params and not (isinstance(params["branches"], list)
                                         and all(isinstance(b, str) and b.strip() for b in params["branches"])):
            errors.append(f"Uzel {nid}: params.branches kroku na míru je seznam jmen větví.")
    errors += [f"Uzel {nid}: odkaz $('{ref}') vede na neexistující uzel." for text in _strings(node.get("params"))
               for ref in NODE_REF.findall(text) if ref not in ids]
    return errors


def _note_errors(notes):
    if not isinstance(notes, list):
        return ["notes musí být seznam."]
    errors, seen = [], set()
    for note in notes:
        nid = note.get("id") if isinstance(note, dict) else None
        if not isinstance(nid, str) or not nid or nid in seen:
            errors.append(f"Poznámka {nid!r} nemá jedinečné id.")
            continue
        seen.add(nid)
        if not isinstance(note.get("content", ""), str) or not all(_number(note.get(f)) for f in ("x", "y")) \
                or not all(_number(note.get(f), 1) for f in ("width", "height")):
            errors.append(f"Poznámka {nid}: content je markdown, x a y čísla, width a height kladná čísla.")
    return errors


def _group_errors(groups, types, links):
    """Skupina podle n8n Canvas Groups: souvislý řetězec, vstup do prvního a výstup z posledního uzlu, sub-hrana
    nepřekročí hranici skupiny (AI uzel je se sub-uzly), žádný spouštěč, uzel nejvýš v jedné skupině."""
    if not isinstance(groups, list):
        return ["groups musí být seznam."]
    errors, seen, owner = [], set(), {}
    for group in groups:
        gid = group.get("id") if isinstance(group, dict) else None
        if not isinstance(gid, str) or not gid or gid in seen:
            errors.append(f"Skupina {gid!r} nemá jedinečné id.")
            continue
        seen.add(gid)
        name, ids, description = group.get("name"), group.get("nodeIds"), group.get("description", "")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"Skupina {gid} nemá jméno.")
        if not isinstance(description, str) or len(description) > 145:
            errors.append(f"Skupina {gid}: popis je text do 145 znaků.")
        errors += [f"Skupina {gid}: {field} musí být objekt." for field in ("inputSchema", "outputSchema")
                   if field in group and not isinstance(group[field], dict)]
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            errors.append(f"Skupina {gid}: nodeIds je neprázdný seznam id uzlů.")
            continue
        for nid in ids:
            if nid not in types:
                errors.append(f"Skupina {gid}: uzel {nid!r} neexistuje.")
            elif nid in owner:
                errors.append(f"Uzel {nid} je ve skupině {owner[nid]} i {gid}.")
            else:
                owner[nid] = gid
                if types[nid].trigger:
                    errors.append(f"Skupina {gid}: spouštěč {nid} do skupiny nepatří.")
        errors += _chain_errors(gid, set(ids) & types.keys(), links)
    return errors


def _chain_errors(gid, members, links):
    entries = {t for s, t, kind in links if kind == "main" and t in members and s not in members}
    exits = {s for s, t, kind in links if kind == "main" and s in members and t not in members}
    errors = [f"Skupina {gid}: {what} jen {where} uzlu, vede přes {sorted(found)}."
              for what, where, found in (("vstup vede", "do prvního", entries), ("výstup vede", "z posledního", exits))
              if len(found) > 1]
    errors += [f"Skupina {gid}: sub-uzel a jeho kořenový uzel musí být ve stejné skupině ({s} → {t})."
               for s, t, kind in links if kind != "main" and (s in members) != (t in members)]
    inside = [(s, t) for s, t, _ in links if s in members and t in members]
    reached, todo = set(), [next(iter(members))] if members else []
    while todo:
        current = todo.pop()
        if current not in reached:
            reached.add(current)
            todo += [t if s == current else s for s, t in inside if current in (s, t)]
    if reached != members:
        errors.append(f"Skupina {gid}: uzly netvoří souvislý řetězec.")
    return errors
