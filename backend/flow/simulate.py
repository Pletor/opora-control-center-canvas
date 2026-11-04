"""Simulátor procesu na plátně (`docs/navrhy/2026-11-04-platno-procesu.md` §4): jeden čistý výpočet pro člověka, LLM
i testy. Graf a případ přijdou jako JSON, nic se nespouští doopravdy (žádná síť, soubor ani SQL) a nic se nezapisuje.

Trasa je fronta kroků od `case.start`: každý krok má vstup, výstup, případně pravidlo a větev; hrany se řídí
výstupním portem (`branch`, bez něj všechny kromě `error`). Chyba kroku zastaví trasu, ledaže uzel má `onError`
`errorOutput` (jde výstupem `error`) nebo `continue`. Tvrdé limity: 200 kroků, 20 tabulek × 200 řádků.
"""

from collections import defaultdict, deque
from copy import deepcopy

from backend.flow.cases import case_errors
from backend.flow.graph_check import FlowInvalid
from backend.flow.node_types import catalog
from backend.flow.simulate_steps import run_step

MAX_STEPS, MAX_TABLES, MAX_ROWS = 200, 20, 200
KIND = "library_flow"


def _inputs(graph, case_id, case):
    """Ověří tvar vstupu a vrátí `(uzly podle id, případ)`; chyby jsou `FlowInvalid` (422)."""
    nodes, edges = (graph or {}).get("nodes"), (graph or {}).get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list) or not all(isinstance(x, dict) for x in nodes + edges):
        raise FlowInvalid("Graf musí mít nodes a edges jako seznamy objektů.")
    if bad := [n for n in nodes if not isinstance(n.get("id"), str) or not isinstance(n.get("type"), str)]:
        raise FlowInvalid(f"Uzel {bad[0].get('id')!r} nemá id a typ.")
    if (case_id is None) == (case is None):
        raise FlowInvalid("Zadejte právě jedno z caseId a case.")
    if case is None:
        case = next((c for c in graph.get("cases") or [] if isinstance(c, dict) and c.get("id") == case_id), None)
        if case is None:
            raise FlowInvalid(f"Graf nemá případ {case_id!r}.")
    by_id = {n["id"]: n for n in nodes}
    errors = case_errors([case], by_id.keys())
    tables = (case.get("env") or {}).get("tables") or {} if not errors else {}
    if len(tables) > MAX_TABLES or any(len(rows) > MAX_ROWS for rows in tables.values()):
        errors.append(f"Případ smí mít nejvýš {MAX_TABLES} tabulek po {MAX_ROWS} řádcích.")
    if errors:
        raise FlowInvalid("; ".join(errors))
    return by_id, case


def node_layer(node, types):
    """Vrstva uzlu: vlastní `layer`, jinak výchozí z katalogu, jinak `neutral`."""
    return node.get("layer") or (types[node["type"]].layer if node["type"] in types else "neutral")


def _step(index, node, layer, data, via, result):
    entry = {"step": index, "nodeId": node["id"], **({"edgeId": via} if via else {}), "layer": layer,
             "type": node["type"], "in": data, **({"rule": result["rule"]} if result.get("rule") else {}),
             "out": result.get("out"), **({"branch": result["branch"]} if result.get("branch") else {}),
             "note": result.get("note", "")}
    return {**entry, "error": result["error"]} if result.get("error") else entry


def simulate(graph, case_id=None, case=None):
    """Přehraje případ: `{ok, result, trace, expect, tables, notify}` (`expect` je null bez očekávání)."""
    nodes, case = _inputs(graph, case_id, case)
    types, env = catalog(KIND), case.get("env") or {}
    tables, services = deepcopy(env.get("tables") or {}), env.get("services") or {}
    out_edges = defaultdict(list)
    for edge in graph.get("edges", []):
        if edge.get("target_node") in nodes:
            out_edges[edge.get("source_node")].append(edge)
    queue, trace, notify = deque([(case["start"], deepcopy(case["input"]), None)]), [], None
    while queue:
        node_id, data, via = queue.popleft()
        node = nodes[node_id]
        layer = node_layer(node, types)
        if len(trace) >= MAX_STEPS:
            trace.append(_step(len(trace) + 1, node, layer, data, via, {"error": f"Překročen limit {MAX_STEPS} kroků trasy."}))
            break
        result = run_step(node, data, tables, services)
        on_error = node.get("onError", "stop")
        if result.get("error") and on_error == "errorOutput":
            base = data if isinstance(data, dict) else {"value": data}
            result = {**result, "out": {**base, "error": result["error"]}, "branch": "error"}
        elif result.get("error") and on_error == "continue":
            result = {**result, "out": data}
        elif result.get("notify"):
            notify = result["note"]
        branch = result.get("branch")
        followed = [e for e in out_edges[node_id] if (e.get("source_port") == branch if branch else e.get("source_port") != "error")]
        if node["type"] == "be.validate" and branch == "false" and not followed:
            result = {**result, "error": "validace neprošla"}
        trace.append(_step(len(trace) + 1, node, layer, data, via, result))
        if result.get("error") and on_error == "stop":
            break
        queue.extend((e["target_node"], result["out"], e.get("id")) for e in followed)
    out = trace[-1]["out"] if trace else None
    return {"ok": not any("error" in s for s in trace), "result": out, "trace": trace, "tables": tables,
            "notify": notify, "expect": _compare(case.get("expect"), out, trace, tables, notify)}


def _compare(expect, result, trace, tables, notify):
    if not expect:
        return None
    diffs = []
    if "result" in expect and expect["result"] != result:
        diffs.append(f"Výsledek: čekáno {expect['result']!r}, vyšlo {result!r}.")
    if "path" in expect and expect["path"] != (path := [s["nodeId"] for s in trace]):
        diffs.append(f"Cesta: čekáno {' → '.join(expect['path'])}, prošlo {' → '.join(path)}.")
    diffs += [f"Tabulka {name}: čekáno {rows!r}, v tabulce je {tables.get(name, [])!r}."
              for name, rows in (expect.get("rows") or {}).items() if tables.get(name, []) != rows]
    if "notify" in expect and expect["notify"] != notify:
        diffs.append(f"Notifikace: čekáno {expect['notify']!r}, vyšlo {notify!r}.")
    return {"ok": not diffs, "diffs": diffs}
