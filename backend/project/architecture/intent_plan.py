"""Plán přehrání záměru stránky (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §6), bez modelu.

Zdroj je jen AKTIVNÍ verze workflow `page_intent` stránky (`owner_ref = opora:page:<nodeId>`); bez ní plán není
(`IntentNotFound`, HTTP 404). Opora plán nepřehrává, jen říká, co harness projektu udělá (`tools/journey_run.py
--intent`), stejně jako plán cesty (`journey_plan.py`).

- `nodes`: uzly v pořadí toku `main` od `intent.entry` (do hloubky, hrany v pořadí grafu, každý uzel jednou;
  větev `intent.error` se nepřehrává). Do plánu jdou jen ověřitelné uzly:
  - `intent.action` → krok `{nodeId, kind: "step", do, scope, text?}`; `do` z parametrů (výchozí `click`);
  - `intent.reaction` → očekávání `{nodeId, kind: "expect", check, value: expect, does}`; `check` z `does`
    (`show` → `visible`, `navigate` → `path`, `send_email` → `email`, `store` → `record`, `call` → `request`);
  - `intent.done` → očekávání `{nodeId, kind: "expect", check, value: claim}`.
- `scope` = `[data-opora-section="<section>"]` podle `section` uzlu, bez ní `body`.
- `path` = `site.path` stránky v přijaté architektuře (bez stránky `/`), `baseUrl` z aplikace nad stránkou
  (`journey_plan.base_url`); bez prostředí klíč chybí a runner ho dostane přes `--base-url`.
- `digest` = `sha256:<hash>` aktivní verze (hash neměnného grafu verze, `workflows.create_draft`).
"""

from backend.flow.workflows import get_version, list_workflows
from backend.project.architecture.journey_plan import base_url, section_scope
from backend.project.architecture.work_status import architecture_graph

SCHEMA = "opora.intent-plan/1"
DOES_CHECK = {"show": "visible", "navigate": "path", "send_email": "email", "store": "record", "call": "request"}


class IntentNotFound(LookupError):
    """Stránka nemá záměr s aktivní verzí."""


def owner_ref(page):
    return f"opora:page:{page}"


def version_digest(version):
    return "sha256:" + version["hash"]


def active_version(db, project, page):
    """Aktivní verze záměru stránky (registry.sqlite, zámek drží volající); jinak `IntentNotFound`."""
    found = [w for w in list_workflows(db, project, "page_intent", owner_ref(page)) if w["active_version_id"]]
    if not found:
        raise IntentNotFound(f"Stránka {page} nemá schválený záměr (aktivní verzi page_intent).")
    return get_version(db, found[0]["active_version_id"])


def main_order(graph):
    """Uzly v pořadí toku `main` od `intent.entry`; větev `intent.error` se nepřehrává."""
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    following = {}
    for edge in graph.get("edges", []):
        if edge.get("kind", "main") == "main":
            following.setdefault(edge["source_node"], []).append(edge["target_node"])
    order, seen = [], set()
    stack = [node["id"] for node in reversed(graph.get("nodes", [])) if node.get("type") == "intent.entry"]
    while stack:
        node_id = stack.pop()
        if node_id in seen or node_id not in nodes or nodes[node_id].get("type") == "intent.error":
            continue
        seen.add(node_id)
        order.append(nodes[node_id])
        stack.extend(reversed(following.get(node_id, [])))
    return order


def _scope(params):
    section = params.get("section")
    return section_scope(section) if isinstance(section, str) and section else "body"


def plan_nodes(graph):
    """Kroky a očekávání plánu z grafu záměru (viz docstring modulu)."""
    items = []
    for node in main_order(graph):
        params = node.get("params") if isinstance(node.get("params"), dict) else {}
        if node["type"] == "intent.action":
            text = params.get("text")
            items.append({"nodeId": node["id"], "kind": "step", "do": params.get("do") or "click",
                          "scope": _scope(params), **({"text": text} if isinstance(text, str) and text else {})})
        elif node["type"] == "intent.reaction":
            items.append({"nodeId": node["id"], "kind": "expect", "check": DOES_CHECK.get(params.get("does")),
                          "value": params.get("expect"), "does": params.get("does")})
        elif node["type"] == "intent.done":
            items.append({"nodeId": node["id"], "kind": "expect", "check": params.get("check"),
                          "value": params.get("claim")})
    return items


def _page_site(architecture, page):
    """`(path, baseUrl)` stránky v přijaté architektuře."""
    nodes = {node["id"]: node for node in architecture.get("nodes", [])}
    node = nodes.get(page) or {}
    site = node.get("site") if isinstance(node.get("site"), dict) else {}
    path = site.get("path") if isinstance(site.get("path"), str) and site.get("path") else "/"
    parent = nodes.get(node.get("parentId"))
    while parent is not None and (parent.get("site") or {}).get("kind") != "application":
        parent = nodes.get(parent.get("parentId"))
    return path, base_url(parent) if parent else None


def intent_plan(architecture, page, version):
    """Plán `opora.intent-plan/1` z aktivní verze záměru a přijaté architektury (čistá funkce)."""
    path, url = _page_site(architecture, page)
    return {"schema": SCHEMA, "pageId": page, "workflowVersionId": version["id"], "digest": version_digest(version),
            "path": path, **({"baseUrl": url} if url else {}), "nodes": plan_nodes(version["graph"])}


def page_intent_plan(service, project, page):
    """`GET /api/project-architecture/intent-plan`: plán z aktivní verze záměru stránky."""
    with service.registry_lock:
        version = active_version(service.db, project, page)
    return intent_plan(architecture_graph(service, project), page, version)
