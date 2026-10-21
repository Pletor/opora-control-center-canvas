"""Resolve evidence authority from project metadata, never from request repository URLs."""
import re

from backend.canvas.opora_change_validation import identifier, scope
from database.repositories.opora_changesets import ChangesetRepository

_REPO = r"([A-Za-z0-9-]+/[A-Za-z0-9_-][A-Za-z0-9._-]*?)"


def github_repository(value):
    if not isinstance(value, str):
        raise ValueError("Projekt nemá platný GitHub repozitář.")  # noqa: TRY004 - API validation
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)" + _REPO + r"(?:\.git)?/?", value)
    if not match or ".." in match[1]:
        raise ValueError("Projekt nemá platný GitHub repozitář.")
    return match[1].casefold()


def configuration(service, pid):
    if pid == "draft":
        raise ValueError("Lokální návrh nemá připojený GitHub repozitář.")
    row = service.row("projects", pid)
    source = service.project_hub.source_info(row)
    folder = service.folder(pid).read()["source"]
    if source["sourceKind"] != "git" or folder.get("kind") != "git":
        raise ValueError("Projekt nemá připojený Git repozitář.")
    repository = github_repository(row.get("url"))
    branch = row.get("branch")
    if (github_repository(folder.get("value")) != repository
            or not isinstance(branch, str) or not branch or branch != folder.get("branch")):
        raise ValueError("Konfigurace repozitáře projektu není konzistentní.")
    return {"repository": repository, "branch": branch, "repoPath": row.get("repo"),
            "sourcePath": source.get("sourcePath")}


def context(service, pid, wid):
    scope({"project": pid, "workspace": wid})
    view = service.view(pid, wid)
    revisions = ChangesetRepository(service.db_for(pid), pid, wid)
    head = revisions.head()
    if head:
        revisions.read(head)
    reason, config = "", None
    try:
        config = configuration(service, pid)
    except ValueError as error:
        reason = str(error)
    if not reason and view["readOnly"]:
        reason = "Pracovní prostor je jen pro čtení."
    if not reason and not head:
        reason = "Nejprve přijměte výchozí zadání."
    return {"acceptedHead": head, "repository": config["repository"] if config else None,
            "available": not bool(reason), "unavailableReason": reason, "config": config}


def validate_request(payload):
    allowed = {"project", "workspace", "expectedAcceptedHead", "prNumber", "expectedHeadSha"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError("Import přijímá pouze identifikátory projektu, revize a PR.")
    pid, wid = scope(payload)
    identifier(payload.get("expectedAcceptedHead"))
    if type(payload.get("prNumber")) is not int or not 1 <= payload["prNumber"] <= 2147483647:
        raise ValueError("Neplatné číslo PR.")
    if "expectedHeadSha" in payload:
        identifier(payload["expectedHeadSha"])
    return pid, wid
