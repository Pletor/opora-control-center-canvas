"""Read the same retained-admission counter used by native experiment admission."""
import os

from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_verifications import OporaVerifications
from backend.library.harness_exploration import snapshot
from backend.library.harness_scope_config import ScopeNotConfigured
from backend.library.harness_verifier_plan import configuration
from backend.library.harness_verifier_records import KIND


def spent(db, project, workspace):
    return db.execute(
        "SELECT COUNT(*) FROM opora_verification_requests WHERE project_id=? AND workspace_id=? "
        "AND json_extract(record,'$.origin.kind')=?", (project, workspace, KIND)).fetchone()[0]


def read(canvas, project, workspace):
    validate({"project": project, "workspace": workspace}, set())
    status, limit = "disabled", None
    if os.environ.get("OPORA_HARNESS_VERIFIER", ""):
        try:
            config = configuration(project, workspace)
            if (config["project"], config["workspace"]) == (project, workspace):
                status, limit = "available", config["maxExperiments"]
            else:
                status = "not-configured-for-scope"
        except ScopeNotConfigured:
            status = "not-configured-for-scope"
        except (ValueError, KeyError, TypeError):
            status = "unavailable"
    with OporaVerifications(canvas).transaction(project, workspace) as repo:
        used = spent(repo.db, project, workspace)
        exploration = snapshot(repo.db, project, workspace)
    remaining = max(0, limit - used) if limit is not None else None
    return {"schema": "harness.experiment-capacity/1", "scope": {"project": project, "workspace": workspace},
            "status": status, "limit": limit, "admitted": used, "remaining": remaining,
            "exploration": exploration, "capacityAvailable": status == "available" and remaining > 0, "reservation": False,
            "meaning": "Cumulative native admissions, including failed and interrupted work. "
                       "A snapshot grants no execution authority or reservation; admission rechecks the transaction."}
