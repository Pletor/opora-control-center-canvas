"""Explicit token scope, including reads; generic application GETs are intentionally open."""
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.graph import valid_id
from backend.canvas.payload_errors import InvalidPayload


def authenticate(service, request, project, workspace):
    if not valid_id(project) or not valid_id(workspace):
        raise InvalidPayload("Explicit valid project and workspace are required.", field="scope")
    session = gate.authenticate(service, request.headers.get(tokens.HEADER), project, ("heart",))
    if session["workspace_id"] != workspace:
        raise GateError(403, "gate_scope", "Capability workspace differs from the authenticated Heart session.",
                        "Use the workspace of this Heart token.")
    # This validates an existing scope only after authenticating it; no foreign graph is loaded.
    service.view(project, workspace)
    return session
