"""Research decisions become native OporaHub proposals, never automatic acceptance."""
import json

from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.canvas_plan_fields import plan_ref
from backend.editor.research import decisions, model, service as research
from backend.editor.node.node_specs import validate_payload


def _tasks(review, tasks):
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 50:
        model.fail("Supply 1 to 50 concrete tasks.")
    refs, existing = set(), set()
    for task in tasks:
        model.shape(task, {"ref", "title", "goal", "acceptance", "dependsOn"}, {"nodeId", "parentId"})
        plan_ref(task["ref"], "task.ref")
        if task["ref"] in refs:
            model.fail("Duplicate task ref.")
        refs.add(task["ref"])
        for key in ("title", "goal", "acceptance"):
            model.text(task[key], key, 500 if key == "title" else 3500, False)
        model.strings(task["dependsOn"], "dependsOn", ids=True)
        if task.get("nodeId"):
            model.identifier(task["nodeId"])
            if task["nodeId"] in existing:
                model.fail("Existing task may appear only once.")
            existing.add(task["nodeId"])
        if task.get("parentId"):
            model.identifier(task["parentId"])
    if existing and len(existing) != len(tasks):
        model.fail("Propose new tasks and existing-task updates in separate decisions.")
    for task in tasks:
        if any(ref not in refs or ref == task["ref"] for ref in task["dependsOn"]):
            model.fail("Task dependency must reference another task in this proposal.")
    remaining = {task["ref"]: set(task["dependsOn"]) for task in tasks}
    while remaining:
        ready = {ref for ref, dependencies in remaining.items() if not dependencies}
        if not ready:
            model.fail("Task dependencies contain a cycle.")
        remaining = {ref: deps - ready for ref, deps in remaining.items() if ref not in ready}
    if existing and any(task["dependsOn"] for task in tasks):
        model.fail("Existing-task dependencies must be changed through a native graph proposal, not a specification update.")
    return "spec" if existing else "graph"


def _fields(review, task, previous=None):
    previous = previous or {}
    provenance = {"reviewId": review["id"], "project": review["project"], "workspace": review["workspace"],
                  "url": "/api/research/decision-reviews/" + review["id"]}
    def combine(old, new):
        return old if new in old else "\n\n".join(value for value in (old, new) if value)
    steps = previous.get("steps", [])
    step = {"id": "research_" + decisions.digest([review["id"], task["ref"]])[:16],
            "order": max((s["order"] for s in steps), default=0) + 1,
            "title": task["title"], "acceptance": [task["acceptance"]], "dependsOn": []}
    return {**previous,
            "goal": combine(previous.get("goal", ""), task["goal"]) + "\n\nResearch basis:\n" + decisions.encoded(provenance),
            "acceptance": combine(previous.get("acceptance", ""), task["acceptance"]),
            "non_goals": combine(previous.get("non_goals", ""), review["constraints"]),
            "steps": [*steps, step]}


def _proposal(service, project, workspace, review, tasks, kind, subject, by):
    native = OporaGraphProposals(service) if kind == "graph" else OporaChangesets(service)
    # Recover the native proposal if the process stopped after its commit but before our receipt.
    table = "opora_graph_proposals" if kind == "graph" else "opora_spec_proposals"
    rows = service.db_for(project).execute(f"SELECT id FROM {table} WHERE project_id=? AND workspace_id=?", (project, workspace))
    for row in rows:
        item = native.read(project, workspace, row[0])
        if item["subject"] == subject:
            return item
    context = native.context(project, workspace)
    payload = {"project": project, "workspace": workspace, "parentRevision": context["acceptedHead"],
               "expectedGraphDigest": context["graphDigest"], "subject": subject}
    if kind == "graph":
        payload["plan"] = {"nodes": [{"ref": t["ref"], "kind": "node", "name": t["title"], "spec": _fields(review, t),
                                      **({"parent": "@" + t["parentId"]} if t.get("parentId") else {})} for t in tasks],
                           "edges": [{"from": dep, "to": t["ref"], "port": "next"} for t in tasks for dep in t["dependsOn"]]}
    else:
        docs = {item["nodeId"]: item for item in context["documents"]}
        if any(t["nodeId"] not in docs for t in tasks):
            model.fail("Existing task does not belong to this workspace.", 404)
        payload["changes"] = [{"nodeId": t["nodeId"], "expectedRevision": docs[t["nodeId"]]["revision"],
                               "fields": _fields(review, t, docs[t["nodeId"]]["fields"])} for t in tasks]
    return native.create(payload, by)


