"""Immutable content proposals and explicit field-level rebase, without native writes."""
from copy import deepcopy

from backend.canvas.graph import digest
from backend.canvas.opora_change_validation import scope, subject
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_content_sources import capture_content
from backend.canvas.opora_content_validation import validate_value
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords


def entry_key(item):
    return item["kind"], item["target"], item["field"]


def index(entries):
    return {entry_key(item): item for item in entries}


def manifest_entries(repo, revision):
    record = repo.read(revision)
    identifier = record.get("contentManifestId")
    return ContentRecords(repo.db, *repo.scope).read(identifier, manifest=True)["entries"] if identifier else None


class OporaContentChanges:
    def __init__(self, canvas):
        self.canvas = canvas

    def current(self, project, workspace):
        db = self.canvas.db_for(project)
        repo = ChangesetRepository(db, project, workspace)
        head = repo.head()
        view = self.canvas.view(project, workspace)
        if view["readOnly"] or head is None:
            raise ValueError("Content proposals require a writable accepted plan.")
        entries, observations = capture_content(self.canvas, project, workspace, view["graph"])
        return {"acceptedHead": head, "graphDigest": view["digest"], "entries": entries,
                "acceptedEntries": manifest_entries(repo, head), "observations": observations,
                "graph": view["graph"]}

    def derive(self, project, workspace, current, changes, author, label, supersedes=None):
        if not isinstance(changes, list) or not 1 <= len(changes) <= 128:
            raise ValueError("Content proposal requires 1 through 128 changes.")
        live = index(current["entries"])
        accepted = index(current["acceptedEntries"] or [])
        result, seen = [], set()
        for item in changes:
            if not isinstance(item, dict) or set(item) != {"kind", "target", "field", "value"}:
                raise ValueError("Invalid content change fields.")
            key = entry_key(item)
            if key not in live or key in seen:
                raise ValueError("Content target is absent or duplicated.")
            validate_value(item["kind"], item["field"], item["value"])
            seen.add(key)
            observation = current["observations"][key]
            change = {**deepcopy(item), "before": deepcopy(live[key]["value"]),
                      "acceptedBefore": deepcopy(accepted.get(key)),
                      "observedOwner": observation["ownerWorkspace"], "observedRound": observation["round"]}
            if "revision" in observation:
                change["observedRevision"] = observation["revision"]
            result.append(change)
        base = current["entries"] if current["acceptedEntries"] is None else []
        from backend.canvas.opora_content_sources import preview_config_changes
        state = DesktopV3State(self.canvas).current(project, workspace)["state"]
        preview_config_changes(state, [item for item in result if item["kind"] == "config"], current["graph"])
        return {"schemaVersion": 1, "kind": "content-proposal", "project": project, "workspace": workspace,
                "parentRevision": current["acceptedHead"], "graphDigest": current["graphDigest"],
                "subject": label, "by": author, "createdAt": stamp(), "supersedes": supersedes,
                "requiresBaseContentAdoption": current["acceptedEntries"] is None,
                "baseContentDigest": digest(base), "baseContent": deepcopy(base), "changes": sorted(result, key=entry_key)}

    def create(self, payload, by):
        if set(payload) != {"project", "workspace", "expectedAcceptedHead", "subject", "changes"}:
            raise ValueError("Invalid content proposal fields.")
        project, workspace = scope(payload)
        author, label = _author(by, allow_agent=True), subject(payload)
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                current = self.current(project, workspace)
                if current["acceptedHead"] != payload["expectedAcceptedHead"]:
                    raise ValueError("Accepted content head changed.")
                record = self.derive(project, workspace, current, payload["changes"], author, label)
                return ContentRecords(db, project, workspace).insert(record)

    def read(self, project, workspace, identifier):
        scope({"project": project, "workspace": workspace})
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            repo = ContentRecords(self.canvas.db_for(project), project, workspace)
            return {"proposal": repo.read(identifier), "accepted": repo.accepted(identifier),
                    "acceptedHead": ChangesetRepository(repo.db, project, workspace).head(),
                    "readOnly": self.canvas.view(project, workspace)["readOnly"]}

    def list(self, project, workspace):
        scope({"project": project, "workspace": workspace})
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            repo = ContentRecords(self.canvas.db_for(project), project, workspace)
            keys = ("id", "kind", "subject", "by", "createdAt", "parentRevision", "supersedes", "requiresBaseContentAdoption")
            head = ChangesetRepository(repo.db, project, workspace).head()
            revision = ChangesetRepository(repo.db, project, workspace).read(head) if head else {}
            return {"items": [{**{key: item[key] for key in keys}, "accepted": repo.accepted(item["id"]) is not None,
                               "changeCount": len(item["changes"])}
                              for item in repo.proposals()],
                    "acceptedHead": head, "contentManifestId": revision.get("contentManifestId"),
                    "readOnly": self.canvas.view(project, workspace)["readOnly"]}

    def rebase(self, identifier, payload, by):
        if set(payload) != {"project", "workspace", "expectedAcceptedHead"}:
            raise ValueError("Invalid content rebase fields.")
        project, workspace = scope(payload)
        author = _author(by, allow_agent=True)
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                repo = ContentRecords(db, project, workspace)
                old, current = repo.read(identifier), self.current(project, workspace)
                if current["acceptedHead"] != payload["expectedAcceptedHead"] or repo.accepted(identifier):
                    raise ValueError("Content rebase head changed or proposal was already accepted.")
                conflicts = content_conflicts(old, current, rebase=True)
                if conflicts:
                    return {"rebased": False, "proposalId": identifier, "proposal": None, "conflicts": conflicts}
                changes = [{key: item[key] for key in ("kind", "target", "field", "value")} for item in old["changes"]]
                record = self.derive(project, workspace, current, changes, author, old["subject"], identifier)
                return {"proposal": repo.insert(record), "rebased": True, "conflicts": []}


def content_conflicts(proposal, current, *, rebase=False):
    live, accepted = index(current["entries"]), index(current["acceptedEntries"] or [])
    base = index(proposal["baseContent"])
    result = []
    for item in proposal["changes"]:
        key = entry_key(item)
        observed = current["observations"].get(key)
        expected = item["acceptedBefore"]
        if rebase and expected is None and proposal["requiresBaseContentAdoption"] and current["acceptedEntries"] is not None:
            expected = base.get(key)
        if (key not in live or observed is None or live[key]["value"] != item["before"]
                or observed["ownerWorkspace"] != item["observedOwner"]
                or observed["round"] != item["observedRound"]
                or observed.get("revision") != item.get("observedRevision") or accepted.get(key) != expected):
            result.append({"kind": item["kind"], "target": item["target"], "field": item["field"],
                           "reason": "Content, accepted value, owner, revision or card round changed."})
    return result
