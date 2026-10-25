"""GitHub repository binding of a folder-sourced project (docs/oporahub-github.md#projekt-z-lokální-složky).

A project whose source is a local folder has no repository in its metadata, so PR
reconciliation, review evidence and merge observation had nothing to bind to. A human
binds the folder to `owner/repo` + branch once; the binding is validated against the
folder on disk (`origin` must be that GitHub repository, the branch must exist) and then
lives in the registry as project metadata. Request URLs never grant authority: every
later caller reads the stored binding through `opora_review_scope.configuration`.

Binding re-queues execution PR links that were stored as `github-not-configured`, so PRs
linked before the binding enroll (and their merges are observed) without a new link. Binding
again re-queues links that failed because GitHub was unreachable or the token was missing
(`github-unavailable`, `github-auth-missing`), so a human can retry them after fixing the token."""
import re

from backend.canvas.opora_changesets import stamp
from backend.integrations.gitio import git

REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_-][A-Za-z0-9._-]*")
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
PAYLOAD = {"project", "repository", "branch"}


def read_binding(service, pid):
    """Stored binding {repository, branch, boundAt} or None. Registry read under the leaf lock."""
    with service.registry_lock:
        row = service.db.execute("SELECT repository,branch,bound_at FROM project_repository_bindings WHERE project_id=?",
                                 (pid,)).fetchone()
    return None if row is None else {"repository": row[0], "branch": row[1], "boundAt": row[2]}


def _folder_source(service, pid):
    if not isinstance(pid, str) or pid == "draft":
        raise ValueError("Repozitář lze připojit jen k projektu z lokální složky.")
    source = service.project_hub.source_info(service.row("projects", pid))
    if source["sourceKind"] != "local" or not source.get("sourcePath"):
        raise ValueError("Repozitář lze připojit jen k projektu z lokální složky.")
    return source["sourcePath"]


def detected_repository(path):
    """`owner/repo` of the folder's GitHub `origin`, or None when it is not a GitHub checkout."""
    from backend.canvas.opora_review_scope import github_repository  # scope imports this module
    origin = git(path, "remote", "get-url", "origin", timeout=10, optional=True)
    try:
        return github_repository(origin.strip()) if origin else None
    except ValueError:
        return None


def _branch_exists(path, branch):
    return any(git(path, "rev-parse", "--verify", "--quiet", ref, timeout=10, optional=True)
               for ref in (f"refs/remotes/origin/{branch}", f"refs/heads/{branch}"))


def _validate(payload):
    if not isinstance(payload, dict) or set(payload) != PAYLOAD:
        raise ValueError("Připojení repozitáře přijímá jen project, repository a branch.")
    repository, branch = payload["repository"], payload["branch"]
    if (not isinstance(repository, str) or len(repository) > 255 or ".." in repository
            or REPOSITORY.fullmatch(repository.removesuffix(".git")) is None):
        raise ValueError("Repozitář zadejte jako owner/název.")
    if (not isinstance(branch, str) or BRANCH.fullmatch(branch) is None or ".." in branch or "//" in branch
            or branch.endswith(("/", ".", ".lock"))):
        raise ValueError("Neplatný název větve.")
    return payload["project"], repository.removesuffix(".git").casefold(), branch


def status(service, pid, actor):
    """What the panel shows; reads `origin` from disk but never writes. `applies` is false for git-cloned projects."""
    binding, reason, detected, applies = None, None, None, True
    try:
        path = _folder_source(service, pid)
        binding, detected = read_binding(service, pid), detected_repository(path)
        if detected is None:
            reason = "Složka projektu není Git checkout s GitHub remote origin."
    except ValueError as error:
        reason, applies = str(error), False
    bindable = reason is None
    return {"project": pid, "applies": applies, "bindable": bindable, "binding": binding, "detectedRepository": detected,
            "canConfigure": actor == "human" and bindable,
            "unavailableReason": reason or (None if actor == "human" else "Připojení repozitáře patří člověku v UI.")}


def _requeue(db, pid, repository):
    """Links stored before the binding enroll on the next loop tick; other repositories stay untouched."""
    with db:
        db.execute("BEGIN IMMEDIATE")
        return db.execute(
            "UPDATE opora_execution_pull_requests SET enrollment='pending',enrollment_error=NULL,"
            "enrollment_retry_at=NULL,enrollment_failures=0,updated_at=? WHERE project_id=? AND repository=? "
            "AND ((enrollment='unavailable' AND enrollment_error='github-not-configured') "
            "OR (enrollment='failed' AND enrollment_error IN ('github-unavailable','github-auth-missing')))",
            (stamp(), pid, repository)).rowcount


def bind(service, payload, by):
    """Human-only (route-checked). Git reads run before any lock; the source is re-read under the locks."""
    pid, repository, branch = _validate(payload)
    path = _folder_source(service, pid)
    detected = detected_repository(path)
    if detected is None:
        raise ValueError("Složka projektu není Git checkout s GitHub remote origin.")
    if detected != repository:
        raise ValueError(f"Remote origin složky ukazuje na {detected}, ne na {repository}.")
    if not _branch_exists(path, branch):
        raise ValueError(f"Větev {branch} ve složce projektu neexistuje (ani jako origin/{branch}).")
    with service.graph_lock_for(pid), service.lock_for(pid):
        if _folder_source(service, pid) != path:
            raise ValueError("Zdroj projektu se mezitím změnil. Zkuste to znovu.")
        current = read_binding(service, pid)
        if current is not None and (current["repository"], current["branch"]) != (repository, branch):
            raise ValueError("Projekt už má připojený jiný repozitář. Nejprve ho odpojte.")
        if current is None:
            with service.registry_lock, service.db:
                service.db.execute("INSERT INTO project_repository_bindings VALUES(?,?,?,?,?)",
                                   (pid, repository, branch, stamp(), by["kind"]))
        requeued = _requeue(service.db_for(pid), pid, repository)
    return {**status(service, pid, "human"), "requeuedLinks": requeued}


def unbind(service, payload, by):
    if not isinstance(payload, dict) or set(payload) != {"project"}:
        raise ValueError("Odpojení repozitáře přijímá jen project.")
    pid = payload["project"]
    _folder_source(service, pid)
    with service.graph_lock_for(pid), service.lock_for(pid), service.registry_lock, service.db:
        service.db.execute("DELETE FROM project_repository_bindings WHERE project_id=?", (pid,))
    return status(service, pid, by["kind"])
