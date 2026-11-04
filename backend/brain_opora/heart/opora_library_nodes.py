"""Kreslení do draftu plátna toku v nástroji srdce: `library nodes add|set|connect` (kontrakt
`docs/navrhy/2026-11-04-platno-procesu.md` §1b). Jen standardní knihovna, volá ho `opora_library.py` (`tool` = nástroj).

Verze jsou neměnné, proto každá změna uloží NOVÝ draft z nejnovějšího draftu (jinak z aktivní verze, u prázdného plátna
z prázdného grafu); pás návrhu na plátně ukazuje nejnovější draft proti aktivní verzi. Graf se před uložením ověří
(`graph-check`): chyba se vrátí a nic se neuloží. Oprávnění jako `propose`: do plátna člověka jen draft (aktivuje člověk).
Výstup nese `nodeId` / `edgeId`, `versionId`, `n`.
"""
import json
import re

KIND = "library_flow"
LAYERS = ("fe", "be", "db", "infra", "ai", "neutral")  # pořadí pruhů shora dolů
# Zrcadlí frontend `flow-editor/flow-lanes/logic/lanes.ts` a `logic/frame-view.ts` (SIZE.main, GAP): karta 76×116, mezera 70.
CARD_W, CARD_H, GAP = 76, 116, 70
NODE_FIELDS = ("params", "notes", "notesInFlow", "inputSchema", "outputSchema", "example", "layer", "mode", "onError",
               "retry")
LIBRARY_HINT = "Uzly vypíše: python opora_heart.py library get FLOW."


def _q(value):
    return re.sub(r"[^\w.-]", "", str(value))


def _fail(tool, error, code, **extra):
    raise tool.Failure({"error": error, "code": code, **extra})


def _base(tool, flow_id):
    """Graf, ze kterého se vychází: nejnovější draft, jinak aktivní verze, jinak prázdný graf (+ ta verze)."""
    versions = tool.call("GET", f"/api/library/flows/{_q(flow_id)}")["versions"]
    drafts = [v for v in versions if v["status"] == "draft"]
    source = drafts[-1] if drafts else next((v for v in versions if v["status"] == "active"), None)
    graph = (source or {}).get("graph") or {}
    return {**graph, "nodes": list(graph.get("nodes") or []), "edges": list(graph.get("edges") or [])}, source


def _save(tool, flow_id, graph, source, note, result):
    checked = tool.call("POST", "/api/flow/graph-check", {"kind": KIND, "graph": graph})
    if not checked["ok"]:
        _fail(tool, "Graf neprošel kontrolou, draft se nezměnil.", "library_graph_check", errors=checked["errors"],
              hint="Typy a vrstvy: GET /api/flow/node-types?kind=library_flow.")
    body = {"graph": graph, "note": note, **({"parent_version_id": source["id"]} if source else {})}
    draft = tool.call("POST", f"/api/flow/workflows/{_q(flow_id)}/versions", body)
    return {"flowId": flow_id, **result, "versionId": draft["id"], "n": draft["n"], "status": draft["status"],
            "next": "návrh přijme nebo zamítne člověk na plátně; zkontroluj: python opora_heart.py library get FLOW"}


def _position(graph, after, layer):
    """x za uzlem `after` (jinak za nejpravějším uzlem), y podle pruhu vrstvy: FE → BE → DB → Infra → AI → ostatní."""
    anchor = (next((n for n in graph["nodes"] if n["id"] == after), None) if after else
              max(graph["nodes"], key=lambda n: (n.get("position") or {}).get("x", 0), default=None))
    x = (anchor.get("position") or {}).get("x", 0) + CARD_W + GAP if anchor else 0
    return {"x": x, "y": LAYERS.index(layer) * (CARD_H + GAP)}


def _unique(prefix, taken):
    return next(f"{prefix}-{i}" for i in range(1, len(taken) + 2) if f"{prefix}-{i}" not in taken)


def add(tool, args):
    graph, source = _base(tool, args.flow)
    types = {t["type"]: t for t in tool.call("GET", "/api/flow/node-types", query={"kind": KIND})["node_types"]}
    if args.type not in types:
        _fail(tool, f"Neznámý typ uzlu {args.type!r}.", "library_node_type",
              hint="Typy a kdy je použít: GET /api/flow/node-types?kind=library_flow (use / avoid / intents).")
    if args.after and args.after not in {n["id"] for n in graph["nodes"]}:
        _fail(tool, f"Uzel --after {args.after!r} v grafu není.", "library_node_missing", hint=LIBRARY_HINT)
    layer = args.layer or types[args.type]["layer"]
    if layer not in LAYERS:
        _fail(tool, f"Vrstva {layer!r} neexistuje.", "library_layer", hint="Vrstvy: " + ", ".join(LAYERS) + ".")
    params = tool.read_json(args.params, "library_params", "--params je JSON objekt (nebo @soubor.json).") \
        if args.params else {}
    if args.branches:
        params["branches"] = [b.strip() for b in args.branches.split(",") if b.strip()]
    node = {"id": _unique(_q(args.type).replace(".", "-"), {n["id"] for n in graph["nodes"]}), "type": args.type,
            "type_version": 1, "params": params}
    if args.title and args.type == "custom.step":
        params["title"] = args.title
    elif args.title:
        node.update(notes=args.title, notesInFlow=True)
    if args.layer or args.type == "custom.step":
        node["layer"] = layer
    node["position"] = _position(graph, args.after, layer)
    graph["nodes"].append(node)
    return _save(tool, args.flow, graph, source, f"Srdce: přidán uzel {node['id']}", {"nodeId": node["id"]})


def set_node(tool, args):
    graph, source = _base(tool, args.flow)
    patch = tool.read_json("@" + args.file, "library_node_file", "--file je JSON objekt se změnou uzlu.")
    if set(patch) - set(NODE_FIELDS):
        _fail(tool, f"Měnit jde jen {', '.join(NODE_FIELDS)}.", "library_node_fields")
    if args.node not in {n["id"] for n in graph["nodes"]}:
        _fail(tool, f"Uzel {args.node!r} v grafu není.", "library_node_missing", hint=LIBRARY_HINT)
    graph["nodes"] = [{**n, **patch} if n["id"] == args.node else n for n in graph["nodes"]]
    return _save(tool, args.flow, graph, source, f"Srdce: změněn uzel {args.node}", {"nodeId": args.node})


def connect(tool, args):
    graph, source = _base(tool, args.flow)
    ids = {n["id"] for n in graph["nodes"]}
    missing = [i for i in (args.src, args.to) if i not in ids]
    if missing:
        _fail(tool, f"Uzly {', '.join(missing)} v grafu nejsou.", "library_node_missing", hint=LIBRARY_HINT)
    edge = {"id": _unique("e", {e["id"] for e in graph["edges"]}), "source_node": args.src,
            "source_port": args.from_port, "target_node": args.to, "target_port": args.to_port, "kind": "main"}
    edge.update({"via": args.via} if args.via else {})
    if args.kind:
        edge["data"] = {"kind": args.kind}
        for key in ("schema", "example"):
            if getattr(args, key) is not None:
                try:
                    edge["data"][key] = json.loads(getattr(args, key))
                except ValueError:
                    _fail(tool, f"--{key} musí být JSON.", f"library_edge_{key}")
    graph["edges"].append(edge)
    return _save(tool, args.flow, graph, source, f"Srdce: hrana {args.src} → {args.to}", {"edgeId": edge["id"]})


def nodes(tool, args):
    return {"add": add, "set": set_node, "connect": connect}[args.op](tool, args)
