"""Canonical scope references pinned without treating bindings as source grants."""
import json

from backend.canvas.graph import digest


def _bindings(db, project, workspace, nodes):
    rows = db.execute("SELECT payload FROM research_scope_bindings b WHERE project_id=? AND workspace_id=? "
        "AND revision=(SELECT MAX(revision) FROM research_scope_bindings r WHERE r.project_id=b.project_id "
        "AND r.workspace_id=b.workspace_id AND r.id=b.id)", (project, workspace)).fetchall()
    return sorted((json.loads(row[0]) for row in rows
                   if json.loads(row[0])["scopeNodeId"] in nodes), key=lambda item: item["id"])


def _source(db, project, workspace, identifier, revision):
    row = db.execute("SELECT payload FROM research_card_revisions WHERE project_id=? AND workspace_id=? AND id=? AND revision=?",
                     (project, workspace, identifier, revision)).fetchone()
    if row is None:
        raise ValueError("Pinned canonical research revision is unavailable.")
    return json.loads(row[0])


def collect(db, project, workspace, node_ids):
    nodes = sorted(set(node_ids) | {""})
    bindings = _bindings(db, project, workspace, nodes)
    records = {}

    def include(ref, context, binding=None, card=None):
        key = json.dumps(ref, sort_keys=True)
        pin = records.setdefault(key, {"canonicalRef": ref, "contexts": [], "bindings": [],
                                      "availability": "source_scope_not_delegated"})
        if context not in pin["contexts"]:
            pin["contexts"].append(context)
        if binding is not None:
            pin["bindings"].append({"projectId": project, "workspaceId": workspace,
                "id": binding["id"], "revision": binding["revision"], "digest": digest(binding),
                "scopeNodeId": binding["scopeNodeId"], "by": binding["by"], "at": binding["at"]})
        if ref["projectId"] == project and ref["workspaceId"] == workspace:
            card = card or _source(db, project, workspace, ref["id"], ref["revision"])
            pin.update(availability="pinned", digest=digest(card), provenance={"by": card["by"],
                "sources": [{key: source[key] for key in ("ref", "title", "platform", "revision", "location") if key in source}
                            for source in card.get("sources", [])], "verification": card.get("verification")})

    # Local and parent records are already selected inside the authorized workspace.
    rows = db.execute("SELECT payload FROM research_card_revisions c WHERE project_id=? AND workspace_id=? "
        "AND revision=(SELECT MAX(revision) FROM research_card_revisions r WHERE r.project_id=c.project_id "
        "AND r.workspace_id=c.workspace_id AND r.id=c.id)", (project, workspace)).fetchall()
    for row in rows:
        card = json.loads(row[0])
        if card.get("archived"):
            continue
        refs = card.get("refs", {}).get("nodeIds", [])
        owners = sorted(set(refs) & set(nodes)) if refs else [""]
        for owner in owners:
            include({"projectId": project, "workspaceId": workspace, "id": card["id"], "revision": card["revision"]},
                    {"scopeNodeId": owner, "relation": "local" if owner else "parent"}, card=card)
    for binding in bindings:
        if not binding["archived"]:
            include(binding["source"], {"scopeNodeId": binding["scopeNodeId"], "relation": "shared"}, binding)
    return {"scopeNodeIds": nodes, "bindingSelectionDigest": digest(bindings),
            "pins": [records[key] for key in sorted(records)]}


def validate(db, project, workspace, evidence):
    bindings = _bindings(db, project, workspace, evidence["scopeNodeIds"])
    if digest(bindings) != evidence["bindingSelectionDigest"]:
        raise ValueError("Canonical research binding selection changed; prepare a new assignment.")
    for pin in evidence["pins"]:
        ref = pin["canonicalRef"]
        if pin["availability"] == "pinned":
            if ref["projectId"] != project or ref["workspaceId"] != workspace:
                raise ValueError("Canonical research source scope was not delegated.")
            if digest(_source(db, project, workspace, ref["id"], ref["revision"])) != pin["digest"]:
                raise ValueError("Historical canonical research revision changed.")
