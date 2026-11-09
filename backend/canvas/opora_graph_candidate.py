"""Full native graph candidates retain caller identities, including comments and architecture.

These graph-only proposals deliberately do not approve task documents or alter Desktop state.
Deletion with content recovery belongs to RemovalService, not to this snapshot operation.
"""
from copy import deepcopy

from backend.canvas.architecture_graph import ids, split
from backend.canvas.graph import digest, validate_graph
from backend.canvas.opora_change_validation import scope, subject
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_records import combined
from backend.canvas.operation_receipts import Receipt
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def candidate(canvas, project, workspace, graph, raw, undo):
    validate_graph(raw)
    architecture = canvas.architecture.read(project)
    result = canvas._content_only(architecture, raw) if undo else deepcopy(raw)
    if not undo:
        for key in ("nodes", "edges"):
            if {i["id"] for i in graph[key]} - {i["id"] for i in result[key]}:
                raise ValueError("Deleting items requires native removal preview; undo only changes graph presence.")
    result["nodes"] = [{**n, "x": round(n["x"]), "y": round(n["y"])} for n in result["nodes"]]
    validate_graph(result)
    from backend.canvas.card_dag import check_save
    check_save(graph, result)
    canvas._verify_source_refs(project, workspace, graph, result)
    boundary, _ = split(result)
    dropped = ids(architecture["graph"])[0] - ids(boundary)[0]
    hits = canvas.architecture_references(project, dropped, skip=workspace, hidden=ids(boundary)[0])
    if hits:
        from backend.canvas.project_architecture import blocked_message
        raise ValueError(blocked_message(hits))
    return result


def evidence(accepted, working, proposed):
    result = {"areaMembership": [], "architectureContext": None}
    for key in ("nodes", "edges"):
        a, w, p = [{i["id"]: i for i in g[key]} for g in (accepted, working, proposed)]
        result[key] = []
        for identifier in sorted(a.keys() | w.keys() | p.keys()):
            if a.get(identifier) == w.get(identifier) == p.get(identifier):
                continue
            operation = "remove" if identifier not in p else "add" if identifier not in a and identifier not in w else "update"
            result[key].append({"id": identifier, "operation": operation, "fields": [], "acceptedBefore": a.get(identifier),
                                "workingBefore": w.get(identifier), "proposedAccepted": p.get(identifier), "proposedWorking": p.get(identifier)})
    return result


def plan_summary(accepted, working, proposed, undo):
    return {"candidateGraph": proposed, "undo": undo,
            "removeNodes": sorted((ids(accepted)[0] | ids(working)[0]) - ids(proposed)[0]),
            "removeEdges": sorted((ids(accepted)[1] | ids(working)[1]) - ids(proposed)[1]),
            "adoptArchitectureContext": split(accepted)[0] != split(proposed)[0] or split(working)[0] != split(proposed)[0]}


def create(canvas, payload, by):
    from backend.canvas.opora_graph_changes import OporaGraphChanges
    project, workspace = scope(payload)
    allowed = {"project", "workspace", "parentRevision", "expectedGraphDigest", "subject", "graph", "undo", "operationId"}
    if set(payload) != allowed or type(payload["undo"]) is not bool:
        raise ValueError("Full graph proposal requires exact graph, undo, context and operation ID.")
    author, label = _author(by, allow_agent=True), subject(payload)
    receipt = Receipt(payload, "graph-candidate", author)
    native = OporaGraphChanges(canvas)
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        repo = native.repository(project, workspace)
        with repo.db:
            repo.db.execute("BEGIN IMMEDIATE")
            replay = receipt.replay(repo.db)
            if replay is not None:
                return replay
            context, graph, manifest = native.observed(project, workspace)
            native.expect(context, payload["parentRevision"], payload["expectedGraphDigest"])
            if context["readOnly"] or context["acceptedHead"] is None:
                raise ValueError("Accepted graph candidates require writable accepted scope.")
            proposed = candidate(canvas, project, workspace, graph, payload["graph"], payload["undo"])
            accepted = combined(manifest) if manifest else graph
            if proposed == graph and proposed == accepted:
                raise ValueError("Full candidate has no graph changes.")
            state = DesktopV3State(canvas).current(project, workspace)
            before = deepcopy(state["state"])
            record = {"schemaVersion": 4, "kind": "graph-changes", "project": project, "workspace": workspace,
                "parentRevision": context["acceptedHead"], "parentGraphManifestId": manifest["id"] if manifest else None,
                "subject": label, "by": author, "createdAt": stamp(), "supersedes": None, "graphDigest": digest(graph),
                "baseGraph": graph, "acceptedGraph": accepted, "resultGraph": proposed, "acceptedResultGraph": proposed,
                "plan": plan_summary(accepted, graph, proposed, payload["undo"]),
                "requiresBaseAdoption": manifest is None, "adoptionDocuments": [], "specifications": [],
                "additions": {key: [i for i in proposed[key] if i["id"] not in {old["id"] for old in graph[key]}] for key in ("nodes", "edges")},
                "refs": {}, "inside": {}, "positions": {}, "changes": evidence(accepted, graph, proposed),
                "architectureRevision": canvas.architecture.read(project)["revision"],
                "stateEffects": {"revision": state["revision"], "before": before, "after": before, "beforeDigest": digest(before),
                    "affectedDigest": digest(before), "effects": {"graphOnly": "Documents, Desktop state, workspace history and accepted content remain unchanged."},
                    "removedNodeIds": [], "removedEdgeIds": [], "rewiredEdgeIds": [], "checkedNodeIds": []}}
            result = {**repo.insert(record), "accepted": False}
            receipt.begin(repo.db)
            receipt.complete(repo.db, result)
            return result


def validate_record(record):
    from backend.canvas.opora_change_validation import identifier
    scope(record)
    if record["schemaVersion"] != 4 or record["kind"] != "graph-changes":
        raise ValueError("Invalid full candidate record.")
    identifier(record["parentRevision"])
    identifier(record["parentGraphManifestId"], nullable=True)
    if record["requiresBaseAdoption"] != (record["parentGraphManifestId"] is None):
        raise ValueError("Invalid candidate graph authority.")
    for key in ("baseGraph", "acceptedGraph", "resultGraph", "acceptedResultGraph"):
        validate_graph(record[key])
    if record["graphDigest"] != digest(record["baseGraph"]) or record["resultGraph"] != record["acceptedResultGraph"] or record["plan"]["candidateGraph"] != record["resultGraph"]:
        raise ValueError("Candidate graph evidence mismatch.")
    if type(record["plan"]["undo"]) is not bool or record["changes"] != evidence(record["acceptedGraph"], record["baseGraph"], record["resultGraph"]):
        raise ValueError("Candidate review differs from stored graph.")
    if record["plan"] != plan_summary(record["acceptedGraph"], record["baseGraph"], record["resultGraph"], record["plan"]["undo"]):
        raise ValueError("Candidate risk metadata differs from the full graph.")
    additions = {key: [i for i in record["resultGraph"][key] if i["id"] not in {old["id"] for old in record["baseGraph"][key]}] for key in ("nodes", "edges")}
    if record["additions"] != additions or record["refs"] or record["inside"] or record["positions"]:
        raise ValueError("Candidate identities differ from exact supplied graph.")
    state = record["stateEffects"]
    if state["before"] != state["after"] or digest(state["before"]) != state["beforeDigest"] or state["affectedDigest"] != state["beforeDigest"]:
        raise ValueError("Graph-only candidate cannot change Desktop state.")
    if record["adoptionDocuments"] or record["specifications"]:
        raise ValueError("Graph-only candidate cannot approve documents.")
