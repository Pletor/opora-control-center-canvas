"""Explicit preparation and immutable private origins for sparse execution context."""
import hashlib
import hmac
import json

from backend.canvas.graph import digest
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_content_execution import require_accepted_content
from backend.canvas.opora_execution_budget_status import status as budget_status
from backend.canvas.opora_execution_lineage import validate_accepted_lineage
from backend.canvas.opora_execution_validation import run_profile, validate
from backend.canvas.opora_graph_execution import require_accepted_graph
from backend.canvas.opora_plan_steps import ordered, steps_of
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from backend.editor.agent_packet.specification_sql_context import project_sql_context
from backend.editor.agent_packet.specification_sql_rows import composed_graph
from backend.library.harness_kit import kit_of_assignment
from database.repositories import opora_context_bindings as bindings
from database.repositories import opora_execution_contexts as private
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_context_events import enroll
from database.repositories.opora_context_snapshot import capture


def claim_fields(payload):
    """Negotiate context independently of budget protocol; no silent downgrade."""
    if not isinstance(payload, dict) or "contextProtocolVersion" not in payload:
        return set()
    if type(payload["contextProtocolVersion"]) is not int or payload["contextProtocolVersion"] != 2:
        raise ValueError("Unsupported execution context protocol version.")
    return {"contextProtocolVersion"}


