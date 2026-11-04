"""Knihovna pláten toku jako nástroj srdce (`opora_heart.py library`, kontrakt
`docs/navrhy/2026-11-04-knihovna-platna-toku.md` §5).

Jen standardní knihovna. Nástroj sem předá sám sebe (`tool`): `call` s tokenem srdce, `Failure`. Knihovna je globální
(`/api/library`, verze přes `/api/flow/*`):
- `show [--owner human|agent] [--folder SLUG]` vypíše složky s plátny (titulek, popis, aktivní verze, rodokmen,
  `learnedFrom`), prázdné složky jen slugem;
- `get FLOW [--version N]` vypíše graf aktivní (nebo zadané) verze `{nodes, edges, notes, groups, cases}` a seznam verzí;
- `brief FLOW [--version N]` vypíše jako markdown zadání pro agenta vygenerované z plátna (kroky po vrstvách, rozhraní,
  data, chybové stavy, případy jako testy s výsledkem simulace, odkaz zpět `opora:library:…@N`); nic neukládá;
- `save --folder SLUG --slug SLUG --title T --file F [--learned-from JSON]` uloží plátno do knihovny AGENTA: složku
  a plátno založí, když chybí, graf ověří (`graph-check`; chyba = nic se neuloží), uloží draft s `learnedFrom`
  a aktivuje ho;
- `propose FLOW --file F [--note N]` uloží k plátnu ČLOVĚKA draft s poznámkou; přijme (aktivuje) ho nebo zamítne
  člověk na plátně. Aktivovat v knihovně člověka srdce nesmí;
- `nodes add|set|connect FLOW …` kreslí do draftu plátna po uzlech (`opora_library_nodes.py`);
- `case add FLOW --file case.json` přidá případ do nového draftu, `case run FLOW --case ID` přehraje případ (simulace,
  trasa a shoda s `expect`; `opora_library_nodes.py`).
Dávka srdce (`command.py`) soubor kopíruje do `brain/` vedle `opora_heart.py`.
"""
import json
from pathlib import Path
from urllib.parse import quote

KIND = "library_flow"
GRAPH_HINT = ("Soubor je JSON grafu {nodes, edges, notes?, groups?} s typy katalogu toků dat "
              "(GET /api/flow/node-types?kind=library_flow); vzor: python opora_heart.py library get FLOW.")


def _q(value):
    return quote(value, safe="")


def _flow(flow):
    out = {"id": flow["id"], "slug": flow["slug"], "title": flow["title"], "activeN": flow["activeN"]}
    for key in ("description", "derivedFrom", "learnedFrom"):
        if flow.get(key):
            out[key] = flow[key]
    if flow.get("derivedCount"):
        out["derivedCount"] = flow["derivedCount"]
    return out


def show(tool, owner, folder):
    parts = [owner] if owner else ["human", "agent"]
    out = {}
    for part in parts:
        folders = [f for f in tool.call("GET", "/api/library", query={"owner": part})["folders"]
                   if not folder or f["slug"] == folder]
        out[part] = {"folders": [{"slug": f["slug"], "title": f["title"], "flows": [_flow(x) for x in f["flows"]]}
                                 for f in folders if f["flows"]],
                     "empty": [f["slug"] for f in folders if not f["flows"]]}
    return out


def get(tool, flow_id, n):
    detail = tool.call("GET", f"/api/library/flows/{_q(flow_id)}")
    versions = detail["versions"]
    version = (next((v for v in versions if v["n"] == n), None) if n is not None else
               next((v for v in versions if v["status"] == "active"), None) or (versions[-1] if versions else None))
    if version is None:
        raise tool.Failure({"error": f"Plátno {flow_id} nemá verzi {n if n is not None else '(žádnou)'}.",
                            "code": "library_no_version", "hint": "Verze vypíše: python opora_heart.py library get FLOW."})
    graph = version["graph"]
    return {"id": detail["id"], "title": detail["title"], "ownerRef": detail["ownerRef"], "n": version["n"],
            "status": version["status"], "meta": version.get("meta"),
            "graph": {key: graph.get(key) or [] for key in ("nodes", "edges", "notes", "groups", "cases")},
            "versions": [f"v{v['n']} {v['status']}" + (f" · {v['meta']['note']}" if (v.get("meta") or {}).get("note")
                                                       else "") for v in versions]}


