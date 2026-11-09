"""Federated pinned research references. Authorization callbacks precede every source read."""
import hashlib
import json
from datetime import UTC, datetime
from backend.editor.research import model, service as research


def reference(value):
    model.shape(value, {"projectId", "workspaceId", "id", "revision"})
    for key in ("projectId", "workspaceId", "id"):
        model.identifier(value[key])
    if type(value["revision"]) is not int or value["revision"] < 1:
        model.fail("Source revision must be a positive integer.")
    return dict(value)


def _target(service, project, workspace, node):
    if not isinstance(node, str):
        model.fail("scopeNodeId must be a node ID or the empty project root.")
    view = research._scope(service, project, workspace)
    if node:
        model.identifier(node)
        if not any(n["id"] == node and n["kind"] in ("node", "sector") for n in view["graph"]["nodes"]):
            model.fail("Context is unavailable.", 404, "research_scope")
    return view


def _bindings(service, project, workspace):
    with service.reading(project):
        rows = service.db_for(project).execute("SELECT payload FROM research_scope_bindings b WHERE project_id=? AND workspace_id=? AND revision=(SELECT MAX(revision) FROM research_scope_bindings r WHERE r.project_id=b.project_id AND r.workspace_id=b.workspace_id AND r.id=b.id)", (project, workspace)).fetchall()
        return [json.loads(row[0]) for row in rows]


def bind(service, project, workspace, node, source, expected, archived, authorize, actor):
    source = reference(source)
    if type(expected) is not int or expected < 0 or type(archived) is not bool:
        model.fail("Expected revision and archived flag are invalid.")
    authorize(project, workspace, True)
    _target(service, project, workspace, node)
    authorize(source["projectId"], source["workspaceId"], False)
    research.detail(service, source["projectId"], source["workspaceId"], source["id"], source["revision"])
    identifier = "kb_" + hashlib.sha256(research._json([node, source]).encode()).hexdigest()[:32]
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        value = {"id": identifier, "revision": expected + 1, "scopeNodeId": node, "source": source,
                 "archived": archived, "by": actor, "at": datetime.now(UTC).isoformat()}
        with db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT MAX(revision) FROM research_scope_bindings WHERE project_id=? AND workspace_id=? AND id=?", (project,workspace,identifier)).fetchone()[0]
            if expected != (old or 0):
                model.fail("Binding revision conflict.", 409, "research_conflict")
            db.execute("INSERT INTO research_scope_bindings VALUES(?,?,?,?,?,?)", (project, workspace, node, identifier, expected + 1, research._json(value)))
        return value


def _record(service, project, workspace, card, contexts):
    return {"canonicalRef": {"projectId": project, "workspaceId": workspace, "id": card["id"], "revision": card["revision"]},
            "card": model.header(card), "contexts": contexts,
            "provenance": {"projectId": project, "projectName": service.project_hub._project(project)["name"], "workspaceId": workspace,
                           "sources": [{k: source[k] for k in ("ref", "title", "platform", "revision", "location") if k in source} for source in card.get("sources", [])[:10]], "sourceCount": len(card.get("sources", [])), "by": card["by"]},
            "verification": card["verification"]}


def context(service, project, workspace, node, authorize):
    authorize(project, workspace, False)
    view = _target(service, project, workspace, node)
    by_id = {n["id"]: n for n in view["graph"]["nodes"]}
    ancestors, cursor = [], by_id.get(node, {}).get("parentId")
    while cursor is not None and cursor in by_id and cursor not in ancestors:
        ancestors.append(cursor); cursor = by_id[cursor].get("parentId")
    records = {}
    def include(p, w, card, relation, scope):
        ref = (p, w, card["id"], card["revision"])
        record = records.setdefault(ref, _record(service, p, w, card, []))
        marker = {"relation": relation, "scopeNodeId": scope or None}
        if marker not in record["contexts"]:
            record["contexts"].append(marker)
    for header in research.listing(service, project, workspace)["cards"]:
        refs = header["refs"]["nodeIds"]
        relations = []
        if not node or node in refs:
            relations.append(("local", node))
        else:
            relations.extend(("parent", parent) for parent in ancestors if parent in refs)
            if not refs:
                relations.append(("parent", ""))
        if relations:
            card = research.detail(service, project, workspace, header["id"], header["revision"])["card"]
            for relation, owner in relations:
                include(project, workspace, card, relation, owner)
    for binding in _bindings(service, project, workspace):
        if binding["archived"] or binding["scopeNodeId"] != node:
            continue
        source = binding["source"]
        try:
            authorize(source["projectId"], source["workspaceId"], False)
            card = research.detail(service, source["projectId"], source["workspaceId"], source["id"], source["revision"])["card"]
        except (ValueError, OSError, model.GateError):
            continue  # No source metadata or counts leak when permission disappears.
        include(source["projectId"], source["workspaceId"], card, "shared", node)
    return {"records": list(records.values())[:200], "truncated": len(records)>200}


