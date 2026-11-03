"""Záměr stránky jako nástroj srdce (`opora_heart.py intent`, docs/navrhy/2026-11-03-platno-2-zamer-stranky.md §4).

Jen standardní knihovna. Nástroj sem předá sám sebe (`tool`): `call` s tokenem srdce, `Failure`, `env`. Záměr je
workflow `page_intent` s `owner_ref = opora:page:<PAGE>` v `/api/flow/*`:
- `show PAGE` vypíše aktivní a kandidátní verzi kompaktně (uzel `id · typ · klíč=hodnota`, vazba `a.port → b.port`);
- `propose PAGE --file F` uloží graf ze souboru jako draft a navrhne ho kandidátem (workflow založí, když chybí);
  `--dry-run` graf jen ověří (`POST /api/flow/graph-check`) a nic nezapíše. Schvaluje jen člověk v UI;
- `diff PAGE` porovná aktivní a kandidátní verzi po uzlech (přidané, odebrané, změněné) a vazbách.
Dávka srdce (`command.py`) soubor kopíruje do `brain/` vedle `opora_heart.py`.
"""
import json
from pathlib import Path
from urllib.parse import quote

KIND = "page_intent"
PARAM = 80  # znaků hodnoty parametru ve výpisu


def _workflow(tool, page):
    found = tool.call("GET", "/api/flow/workflows", query={"project": tool.env("OPORA_PROJECT"), "kind": KIND,
                                                           "owner_ref": f"opora:page:{page}"})["workflows"]
    return found[0] if found else None


def _versions(tool, workflow):
    """`(aktivní, poslední kandidát)` workflow; chybějící = None."""
    if workflow is None:
        return None, None
    versions = tool.call("GET", f"/api/flow/workflows/{quote(workflow['id'], safe='')}/versions")["versions"]
    active = next((v for v in versions if v["status"] == "active"), None)
    candidate = next((v for v in reversed(versions) if v["status"] == "candidate"), None)
    return active, candidate


def _value(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= PARAM else text[: PARAM - 1] + "…"


def _node(node):
    params = "; ".join(f"{key}={_value(value)}" for key, value in (node.get("params") or {}).items())
    return f"{node['id']} · {node.get('type')}" + (f" · {params}" if params else "")


def _edge(edge):
    data = " (data)" if edge.get("kind", "main") != "main" else ""
    return f"{edge.get('source_node')}.{edge.get('source_port')} → {edge.get('target_node')}.{edge.get('target_port')}{data}"


def _compact(version):
    if version is None:
        return None
    graph = version["graph"]
    return {"versionId": version["id"], "n": version["n"], "nodes": [_node(n) for n in graph.get("nodes") or []],
            "edges": [_edge(e) for e in graph.get("edges") or []]}


def show(tool, page):
    workflow = _workflow(tool, page)
    active, candidate = _versions(tool, workflow)
    return {"page": page, "workflowId": workflow["id"] if workflow else None, "active": _compact(active),
            "candidate": _compact(candidate)}


def _graph(tool, path):
    try:
        graph = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise tool.Failure({"error": f"Soubor záměru {path} nejde přečíst: {error}", "code": "intent_file",
                            "hint": "Soubor je JSON grafu {nodes, edges} s typy intent.* (GET /api/flow/node-types?kind=page_intent)."}) from None
    return graph.get("graph", graph) if isinstance(graph, dict) else graph


def propose(tool, page, path, dry_run):
    graph = _graph(tool, path)
    if dry_run:
        return {"dryRun": True, **tool.call("POST", "/api/flow/graph-check", {"kind": KIND, "graph": graph})}
    workflow = _workflow(tool, page) or tool.call("POST", "/api/flow/workflows", {
        "kind": KIND, "name": f"Záměr stránky {page}", "project_id": tool.env("OPORA_PROJECT"),
        "owner_ref": f"opora:page:{page}"})
    draft = tool.call("POST", f"/api/flow/workflows/{quote(workflow['id'], safe='')}/versions", {"graph": graph})
    candidate = tool.call("POST", f"/api/flow/versions/{quote(draft['id'], safe='')}/candidate", {})
    return {"page": page, "workflowId": workflow["id"], "versionId": candidate["id"], "n": candidate["n"],
            "status": candidate["status"], "next": "kandidáta schválí nebo zamítne člověk v UI"}


def diff(tool, page):
    active, candidate = _versions(tool, _workflow(tool, page))
    if candidate is None:
        raise tool.Failure({"error": f"Stránka {page} nemá kandidáta záměru.", "code": "intent_no_candidate",
                            "hint": "Navrhni ho: python opora_heart.py intent propose PAGE --file F."})
    old = {n["id"]: n for n in (active["graph"].get("nodes") if active else None) or []}
    new = {n["id"]: n for n in candidate["graph"].get("nodes") or []}
    old_edges = {_edge(e) for e in (active["graph"].get("edges") if active else None) or []}
    new_edges = {_edge(e) for e in candidate["graph"].get("edges") or []}
    changed = [f"{_node(old[key])} ⇒ {_node(new[key])}" for key in new
               if key in old and (old[key].get("type"), old[key].get("params")) != (new[key].get("type"), new[key].get("params"))]
    return {"page": page, "activeN": active["n"] if active else None, "candidateN": candidate["n"],
            "nodesAdded": [_node(new[key]) for key in new if key not in old],
            "nodesRemoved": [_node(old[key]) for key in old if key not in new], "nodesChanged": changed,
            "edgesAdded": sorted(new_edges - old_edges), "edgesRemoved": sorted(old_edges - new_edges)}


def intent(args, tool):
    if args.action == "show":
        return show(tool, args.page)
    if args.action == "propose":
        return propose(tool, args.page, args.file, args.dry_run)
    return diff(tool, args.page)