def token(secret, projection, accepted, binding):
    raw = json.dumps({"projection": projection, "acceptedRevision": accepted, "binding": binding},
                     ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hmac.new(bytes.fromhex(secret), raw, hashlib.sha256).hexdigest()


def persist(repo, record, pin):
    private.insert(repo.db, *repo.scope, record["executionId"], pin)
    private.proof(repo.db, *repo.scope, record["executionId"], {
        "contextProtocolVersion": 2, "originAcceptedRevision": record["acceptedRevision"],
        "checkedAcceptedRevision": record["acceptedRevision"], "acceptedRevisionsChecked": 1,
        "liveTransitionsChecked": 0, "acceptedScopeUnchanged": True, "liveScopeUnchanged": True})


def pin_id(record):
    """Klíč platného pinu běhu: původní (`executionId`), po re-pinu nový neměnný pin (`contextPinId`)."""
    return record.get("contextPinId") or record["executionId"]


def public_proof(repo, record):
    if record.get("contextProtocolVersion") != 2:
        return {}
    return {"contextValidation": private.read_proof(repo.db, *repo.scope, pin_id(record)),
            "researchEvidenceCoverage": record["assignment"].get("researchEvidence", {}).get("coverage", "legacy-untracked")}


def _metadata(canvas, project):
    value = canvas.project_hub.settings(project)["project"]
    return {"id": value["id"], "name": value["name"]}


def _collect(canvas, db, project, workspace, node):
    """Caller holds graph/project/registry locks and a project SQL transaction."""
    before = bindings.checkpoint(canvas.db, project, workspace)
    snapshot = capture(db, project)
    metadata = _metadata(canvas, project)
    projection = project_sql_context(snapshot["rows"], project, workspace, node, metadata=metadata)
    view = canvas.view(project, workspace)
    graph, _ = composed_graph(snapshot["rows"], workspace)
    if view["readOnly"] or digest(graph) != digest(view["graph"]):
        raise ValueError("SQL context does not match the writable workspace view.")
    target = next(item for item in graph["nodes"] if item["id"] == node)
    own = next(item for item in projection["eligibility"]["facts"] if item["nodeId"] == node)
    if target["kind"] not in {"node", "sector"} or own["done"]["confirmed"] or projection["eligibility"]["blockers"]:
        raise ValueError("Card is closed, blocked or cannot be executed.")
    context = OporaChangesets(canvas).context(project, workspace)
    head = context["acceptedHead"]
    validate_accepted_lineage(db, project, workspace, node, head, head)
    require_accepted_graph(canvas, project, workspace, head, graph)
    require_accepted_content(canvas, project, workspace, head, projection["selection"]["cardIds"], graph)
    from backend.canvas.requirement_readiness import require_inputs
    requirements = require_inputs(canvas, project, workspace, node, head, graph, context["acceptedDocuments"])
    accepted = {item["nodeId"]: item for item in context["acceptedDocuments"]}
    from backend.canvas.execution_write_set import resolve_affected
    affected = resolve_affected(node, accepted.get(node, {}).get("fields", {}), graph, context["acceptedDocuments"])
    for identifier in affected:
        requirements.extend(require_inputs(canvas, project, workspace, identifier, head, graph, context["acceptedDocuments"]))
    requirements = list({item["edgeId"]: item for item in requirements}.values())
    selected = []
    scopes = [projection, *projection.get("affectedScopes", [])]
    owners = {item["nodeId"]: item["specWorkspace"] for scope in scopes for item in scope["owners"]}
    cards = {item["nodeId"]: item for scope in scopes for item in scope["cards"]}
    require_accepted_content(canvas, project, workspace, head, sorted(cards), graph)
    for card in cards.values():
        actual = {"nodeId": card["nodeId"], "ownerWorkspace": owners[card["nodeId"]],
                  "revision": card["spec"]["revision"], "fields": card["spec"]["fields"]}
        if accepted.get(card["nodeId"]) != actual:
            raise ValueError("Relevant specifications differ from their accepted revision.")
        selected.append(actual)
    after = bindings.checkpoint(canvas.db, project, workspace)
    if before != after:
        raise ValueError("Registry source binding changed during context capture.")
    from backend.editor.research.execution_evidence import collect as research_evidence
    evidence = research_evidence(db, project, workspace, head, sorted(cards))
    from backend.canvas.storyboard_evidence import collect as storyboard_inputs
    storyboards = storyboard_inputs(canvas, project, workspace, sorted(cards), graph)
    opaque = token(private.key(db, project), {**projection, "researchEvidence": evidence, "storyboards": storyboards}, head, before)
    steps = ordered(steps_of((accepted.get(node) or {}).get("fields")))  # pinned plan (oporahub-plan-steps.md)
    assignment = {"acceptedRevision": head, "documents": redact_deep(selected), "contextVersion": opaque,
                  "contextProtocolVersion": 2, "steps": redact_deep(steps), "run": run_profile(target, graph, steps),
                  "specification": {**redact_deep(projection), "schema": "opora.specification-context/2"},
                  "researchEvidence": evidence, "storyboards": storyboards, **({"requiredInputs": requirements} if requirements else {}),
                  **({"affectedElements": [{"nodeId": identifier, "revision": accepted[identifier]["revision"],
                     "documentDigest": digest(accepted[identifier])} for identifier in affected]} if affected else {})}
    kit_of_assignment(assignment, node)  # Validate transported content before issuing an execution pin.
    pin = {"schemaVersion": 1, "snapshot": snapshot, "metadata": metadata, "binding": before,
           "nodeId": node, "acceptedRevision": head, "contextVersion": opaque,
           "assignmentDigest": digest(assignment)}
    return assignment, pin


def collect(canvas, db, project, workspace, node):
    try:
        with canvas.registry_lock:
            return _collect(canvas, db, project, workspace, node)
    except (TypeError, KeyError, IndexError, AttributeError, RecursionError) as error:
        raise ValueError("Sparse execution context evidence is malformed.") from error


def prepare(executions, payload):
    project, workspace = validate(payload, {"nodeId", "contextProtocolVersion"})
    if type(payload["contextProtocolVersion"]) is not int or payload["contextProtocolVersion"] != 2:
        raise ValueError("Unsupported execution context protocol version.")
    with executions.transaction(project, workspace) as repo, executions.canvas.registry_lock:
        registry = executions.canvas.db
        if registry.in_transaction:
            raise RuntimeError("Context preparation requires its own registry transaction.")
        with registry:
            registry.execute("BEGIN IMMEDIATE")
            bindings.install(registry)
            bindings.enroll(registry, project, workspace)
        from backend.canvas.opora_context_graph_storage import promote_sql_draft
        promote_sql_draft(executions.canvas, project, workspace,
                          ChangesetRepository(repo.db, project, workspace).head())
        enroll(repo.db, project)
        private.key(repo.db, project, create=True)
        assignment, _ = collect(executions.canvas, repo.db, project, workspace, payload["nodeId"])
        budget = budget_status(repo.db, project, workspace, payload["nodeId"], assignment["acceptedRevision"])
        return {"available": not bool(budget["blockedReason"]), "unavailableReason": budget["blockedReason"],
                "acceptedHead": assignment["acceptedRevision"], "contextVersion": assignment["contextVersion"],
                "contextProtocolVersion": 2, "executionProtocolVersion": 2 if budget["enrolled"] else 1,
                "budget": budget}