def _graph(tool, path):
    try:
        graph = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise tool.Failure({"error": f"Soubor grafu {path} nejde přečíst: {error}", "code": "library_file",
                            "hint": GRAPH_HINT}) from None
    graph = graph.get("graph", graph) if isinstance(graph, dict) else graph
    checked = tool.call("POST", "/api/flow/graph-check", {"kind": KIND, "graph": graph})
    if not checked["ok"]:
        raise tool.Failure({"error": "Graf neprošel kontrolou, nic se neuložilo.", "code": "library_graph_check",
                            "errors": checked["errors"], "hint": GRAPH_HINT})
    return graph


def _learned(tool, raw):
    if raw is None:
        return None
    return tool.read_json(raw, "library_learned_from", 'JSON {"project": "<id>", "card": "<id>", "result": '
                                                       '"verified|delivered|failed"} (nebo @soubor.json).')


def save(tool, args):
    graph = _graph(tool, args.file)
    learned = _learned(tool, args.learned_from)
    folders = tool.call("GET", "/api/library", query={"owner": "agent"})["folders"]
    folder = next((f for f in folders if f["slug"] == args.folder), None)
    if folder is None:
        human = tool.call("GET", "/api/library", query={"owner": "human"})["folders"]
        title = next((f["title"] for f in human if f["slug"] == args.folder), args.folder)
        folder = {**tool.call("POST", "/api/library/folders", {"owner": "agent", "slug": args.folder, "title": title}),
                  "flows": []}
    flow = next((f for f in folder["flows"] if f["slug"] == args.slug), None)
    created = flow is None
    if created:
        flow = tool.call("POST", "/api/library/flows", {"folder": folder["id"], "slug": args.slug, "title": args.title})
    body = {"graph": graph, **({"learnedFrom": learned} if learned else {})}
    draft = tool.call("POST", f"/api/flow/workflows/{_q(flow['id'])}/versions", body)
    tool.call("POST", f"/api/flow/versions/{_q(draft['id'])}/candidate", {})
    active = tool.call("POST", f"/api/flow/versions/{_q(draft['id'])}/activate", {})
    return {"flowId": flow["id"], "ownerRef": f"opora:library:agent:{args.folder}/{args.slug}", "created": created,
            "versionId": active["id"], "n": active["n"], "status": active["status"], "learnedFrom": learned}


def propose(tool, flow_id, path, note):
    detail = tool.call("GET", f"/api/library/flows/{_q(flow_id)}")
    if not detail["ownerRef"].startswith("opora:library:human:"):
        raise tool.Failure({"error": f"Plátno {flow_id} není v knihovně člověka.", "code": "library_not_human",
                            "hint": "Do knihovny agenta piš rovnou: python opora_heart.py library save …"})
    graph = _graph(tool, path)
    draft = tool.call("POST", f"/api/flow/workflows/{_q(flow_id)}/versions",
                      {"graph": graph, **({"note": note} if note else {})})
    return {"flowId": flow_id, "versionId": draft["id"], "n": draft["n"], "status": draft["status"],
            "next": "návrh přijme (aktivuje) nebo zamítne člověk na plátně toku"}


def brief(tool, flow_id, n):
    """Markdown zadání pro agenta z plátna (`GET /api/library/flows/{id}/brief`), vypsaný jako text."""
    return tool.call("GET", f"/api/library/flows/{_q(flow_id)}/brief",
                     query={"version": n} if n is not None else None)["markdown"]


def library(args, tool):
    if args.action == "brief":
        return brief(tool, args.flow, args.version)
    if args.action == "show":
        return show(tool, args.owner, args.folder)
    if args.action == "get":
        return get(tool, args.flow, args.version)
    if args.action == "save":
        return save(tool, args)
    if args.action in ("nodes", "case"):
        return tool.research_module("opora_library_nodes").nodes(tool, args)
    return propose(tool, args.flow, args.file, args.note)
