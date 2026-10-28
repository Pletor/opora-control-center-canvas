"""Validate original sparse evidence without rebinding the assignment or budget family."""
import hmac

from backend.canvas.graph import digest
from backend.canvas.opora_execution_context import pin_id, token
from backend.canvas.opora_execution_lineage import validate_accepted_lineage
from backend.editor.agent_packet.specification_sql_context import project_sql_context
from database.repositories import opora_context_bindings as bindings
from database.repositories import opora_execution_contexts as private
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_context_replay import replay


def _validate_context(canvas, repo, record):
    project, workspace = repo.scope
    identifier = pin_id(record)  # po re-pinu nový neměnný pin; původní zůstává jako doklad
    pin = private.read(repo.db, project, workspace, identifier)
    expected = {"schemaVersion", "snapshot", "metadata", "binding", "nodeId", "acceptedRevision",
                "contextVersion", "assignmentDigest"}
    if (set(pin) != expected or pin["schemaVersion"] != 1 or pin["nodeId"] != record["nodeId"]
            or pin["acceptedRevision"] != record["acceptedRevision"]
            or pin["assignmentDigest"] != record["assignmentDigest"]
            or digest(record["assignment"]) != record["assignmentDigest"]
            or pin["contextVersion"] != record["assignment"]["contextVersion"]):
        raise ValueError("Sparse execution origin does not match its immutable assignment.")
    before = bindings.checkpoint(canvas.db, project, workspace)
    if before != pin["binding"]:
        raise ValueError("Sparse execution source binding changed.")

    def project_rows(rows):
        return project_sql_context(rows, project, workspace, record["nodeId"], metadata=pin["metadata"])

    original = project_rows(pin["snapshot"]["rows"])
    opaque = token(private.key(repo.db, project), original, pin["acceptedRevision"], pin["binding"])
    if not hmac.compare_digest(opaque, pin["contextVersion"]):
        raise ValueError("Sparse execution origin context token does not match.")
    current = ChangesetRepository(repo.db, project, workspace).head()
    accepted = validate_accepted_lineage(repo.db, project, workspace, record["nodeId"],
                                        pin["acceptedRevision"], current)
    live = replay(repo.db, pin["snapshot"], project_rows)
    if before != bindings.checkpoint(canvas.db, project, workspace):
        raise ValueError("Sparse execution source binding changed during validation.")
    proof = {"contextProtocolVersion": 2, "originAcceptedRevision": pin["acceptedRevision"],
             "checkedAcceptedRevision": current, "acceptedScopeUnchanged": True,
             "liveScopeUnchanged": True, "acceptedRevisionsChecked": accepted["checkedCount"],
             "liveTransitionsChecked": live["transitionCount"]}
    private.proof(repo.db, project, workspace, identifier, proof)
    return proof


def validate_context(canvas, repo, record):
    try:
        with canvas.registry_lock:
            return _validate_context(canvas, repo, record)
    except (TypeError, KeyError, IndexError, AttributeError, RecursionError) as error:
        raise ValueError("Sparse execution context origin is malformed.") from error
