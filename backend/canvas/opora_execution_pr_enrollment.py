"""Deterministic auto-enrollment of a linked execution PR into durable reconciliation.

The caller holds graph -> project locks and an open BEGIN IMMEDIATE transaction. The
PR identity was read from GitHub before the locks were taken. Enrollment reuses the
existing binding/control/job authority; it grants no plan acceptance or review."""
import time

from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_hub_store import content_id
from backend.canvas.opora_reconciliation_validation import AUTO_ENROLL_AUTHOR
from backend.canvas.opora_review_scope import configuration
from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs


def retry_delay(failures):
    return min(3600, 30 * 2 ** min(failures, 7))


def link_identity(project, workspace, execution_id, repository, number):
    """Stable 40-hex identity of the link; stored as the binding's identity evidence reference."""
    return content_id({"kind": "execution-pull-request", "project": project, "workspace": workspace,
                       "executionId": execution_id, "repository": repository, "number": number})


def configured(service, project):
    try:
        return configuration(service, project)
    except ValueError:
        return None


AUTH_MISSING = "github-auth-missing"
AUTH_INVALID = "github-auth-invalid"
AUTH = (AUTH_MISSING, AUTH_INVALID)
# Failed links a restart retries once: a token problem (older rows stored a rejected token as
# `github-unavailable`) is fixed by replacing the token and restarting, never by a new link.
HEALABLE = ("github-unavailable",) + AUTH


def fail(links, row, code, now, *, retry):
    """A missing or rejected token needs a human (attention) but heals once the token is fixed: it keeps retrying."""
    from backend.app import error_log

    failures = row["enrollment_failures"] + 1
    extra = {}
    if code in AUTH:
        retry, extra = True, {"attention": code}
    # OP-32F3B3.4: enrollment_error byl jen sloupec; frontou, volající drží zámky a transakci projektu
    error_log.submit("card", "exception", f"PR karty se nezapsal do sledování: {code}", project=links.scope[0],
                     workspace=links.scope[1], subject=row["execution_id"], severity="warn" if retry else "error",
                     lever="Nahradit GitHub token a restartovat OPORU." if code in AUTH else
                     "Zkontrolovat PR a konfiguraci review projektu (repozitář, větev).",
                     data={"code": code, "failures": failures, "retry": retry, "pr": row["number"]})
    return links.update(row["execution_id"], enrollment="pending" if retry else "failed", enrollment_error=code,
                        enrollment_failures=failures, enrollment_retry_at=now + retry_delay(failures) if retry else None,
                        updated_at=stamp(), **extra)


def apply_enrollment(service, links, row, pr, now=None):
    """Bind (or reuse the enabled binding of) the observed PR; returns the updated link row."""
    now = time.time() if now is None else now
    project, workspace = links.scope
    config = configured(service, project)
    if config is None:
        return links.update(row["execution_id"], enrollment="unavailable", enrollment_error="github-not-configured",
                            enrollment_retry_at=None, updated_at=stamp())
    if (pr["repository"]["fullName"] != config["repository"] or pr["number"] != row["number"]
            or row["repository"] != config["repository"] or pr["baseRef"] != config["branch"]):
        return fail(links, row, "github-identity-mismatch", now, retry=False)
    if pr["headRepoId"] is None:
        return fail(links, row, "head-repository-missing", now, retry=False)
    repo = ReconciliationRepository(links.db, project, workspace)
    binding = repo.enabled_for(pr["repository"]["id"], pr["id"])
    if binding is None:
        binding = repo.insert("binding", {
            "schemaVersion": 1, "project": project, "workspace": workspace,
            "acceptedRevision": row["accepted_revision"],
            "identityEvidenceId": link_identity(project, workspace, row["execution_id"], row["repository"], row["number"]),
            "repository": {"id": pr["repository"]["id"], "fullName": config["repository"], "baseBranch": config["branch"]},
            "pr": {"id": pr["id"], "number": pr["number"], "headRepoId": pr["headRepoId"]},
            "enrolledHeadSha": pr["headSha"], "configuration": config, "intervalSeconds": 300,
            "by": AUTO_ENROLL_AUTHOR, "createdAt": stamp()})
        control = repo.activate_control({
            "schemaVersion": 1, "project": project, "workspace": workspace, "bindingId": binding["id"],
            "parentControlId": None, "generation": 1, "action": "auto-enroll", "enabled": True,
            "requestId": None, "requestDigest": None, "by": AUTO_ENROLL_AUTHOR, "createdAt": stamp()}, 0)
        ReconciliationJobs(links.db, project, workspace).create(binding, control, now)
    cleared = {"attention": None} if row["attention"] in AUTH else {}
    if row["enrollment_error"]:
        from backend.app import error_log

        error_log.resolve(source="card", project=project, subject=row["execution_id"])
    return links.update(row["execution_id"], binding_id=binding["id"], enrollment="enrolled", enrollment_error=None,
                        enrollment_retry_at=None, head_sha=pr["headSha"], head_ref=pr["headRef"], updated_at=stamp(),
                        **cleared)
