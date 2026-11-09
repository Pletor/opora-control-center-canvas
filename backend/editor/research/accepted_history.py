"""Validated immutable provenance history, shared only inside a locked steady read."""
import json

from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_graph_changes import GraphChanges


def touched(proposal):
    before = proposal.get("baseGraph", {"nodes": [], "edges": []})
    after = proposal.get("resultGraph", before)
    old = {item["id"]: item for item in before["nodes"]}
    new = {item["id"]: item for item in after["nodes"]}
    meaningful = lambda value: {key: item for key, item in (value or {}).items() if key not in ("x", "y")}
    ids = {key for key in old.keys() | new.keys() if meaningful(old.get(key)) != meaningful(new.get(key))}
    edges_before = {item["id"]: item for item in before["edges"]}
    edges_after = {item["id"]: item for item in after["edges"]}
    for key in edges_before.keys() | edges_after.keys():
        if edges_before.get(key) != edges_after.get(key):
            for edge in (edges_before.get(key), edges_after.get(key)):
                if edge:
                    ids.update((edge["source"], edge["target"]))
    ids.update(doc["nodeId"] for doc in proposal.get("contentEffects", {}).get("documents", []))
    state_before = proposal.get("stateEffects", {}).get("before", {}).get("nodes", {})
    state_after = proposal.get("contentEffects", {}).get("after", {}).get("nodes", {})
    ids.update(key for key in state_before.keys() | state_after.keys()
               if state_before.get(key) != state_after.get(key))
    return ids


def _read(db, project, workspace, head):
    revisions, proposals = ChangesetRepository(db, project, workspace), GraphChanges(db, project, workspace)
    records, seen, latest = [], set(), None
    while head:
        if head in seen:
            raise ValueError("Research provenance ancestry contains a cycle.")
        seen.add(head)
        revision = revisions.read(head)
        if latest is None:
            latest = revision
        if revision.get("kind") in ("graph-acceptance", "graph-baseline") and revision.get("proposalId"):
            proposal = proposals.read(revision["proposalId"])
            source, inputs = proposal.get("researchSource"), proposal.get("contentInputs", {})
            records.append({"id": proposal["id"], "source": source,
                            "observed": inputs.get("researchEvidenceByNode"),
                            "fragments": inputs.get("fragments", {}),
                            "touched": touched(proposal) if source and "continuationId" in source else set()})
        head = revision.get("parentRevision")
    accepted_ids, drafts = set(), []
    if latest:
        from backend.canvas.opora_graph_records import combined
        manifest = latest.get("graphManifestId")
        if manifest:
            accepted_ids = {node["id"] for node in combined(proposals.read(manifest, manifest=True))["nodes"]}
        rows = db.execute("SELECT author,operation_id,response FROM canvas_operation_receipts WHERE project_id=? "
                          "AND workspace_id=? AND operation_kind='canvas-plan' AND status='complete' ORDER BY rowid DESC",
                          (project, workspace))
        for author, operation, raw in rows:
            if json.loads(author) != {"kind": "agent", "name": "heart"}:
                continue
            saved = json.loads(raw)
            source = saved.get("researchSource")
            if source and saved.get("acceptedHeadAtWrite", "missing") is None and saved.get("canvasDraft"):
                draft = saved["canvasDraft"]
                ids = set(draft.get("affectedNodeIds", draft["nodeIds"]))
                ids.update(doc["nodeId"] for doc in draft["documents"])
                drafts.append((source, ids & accepted_ids, operation))
    return records, drafts


def read(db, project, workspace, head, canvas=None):
    compute = lambda: _read(db, project, workspace, head)
    return (canvas.steady_value(project, ("research.accepted_history", workspace, head), compute)
            if canvas is not None else compute())