def materialize(service, project, workspace, review_id, tasks, by):
    with service.graph_lock_for(project), service.lock_for(project):
        review = decisions.read(service, project, workspace, review_id)
        kind = _tasks(review, tasks)
        signature = decisions.digest(tasks)
        db = service.db_for(project)
        row = db.execute("SELECT digest,payload FROM research_materializations WHERE project_id=? AND workspace_id=? AND review_id=?",
                         (project, workspace, review_id)).fetchone()
        if row:
            if row[0] != signature:
                model.fail("This reviewed decision already has a different task proposal.", 409)
            if json.loads(row[1]).get("proposalId"):
                return status(service, project, workspace, review_id)
        graph = {node["id"]: node for node in service.view(project, workspace)["graph"]["nodes"]}
        current = research.detail(service, project, workspace, review["decision"]["id"])["card"]
        known_ids = set(current["refs"]["nodeIds"]) | set(review["decision"]["refs"]["nodeIds"])
        prior = db.execute(
            "SELECT m.payload FROM research_materializations m JOIN research_decision_reviews r "
            "ON r.project_id=m.project_id AND r.workspace_id=m.workspace_id AND r.id=m.review_id "
            "WHERE m.project_id=? AND m.workspace_id=? AND r.decision_id=?",
            (project, workspace, review["decision"]["id"]))
        for record in prior:
            known_ids.update(json.loads(record[0]).get("nodeIds", {}).values())
        linked = {cid for cid in known_ids if graph.get(cid, {}).get("kind") == "node"}
        if kind == "graph" and linked:
            model.fail("Decision links existing tasks; supply their nodeId instead of duplicating them.", 409)
        if kind == "spec" and any(t["nodeId"] not in graph for t in tasks):
            model.fail("Existing task does not belong to this workspace.", 404)
        if any(t.get("parentId") and t["parentId"] not in graph for t in tasks):
            model.fail("Task parent does not belong to this workspace.", 404)
        for task in tasks:
            old = service.node_spec(project, workspace, task["nodeId"])["fields"] if kind == "spec" else None
            validate_payload({"project": project, "workspace": workspace, "node": task.get("nodeId", task["ref"]),
                              "expected_revision": 0, "fields": _fields(review, task, old)})
        if not row:
            # Durable intent makes changed retries conflict even across a process interruption.
            with db:
                db.execute("INSERT INTO research_materializations VALUES(?,?,?,?,?)",
                           (project, workspace, review_id, signature,
                            decisions.encoded({"reviewId": review_id, "tasks": tasks, "proposalKind": kind})))
        subject = "Research " + review_id + " " + signature
        proposal = _proposal(service, project, workspace, review, tasks, kind, subject, by)
        nodes = proposal["refs"] if kind == "graph" else {t["ref"]: t["nodeId"] for t in tasks}
        receipt = {"reviewId": review_id, "proposalId": proposal["id"], "proposalKind": kind,
                   "nodeIds": nodes, "tasks": tasks}
        with db:
            db.execute("UPDATE research_materializations SET payload=? WHERE project_id=? AND workspace_id=? AND review_id=?",
                       (decisions.encoded(receipt), project, workspace, review_id))
        return status(service, project, workspace, review_id)


def status(service, project, workspace, review_id):
    decisions.read(service, project, workspace, review_id)
    row = service.db_for(project).execute("SELECT payload FROM research_materializations WHERE project_id=? AND workspace_id=? AND review_id=?",
                                         (project, workspace, review_id)).fetchone()
    if not row:
        model.fail("No task proposal exists for this review.", 404)
    receipt = json.loads(row[0])
    if not receipt.get("proposalId"):
        return {**receipt, "acceptedRevision": None, "accepted": False, "pending": True}
    native = OporaGraphProposals(service) if receipt["proposalKind"] == "graph" else OporaChangesets(service)
    table = "opora_graph_proposals" if receipt["proposalKind"] == "graph" else "opora_spec_proposals"
    ids = service.db_for(project).execute(f"SELECT id FROM {table} WHERE project_id=? AND workspace_id=?", (project, workspace))
    records = [native.read(project, workspace, row[0]) for row in ids]
    lineage = {receipt["proposalId"]}
    while any(item.get("supersedes") in lineage and item["id"] not in lineage for item in records):
        lineage.update(item["id"] for item in records if item.get("supersedes") in lineage)
    for proposal_id in sorted(lineage):
        accepted = service.db_for(project).execute(
            "SELECT id FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? AND proposal_id=?",
            (project, workspace, proposal_id)).fetchone()
        if accepted:
            return {**receipt, "acceptedRevision": accepted[0], "acceptedProposalId": proposal_id, "accepted": True}
    return {**receipt, "acceptedRevision": None, "accepted": False}


def reconcile(service, project, workspace, review_id):
    """Explicit retryable sync; native acceptance remains the sole task authority."""
    with service.graph_lock_for(project), service.lock_for(project):
        receipt = status(service, project, workspace, review_id)
        if not receipt["accepted"]:
            model.fail("The native OporaHub proposal has not been accepted.", 409)
        review = decisions.read(service, project, workspace, review_id)
        operations = []
        for cid in dict.fromkeys(item["id"] for item in [review["problem"], review["decision"], *review["evidence"]]):
            card = research.detail(service, project, workspace, cid)["card"]
            ids = sorted(set(card["refs"]["nodeIds"]) | set(receipt["nodeIds"].values()))
            if ids != sorted(card["refs"]["nodeIds"]):
                operations.append({"op": "card", "id": cid, "expectedRevision": card["revision"],
                                   **{key: card[key] for key in model.CARD}, "refs": {**card["refs"], "nodeIds": ids}})
        if operations:
            research.apply(service, {"project": project, "workspace": workspace,
                                     "key": "materialized:" + review_id + ":" + decisions.digest(operations),
                                     "operations": operations}, "agent", "heart")
        return receipt