def search(service, scopes, query, kinds, verification, limit, authorize):
    if not isinstance(scopes, list) or not 1 <= len(scopes) <= 30:
        model.fail("Search requires 1 to 30 explicit project scopes.")
    model.text(query, "query", 500, False)
    if not isinstance(kinds, list) or any(not isinstance(k, str) or k not in model.KINDS for k in kinds):
        model.fail("Unknown research kind filter.")
    if not isinstance(verification, list) or any(not isinstance(v, str) or v not in model.VERIFICATION for v in verification):
        model.fail("Unknown verification filter.")
    if type(limit) is not int or not 1 <= limit <= 100:
        model.fail("Search limit must be 1 to 100.")
    # Authorize all requested sources before collecting any candidates.
    for scope in scopes:
        model.shape(scope, {"project", "workspace"}, {"scopeNodeId", "includeDescendants"})
        if "scopeNodeId" in scope and not isinstance(scope["scopeNodeId"], str):
            model.fail("scopeNodeId must be a node ID or empty root.")
        if type(scope.get("includeDescendants", True)) is not bool:
            model.fail("includeDescendants must be boolean.")
        authorize(scope["project"], scope["workspace"], False)
    words = query.casefold().split()
    found = {}
    for scope in scopes:
        p, w = scope["project"], scope["workspace"]
        allowed = None
        scoped = scope.get("scopeNodeId")
        if scoped:
            view = _target(service,p,w,scoped)
            allowed = {scoped}
            if scope.get("includeDescendants",True):
                for _ in view["graph"]["nodes"]:
                    expanded = allowed | {n["id"] for n in view["graph"]["nodes"] if n.get("parentId") in allowed}
                    if expanded == allowed:
                        break
                    allowed = expanded
        for header in research.listing(service, p, w)["cards"]:
            if allowed is not None and not allowed.intersection(header["refs"]["nodeIds"]):
                continue
            if kinds and header["kind"] not in kinds or verification and header["verification"]["status"] not in verification:
                continue
            corpus = research._json(header).casefold()
            if not all(word in corpus for word in words):
                continue
            card = research.detail(service, p, w, header["id"], header["revision"])["card"]
            found[(p, w, card["id"], card["revision"])] = _record(service, p, w, card, [{"relation": "local", "scopeNodeId": n} for n in card["refs"]["nodeIds"]])
    ordered = sorted(found.values(), key=lambda r: (r["card"]["title"].casefold(), research._json(r["canonicalRef"])))
    return {"results": ordered[:limit], "truncated": len(ordered) > limit, "ranking": "lexical-all-terms"}


def solutions(service, scopes, query, limit, authorize):
    from backend.editor.research.solution_verification import project as solution_proofs
    # Search validation and complete authorization precede all project collection.
    search(service, scopes, query, [], [], limit, authorize)
    found = {}
    words = query.casefold().split()
    for scope in scopes:
        p, w = scope["project"], scope["workspace"]
        view = research._scope(service, p, w)
        nodes = view["graph"]["nodes"]
        scoped = scope.get("scopeNodeId")
        allowed = {n["id"] for n in nodes} if not scoped else {scoped}
        if scoped and not any(n["id"] == scoped for n in nodes):
            model.fail("Search context is unavailable.", 404, "research_scope")
        if type(scope.get("includeDescendants", True)) is not bool:
            model.fail("includeDescendants must be boolean.")
        if scoped and scope.get("includeDescendants", True):
            for _ in nodes:
                expanded = allowed | {n["id"] for n in nodes if n.get("parentId") in allowed}
                if expanded == allowed:
                    break
                allowed = expanded
        candidates = [node for node in nodes if node["id"] in allowed and node["kind"] in ("node", "sector")
                      and all(word in research._json([node["id"], node["name"], node["purpose"], node.get("element")]).casefold() for word in words)]
        proofs = solution_proofs(service, p, w, view, [node["id"] for node in candidates])
        for node in candidates:
            item = {"solutionRef": {"projectId": p, "nodeId": node["id"]},
                    "snapshot": {"workspaceId": w, "graphDigest": view["digest"], "verification": proofs[node["id"]]},
                    "title": node["name"], "purpose": node["purpose"], "element": node.get("element"),
                    "verification": proofs[node["id"]],
                    "evidence": context(service,p,w,node["id"],authorize)["records"]}
            # One problem identity across workspaces; preserve all observed snapshots.
            key = (p, node["id"])
            if key in found:
                found[key]["snapshots"].append(item["snapshot"])
                if item["verification"].get("verified") and not found[key]["verification"].get("verified"):
                    found[key] = {**item, "snapshots": found[key]["snapshots"]}
            else:
                found[key] = {**item, "snapshots": [item["snapshot"]]}
    ordered = sorted(found.values(), key=lambda item: (item["title"].casefold(), research._json(item["solutionRef"])))
    return {"solutions": ordered[:limit], "truncated": len(ordered)>limit, "ranking": "lexical-all-terms"}
