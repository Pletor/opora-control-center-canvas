"""Zadání pro agenta z plátna procesu (`docs/navrhy/2026-11-04-platno-procesu.md` §6): čistá deterministická funkce,
žádný model. Text se generuje z grafu pokaždé znovu, pravda o chování je plátno. Kroky řadí průchod grafem od startů
(uzlů bez vstupní hrany), vrstvu uzlu bere `simulate.node_layer`, případy přehrává `simulate.simulate`.
"""

import json
from collections import deque

from backend.flow.graph_check import FlowInvalid
from backend.flow.node_types import catalog
from backend.flow.simulate import KIND, node_layer, simulate

LAYER_TITLES = (("fe", "Frontend"), ("be", "Backend"), ("db", "Databáze"), ("infra", "Infrastruktura"),
                ("ai", "AI"), ("neutral", "Ostatní"))
SKIP_PARAMS = {"title", "description"}
FOOTER = "Odchylku od plátna hlaste, plátno se nemění tiše."


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def _title(node):
    return (node.get("params") or {}).get("title") or node.get("notes") or node["id"]


def _order(nodes, edges):
    """Id uzlů v pořadí průchodu do šířky od startů; nedosažitelné uzly na konec v pořadí plátna."""
    out, seen = {}, set()
    for e in edges:
        out.setdefault(e["source_node"], []).append(e["target_node"])
    ids = [n["id"] for n in nodes]
    targets = {e["target_node"] for e in edges}
    queue, order = deque(i for i in ids if i not in targets), []
    while queue:
        nid = queue.popleft()
        if nid not in seen:
            seen.add(nid)
            order.append(nid)
            queue.extend(out.get(nid, []))
    return order + [i for i in ids if i not in seen]


def _steps(order, by_id, types):
    lines = []
    for key, title in LAYER_TITLES:
        rows = []
        for nid in order:
            node = by_id[nid]
            if node_layer(node, types) != key:
                continue
            params = node.get("params") or {}
            line = f"- **{_title(node)}** (`{node['type']}`, `{nid}`)"
            extra = [f"{k}: {v if isinstance(v, str) else _json(v)}" for k, v in params.items()
                     if k not in SKIP_PARAMS and v not in (None, "", [])]
            if extra:
                line += " – " + "; ".join(extra)
            if desc := params.get("description"):
                line += f". {desc}"
            rows.append(line)
        if rows:
            lines += [f"\n### {title}", *rows]
    return lines


def _interface(order, by_id, edges):
    lines = []
    for nid in order:
        node = by_id[nid]
        if node["type"] != "be.endpoint":
            continue
        params = node.get("params") or {}
        into = next((e["data"] for e in edges if e["target_node"] == nid and (e.get("data") or {}).get("schema")), {})
        outof = next((e["data"] for e in edges if e["source_node"] == nid and (e.get("data") or {}).get("schema")), {})
        lines.append(f"- `{params.get('method', 'GET')} {params.get('path', '/')}` ({_title(node)})")
        for label, schema in (("vstup", node.get("inputSchema") or params.get("body") or into.get("schema")),
                              ("výstup", node.get("outputSchema") or params.get("response") or outof.get("schema"))):
            if schema:
                lines.append(f"  - {label}: `{_json(schema)}`")
    return lines


def _data(order, by_id, edges):
    lines = []
    for nid in order:
        node = by_id[nid]
        params = node.get("params") or {}
        if node["type"] in ("db.read", "db.write") and params.get("table"):
            verb = "čte" if node["type"] == "db.read" else "zapisuje"
            cols = params.get("columns")
            lines.append(f"- Tabulka `{params['table']}` {verb} ({_title(node)})" +
                         (f", sloupce: {', '.join(f'`{c}`' for c in cols)}" if cols else ""))
    for e in edges:
        data = e.get("data") or {}
        if data.get("kind"):
            line = f"- Hrana {e['source_node']} → {e['target_node']}: druh `{data['kind']}`"
            line += "".join(f", {name} `{_json(data[key])}`" for key, name in (("schema", "schéma"), ("example", "příklad"))
                            if data.get(key))
            lines.append(line)
    return lines


def _errors(order, by_id, edges):
    lines = [f"- {_title(by_id[i])} (`{i}`): onError `{by_id[i]['onError']}`" for i in order
             if by_id[i].get("onError", "stop") != "stop"]
    bad = [e for e in edges if e.get("source_port") in ("false", "error")]
    lines += [f"- {_title(by_id[e['source_node']])}: výstup `{e['source_port']}` vede na {_title(by_id[e['target_node']])}"
              for e in bad]
    after, queue = set(), deque(e["target_node"] for e in bad)
    while queue:
        nid = queue.popleft()
        if nid not in after:
            after.add(nid)
            queue.extend(e["target_node"] for e in edges if e["source_node"] == nid)
    lines += [f"- Chybová zpráva ve FE: {_title(by_id[i])} – {(by_id[i].get('params') or {}).get('message', '')}"
              for i in order if i in after and by_id[i]["type"] == "fe.notify"]
    return lines


def _cases(graph, by_id):
    lines = []
    for case in graph.get("cases") or []:
        lines.append(f"\n### {case.get('name') or case['id']} (`{case['id']}`)")
        lines.append(f"- Vstup: `{_json(case.get('input'))}`")
        if case.get("expect"):
            lines.append(f"- Očekávání: `{_json(case['expect'])}`")
        try:
            sim = simulate(graph, case=case)
        except FlowInvalid as error:
            lines.append(f"- Simulace: nešla spustit ({error})")
            continue
        verdict = "bez očekávání" if sim["expect"] is None else "shoda" if sim["expect"]["ok"] else "NESHODA"
        lines.append(f"- Simulace: {verdict}" + (" – " + "; ".join(sim["expect"]["diffs"]) if verdict == "NESHODA" else ""))
        lines.append("- Trasa: " + ", ".join(f"{s['layer']}: {_title(by_id[s['nodeId']])}" for s in sim["trace"]))
    return lines


def brief(workflow, version, graph):
    """`{markdown, sections}`; prázdné sekce chybí, graf bez uzlů je `FlowInvalid` (422)."""
    nodes, edges = graph.get("nodes") or [], graph.get("edges") or []
    if not nodes:
        raise FlowInvalid("Plátno nemá žádné kroky.")
    by_id, types = {n["id"]: n for n in nodes}, catalog(KIND)
    order = _order(nodes, edges)
    ref = f"{workflow['ownerRef']}@{version['n']}"
    sections = {
        "Cíl": [f"**{workflow['title']}**", *([workflow["description"]] if workflow.get("description") else [])],
        "Kroky po vrstvách": _steps(order, by_id, types),
        "Rozhraní": _interface(order, by_id, edges),
        "Data": _data(order, by_id, edges),
        "Chybové stavy": _errors(order, by_id, edges),
        "Případy jako testy": _cases(graph, by_id),
        "Odkaz zpět": [f"`{ref}`", f"Zadání vzniklo z plátna {ref}. {FOOTER}"],
    }
    sections = {name: lines for name, lines in sections.items() if lines}
    markdown = "\n\n".join(f"## {name}\n\n" + "\n".join(lines).lstrip("\n") for name, lines in sections.items())
    return {"markdown": f"# Zadání: {workflow['title']}\n\n{markdown}\n", "sections": sections}
