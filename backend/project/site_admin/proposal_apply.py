"""Durable Site bundle acceptance: recover by exact before/after digests, never overwrite drift."""
import json
from datetime import UTC, datetime

from backend.project.site_admin import proposal_attachments as files
from backend.project.site_admin import store
from backend.project.site_admin.design_system import normalize
from backend.project.site_admin.tokens import shape


class RecoveryNeeded(store.SiteAdminConflict):
    def __init__(self, proposal, targets, reason):
        self.detail = {"code": "site_recovery_needed", "proposalId": proposal, "targets": targets, "reason": reason}
        super().__init__("Site acceptance recovery needed: " + reason)


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def journal_path(proposal_id):
    return "proposals/apply-" + proposal_id + ".json"


def load(service, project, proposal_id):
    raw = files.read(service, project, journal_path(proposal_id))
    return json.loads(raw) if raw else None


def active(service, project):
    folder = files.path(service, project, "proposals")
    found = []
    for item in folder.glob("apply-sp_*.json") if folder.exists() else []:
        journal = json.loads(files.read(service, project, "proposals/" + item.name))
        if journal.get("state") != "complete":
            found.append(journal)
    return found


def guard(service, project, allowed=None):
    for journal in active(service, project):
        if journal["proposalId"] != allowed:
            raise RecoveryNeeded(journal["proposalId"], observed(service, project, journal), "Finish the interrupted reviewed bundle first.")


def observed(service, project, journal):
    result = []
    for item in journal["targets"]:
        try:
            actual = files.digest(files.read(service, project, item["path"]))
        except (OSError, store.SiteAdminInvalid) as error:
            result.append({"path": item["path"], "before": item["before"], "after": item["after"],
                           "actual": None, "state": "conflict", "reason": str(error)})
            continue
        state = "after" if actual == item["after"] else "before" if actual == item["before"] else "conflict"
        result.append({"path": item["path"], "before": item["before"], "after": item["after"], "actual": actual, "state": state})
    return result


def start(service, project, proposal, expected_revision):
    shape(type(expected_revision) is int and expected_revision >= 0, "expectedRevision must be a nonnegative integer.")
    current = store.read(service, project)
    if proposal["baseRevision"] != current["revision"] or expected_revision != current["revision"]:
        raise store.SiteAdminConflict("Site proposal base revision changed.")
    files.quota(service, project, proposal["attachments"])
    targets = []
    for attachment in proposal["attachments"]:
        before = files.read(service, project, attachment["path"])
        if files.digest(before) != attachment["baseDigest"]:
            raise store.SiteAdminConflict("Site attachment changed since review: " + attachment["path"])
        after = files.blob(service, project, attachment["sha256"]) if attachment["sha256"] else None
        if after is not None:
            store._checked(attachment["name"], after, store.ASSET_TYPES if attachment["kind"] == "asset" else store.FONT_TYPES,
                           store.ASSET_LIMIT if attachment["kind"] == "asset" else store.FONT_LIMIT)
        targets.append({"path": attachment["path"], "before": files.save_blob(service, project, before),
                        "after": files.digest(after)})
    document, notes = normalize(proposal["document"], current)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    saved = {**document, "revision": current["revision"] + 1,
             "lastChange": {"by": "human", "via": "page", "at": now, "note": "Accepted Site bundle " + proposal["id"]}}
    accepted = {**proposal, "status": "accepted", "decidedAt": now}
    for relative, after in (("design-system.json", encode(saved)), ("proposals/" + proposal["id"] + ".json", encode(accepted))):
        targets.append({"path": relative, "before": files.save_blob(service, project, files.read(service, project, relative)),
                        "after": files.save_blob(service, project, after)})
    journal = {"v": 1, "proposalId": proposal["id"], "project": project, "state": "applying",
               "baseRevision": current["revision"], "targets": targets, "saved": saved, "notes": notes, "proposal": accepted}
    files.write(service, project, journal_path(proposal["id"]), encode(journal))
    return journal


def accept(service, project, proposal, expected_revision):
    guard(service, project, proposal["id"])
    journal = load(service, project, proposal["id"])
    if journal is None:
        journal = start(service, project, proposal, expected_revision)
    shape(type(expected_revision) is int and expected_revision in (journal["baseRevision"], journal["saved"]["revision"]),
          "Retry must use the original or resulting reviewed revision.")
    if journal["state"] == "complete":
        return journal["saved"], journal["notes"], journal["proposal"]
    states = observed(service, project, journal)
    if any(item["state"] == "conflict" for item in states):
        raise RecoveryNeeded(proposal["id"], states, "A target differs from both reviewed states; no files were overwritten.")
    # Read all immutable bytes before touching any live target, including on recovery.
    try:
        files.quota(service, project, journal["proposal"]["attachments"])
        contents = {item["after"]: files.blob(service, project, item["after"]) for item in journal["targets"] if item["after"]}
    except (OSError, store.SiteAdminInvalid) as error:
        raise RecoveryNeeded(proposal["id"], states, str(error)) from error
    try:
        for item in states:
            if item["state"] == "before":
                # A native writer cannot interleave under the project lock; still fence external edits per target.
                if files.digest(files.read(service, project, item["path"])) != item["before"]:
                    raise RecoveryNeeded(proposal["id"], observed(service, project, journal), "Target changed during recovery.")
                files.write(service, project, item["path"], contents.get(item["after"]))
        actual = observed(service, project, journal)
        if any(item["state"] != "after" for item in actual):
            raise RecoveryNeeded(proposal["id"], actual, "Bundle readback differs from reviewed result.")
        files.write(service, project, journal_path(proposal["id"]), encode({**journal, "state": "complete"}))
    except OSError as error:
        raise RecoveryNeeded(proposal["id"], observed(service, project, journal), str(error)) from error
    return journal["saved"], journal["notes"], journal["proposal"]
