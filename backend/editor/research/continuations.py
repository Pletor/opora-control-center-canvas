"""Durable planning receipts dispatched exclusively by the existing HeartDriver."""
import hashlib
import json

from backend.editor.research import model

MAX_ATTEMPTS = 3
OPEN_RUNS = ("queued", "running", "waiting")


def save(db, project, workspace, item):
    db.execute("UPDATE research_continuations SET payload=? WHERE project_id=? AND workspace_id=? AND id=?",
               (json.dumps(item, ensure_ascii=False), project, workspace, item["id"]))


def create(db, project, workspace, intent, result, actor, agent):
    """Join the importing transaction; a lost import response cannot lose this intent."""
    model.shape(intent, {"researchId", "sourceFragmentId", "sourceRevision"}, {"finalization"})
    model.identifier(intent["researchId"]); model.identifier(intent["sourceFragmentId"])
    if type(intent["sourceRevision"]) is not int or intent["sourceRevision"] < 1:
        model.fail("sourceRevision must be a positive integer.")
    card = next((c for c in result["cards"] if c["id"] == intent["researchId"]), None)
    if not card or card["kind"] != "question" or intent["sourceFragmentId"] not in card["refs"]["fragmentIds"]:
        model.fail("Continuation must reference the imported research question and its original fragment.")
    source = db.execute("SELECT kind FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? "
                        "AND fragment_id=? AND revision=?", (project, workspace, intent["sourceFragmentId"],
                                                             intent["sourceRevision"])).fetchone()
    if not source or source[0] != "research":
        model.fail("Original research revision not found in this workspace.", 409, "research_source")
    key = hashlib.sha256(json.dumps([project, workspace, card["id"], card["revision"]]).encode()).hexdigest()
    item = {"id": "rp_" + key[:32], "researchId": card["id"], "researchRevision": card["revision"],
            "sourceFragmentId": intent["sourceFragmentId"], "sourceRevision": intent["sourceRevision"],
            "operationId": "research-plan:" + key, "status": "pending", "attempts": 0, "nextAt": 0,
            "flowRunId": None, "proposalId": None, "error": None, "by": {"kind": actor, "name": agent or ""}}
    from backend.editor.research.execution_evidence import imported_pins, original_input
    item["evidence"] = imported_pins(db, project, workspace, card["id"], result)
    item["evidence"]["originalInput"] = original_input(db, project, workspace, intent["sourceFragmentId"], intent["sourceRevision"])
    item["evidence"]["originalSourceCoverage"] = "semantic-input-only; direct-original-output-edits-untracked"
    if "finalization" in intent:
        from backend.editor.research.finalization import expected
        item["finalization"] = expected(intent["finalization"])
        item.update(status="awaiting_finalization", error="Awaiting native research completion.")
    db.execute("INSERT INTO research_continuations VALUES(?,?,?,?,?,?)",
               (project, workspace, item["id"], card["id"], card["revision"], json.dumps(item)))
    from backend.canvas.opora_events import emit_event
    emit_event(db, project_id=project, workspace_id=workspace, kind="research.planning.requested",
               actor={"kind": actor, "name": agent or "human"}, data={"continuationId": item["id"]})
    return item


def listing(service, project, workspace):
    from backend.editor.research.service import _scope
    _scope(service, project, workspace)
    with service.reading(project):
        return [json.loads(row[0]) for row in service.db_for(project).execute(
            "SELECT payload FROM research_continuations WHERE project_id=? AND workspace_id=?",
            (project, workspace))]


