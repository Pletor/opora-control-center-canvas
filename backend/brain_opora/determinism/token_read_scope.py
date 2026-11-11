"""Supplied tokens constrain legacy reads, independently of the project's write gate."""
import re

from backend.brain_opora.determinism import brain_files, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.flow import workflows
from backend.brain_opora.determinism.heart_workspace_scope import permits as bootstrap_workspace
from backend.brain_opora.determinism.token_scoped_reads import PATHS

# These exact reads carry no project content; gate routes authenticate their own session/record.
PUBLIC_METADATA = {"/api/health", "/api/flow/node-types", "/api/gate/kinds"}
GLOBAL_REGISTRY = {"/api/bootstrap", "/api/projects", "/api/project-list"}


def denied(message):
    raise GateError(403, "gate_scope", message, "Use the authenticated project/workspace or a scoped capability.")


def _owner(service, path):
    match = re.fullmatch(r"/api/(?:flow|library)/(workflows|versions|runs|node-runs|flows)/([^/]+)(?:/.*)?", path)
    if not match:
        return False, None
    kind, identifier = match.groups()
    with service.registry_lock:
        try:
            if kind == "node-runs":
                row = service.db.execute("SELECT run_id FROM flow_node_runs WHERE id=?", (identifier,)).fetchone()
                if not row:
                    denied("Flow target is not available in this scope.")
                kind, identifier = "runs", row[0]
            arg = {"workflow_id" if kind in ("workflows", "flows") else "version_id" if kind == "versions" else "run_id": identifier}
            owner = workflows.workflow_of(service.db, **arg)
            if owner is None:
                denied("Flow target is not available in this scope.")
            return True, owner["project_id"]
        except (LookupError, KeyError):
            denied("Flow target is not available in this scope.")


def _workspace_allowed(service, session, workspace, path, method):
    if workspace == session["workspace_id"]:
        return True
    if session["role"] != "heart":
        return False
    # Existing explicit delegation: a main Heart may use its project's saved active workspace.
    if session["workspace_id"] == "main":
        active = brain_files.active_workspace(brain_files.brain_dir(service, session["project_id"]))
        if active and active == workspace:
            return True
        if bootstrap_workspace(service, session["project_id"], workspace, path, method):
            return True
    # Existing CLI discovery only. The view is still restricted to this project.
    return method in ("GET", "HEAD") and path == "/api/view" and workspace == "main"


def enforce(service, method, path, header, query, body=None):
    """Return verified identity or None. Caller must keep token requests attributed to this agent."""
    if not header:
        return None
    session = tokens.verify(service, header)
    if session is None:
        raise GateError(401, "gate_token_invalid", "Supplied gate token is invalid or revoked.", "Obtain a valid scoped session.")
    body = body if isinstance(body, dict) else {}
    projects = [value for source in (query, body) for key in ("project", "project_id", "of")
                if (value := source.get(key)) not in (None, "")]
    if any(value != session["project_id"] for value in projects):
        denied("Token does not authorize the requested project.")
    for source in (query, body):
        for key in ("workspace", "workspace_id", "ofWorkspace"):
            value = source.get(key)
            if value not in (None, "") and not _workspace_allowed(service, session, value, path, method):
                denied("Token does not authorize the requested workspace.")
    found, owner = _owner(service, path)
    if found:
        if owner is not None and owner != session["project_id"]:
            denied("Flow target belongs to another project.")
        if owner is None and method in ("GET", "HEAD") and not re.fullmatch(r"/api/library/flows/[^/]+/brief", path):
            denied("Global workflow records include cross-project lineage; use a scoped capability.")
        return session
    if method not in ("GET", "HEAD"):
        return session  # Native writes retain their domain permissions after ownership verification.
    if path in GLOBAL_REGISTRY:
        denied("Global registry reads are not a project-scoped agent capability.")
    scoped = any(re.fullmatch(re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(pattern)), path) for pattern in PATHS)
    # OP-80B255.pin: immutable public plugin ZIPs carry no project content; keep token/scope checks above.
    if re.fullmatch(r"/api/brain-registry/pins/[a-z0-9][a-z0-9-]{0,63}@[0-9a-f]{12}\.zip", path):
        return session
    if (projects and scoped) or path in PUBLIC_METADATA or path == "/api/gate" or path.startswith("/api/gate/"):
        return session
    denied("Token-authenticated read requires an explicit project or an audited ownership resolver.")