def verified_proposal(service, project, workspace, item):
    """Require native durable operation identity and compare all immutable proposal content."""
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    db = service.db_for(project)
    rows = db.execute("SELECT author,status,response,operation_kind FROM canvas_operation_receipts WHERE project_id=? AND "
                     "workspace_id=? AND operation_kind IN ('graph-proposal','canvas-plan') AND operation_id=?",
                     (project, workspace, item["operationId"])).fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        model.fail("Multiple planning operations require reconciliation.", 409, "continuation_conflict")
    row = rows[0]
    author = json.loads(row[0])
    if author != {"kind": "agent", "name": "heart"} or row[1] != "complete":
        model.fail("Planning operation requires reconciliation.", 409, "operation_incomplete")
    original = json.loads(row[2])
    from backend.editor.research.planning_source import pins, validate_source
    if row[3] == "canvas-plan":
        if original.get("researchSource") != pins(item):
            model.fail("Draft does not pin this research revision.", 409, "continuation_conflict")
        from backend.canvas.research_canvas_draft import verify
        try:
            draft = verify(service, project, workspace, original)
        except (ValueError, KeyError, TypeError) as error:
            model.fail(str(error), 409, "continuation_conflict")
        if not draft.get("nodeIds"):
            model.fail("An empty draft cannot complete research planning.", 409, "continuation_conflict")
        accepted = draft.pop("acceptedHeadAtReadback", None)
        return {"resultKind": "canvasDraft", "proposalId": None, "canvasDraft": draft,
                "acceptedHeadAtReadback": accepted}
    current = OporaGraphProposals(service).read(project, workspace, original["id"])
    source = current.get("researchSource")
    if source != pins(item):
        model.fail("Proposal does not pin this research revision.", 409, "continuation_conflict")
    validate_source(service, project, workspace, source)
    effects = current.get("contentEffects") or {}
    changed = (current.get("resultGraph") != current.get("baseGraph") or effects.get("documents")
               or (effects.get("afterDigest") and effects["afterDigest"] != current.get("stateEffects", {}).get("beforeDigest")))
    if current.get("schemaVersion") != 3 or not changed:
        model.fail("An empty proposal cannot complete research planning.", 409, "continuation_conflict")
    if current["project"] != project or current["workspace"] != workspace:
        model.fail("Expected a proposal in this workspace.", 409, "continuation_conflict")
    if any(current.get(key) != value for key, value in original.items() if key != "accepted"):
        model.fail("Native proposal readback differs from the operation receipt.", 409, "continuation_conflict")
    return {"resultKind": "proposal", "proposalId": current["id"], "acceptedAtReadback": current.get("accepted") is True}


def wakes(service, project, now):
    """Recover from native flow history on every poll, including before the first outbox cursor."""
    # Registry and project DBs have separate transactions. Read durable runs first; a crash
    # after start_run but before updating a receipt is recovered by its input identity.
    with service.registry_lock:
        runs = []
        for row in service.db.execute("SELECT id,status,trigger FROM flow_runs ORDER BY rowid"):
            trigger = json.loads(row[2])
            payload = trigger.get("payload") or {}
            if trigger.get("source") == "heart" and payload.get("project") == project:
                for value in payload.get("items", []):
                    if value.get("type") == "researchPlanning":
                        runs.append((value.get("continuationId"), row[0], row[1], payload.get("workspace")))
    found = []
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        with db:
            rows = db.execute("SELECT workspace_id,payload FROM research_continuations WHERE project_id=?", (project,)).fetchall()
            for workspace, raw in rows:
                item = json.loads(raw)
                if item["status"] in ("complete", "conflict", "exhausted"):
                    continue
                revision = db.execute("SELECT MAX(revision) FROM research_card_revisions WHERE project_id=? "
                    "AND workspace_id=? AND id=?", (project, workspace, item["researchId"])).fetchone()[0]
                if revision != item["researchRevision"]:
                    item.update(status="conflict", error="Research revision changed; reconcile the pinned operation.")
                    save(db, project, workspace, item)
                    continue
                try:
                    from backend.editor.research.finalization import observe
                    if not observe(db, project, workspace, item):
                        save(db, project, workspace, item)
                        continue
                    proposal = verified_proposal(service, project, workspace, item)
                except (model.GateError, ValueError) as error:
                    item.update(status="conflict", error=str(error))
                    save(db, project, workspace, item)
                    continue
                if proposal:
                    item.update(status="complete", **proposal, error=None)
                else:
                    if item["status"] == "blocked_context":
                        item.update(status="pending", error=None)
                    latest = [r for r in runs if r[0] == item["id"] and r[3] == workspace]
                    item["attempts"] = len(latest)
                    if latest:
                        _, run_id, status, _ = latest[-1]
                        if status in OPEN_RUNS:
                            item.update(status="running", flowRunId=run_id)
                        elif item["flowRunId"] != run_id or item["status"] == "running":
                            item.update(status="exhausted" if len(latest) >= MAX_ATTEMPTS else "pending",
                                        flowRunId=run_id, nextAt=now + 60 * len(latest),
                                        error="Run ended without a verified proposal or initial canvas draft.")
                    if item["status"] == "pending" and item["nextAt"] <= now:
                        found.append((workspace, {"type": "researchPlanning", "continuationId": item["id"],
                            "researchId": item["researchId"], "researchRevision": item["researchRevision"],
                            "operationId": item["operationId"], "workspace": workspace,
                            "researchSource": {"continuationId": item["id"], "researchId": item["researchId"],
                                "researchRevision": item["researchRevision"], "sourceFragmentId": item["sourceFragmentId"],
                                "sourceRevision": item["sourceRevision"]}}))
                save(db, project, workspace, item)
    return found
