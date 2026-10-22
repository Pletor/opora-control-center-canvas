"""Specification proposals form immutable siblings without touching the working canvas."""
from datetime import UTC, datetime

from backend.canvas.opora_change_validation import (
    check_changes,
    documents,
    identifier,
    scope,
    specifications_version,
    subject,
)
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_proposal_acceptance_guard import bootstrap, seal
from database.repositories.opora_changesets import ChangesetRepository


def stamp():
    return datetime.now(UTC).isoformat(timespec="microseconds")


class OporaChangesets:
    def __init__(self, service):
        self.service = service

    def repository(self, pid, wid):
        return ChangesetRepository(self.service.db_for(pid), pid, wid)

    def context(self, pid, wid):
        scope({"project": pid, "workspace": wid})
        with self.service.graph_lock_for(pid), self.service.lock_for(pid), self.service.steady_reads(pid):
            view = self.service.view(pid, wid)
            repo = self.repository(pid, wid)
            head = repo.head()
            current = documents(self.service, pid, wid, view)
            accepted = repo.read(head)["documents"] if head else []
            return {"acceptedHead": head, "graphDigest": view["digest"], "documents": current,
                    "acceptedDocuments": accepted, "specificationsVersion": specifications_version(current),
                    "workingDiffers": current != accepted, "readOnly": view["readOnly"]}

    def baseline(self, payload, by):
        by = _author(by)
        if by["kind"] != "human":
            raise ValueError("Výchozí zadání přijímá člověk.")
        pid, wid = scope(payload)
        if "expectedAcceptedHead" not in payload or payload["expectedAcceptedHead"] is not None:
            raise ValueError("Výchozí zadání lze založit pouze před první přijatou revizí.")
        label = subject(payload)
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            current = self.context(pid, wid)
            if current["readOnly"]:
                raise ValueError("Pracovní prostor je jen pro čtení.")
            if current["acceptedHead"] is not None:
                raise ValueError("Výchozí zadání již existuje; změny přijímejte pomocí návrhů.")
            if not current["documents"]:
                raise ValueError("Nejprve vytvořte kartu na plátně; prázdné výchozí zadání nelze přijmout.")
            if (payload.get("expectedGraphDigest") != current["graphDigest"]
                    or payload.get("expectedSpecificationsVersion") != current["specificationsVersion"]):
                raise ValueError("Pracovní zadání se změnilo. Načtěte nový kontext.")
            repo = self.repository(pid, wid)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                authorization = bootstrap(repo.db, pid, wid)
                result = repo.insert({"project": pid, "workspace": wid, "kind": "baseline",
                                      "parentRevision": None, "proposalId": None, "subject": label,
                                      "by": by, "createdAt": stamp(), "documents": current["documents"]})
                repo.advance(None, result["id"])
                seal(repo.db, pid, wid, authorization, result)
            return result

    def create(self, payload, by):
        by = _author(by, allow_agent=True)
        pid, wid = scope(payload)
        parent = payload.get("parentRevision")
        identifier(parent)
        label = subject(payload)
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            current = self.context(pid, wid)
            if current["readOnly"]:
                raise ValueError("Pracovní prostor je jen pro čtení.")
            if current["acceptedHead"] != parent or payload.get("expectedGraphDigest") != current["graphDigest"]:
                raise ValueError("Přijatá revize nebo graf se změnily. Načtěte nový kontext.")
            changes = check_changes(payload, current["acceptedDocuments"], current["documents"])
            repo = self.repository(pid, wid)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                return {**repo.insert({"project": pid, "workspace": wid, "parentRevision": parent,
                                      "graphDigest": current["graphDigest"], "subject": label, "by": by,
                                      "createdAt": stamp(), "changes": changes, "supersedes": None}, proposal=True),
                        "accepted": False}

    def read(self, pid, wid, proposal_id):
        scope({"project": pid, "workspace": wid})
        with self.service.lock_for(pid):
            repo = self.repository(pid, wid)
            return {**repo.read(proposal_id, proposal=True), "accepted": repo.accepted(proposal_id)}

    def list(self, pid, wid):
        scope({"project": pid, "workspace": wid})
        with self.service.lock_for(pid):
            repo = self.repository(pid, wid)
            return {"items": repo.proposals(), "acceptedHead": repo.head()}

    def revision(self, pid, wid, revision_id):
        scope({"project": pid, "workspace": wid})
        with self.service.lock_for(pid):
            return self.repository(pid, wid).read(revision_id)

    def rebase(self, proposal_id, payload, by):
        by = _author(by, allow_agent=True)
        pid, wid = scope(payload)
        expected = payload.get("expectedAcceptedHead")
        identifier(expected)
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            repo = self.repository(pid, wid)
            old = repo.read(proposal_id, proposal=True)
            current = self.context(pid, wid)
            if current["readOnly"] or current["acceptedHead"] != expected:
                raise ValueError("Pracovní prostor je jen pro čtení nebo se přijatá revize změnila.")
            if repo.accepted(proposal_id) or old["parentRevision"] == expected:
                raise ValueError("Přenos vyžaduje nepřijatý návrh se starším rodičem.")
            if old["graphDigest"] != current["graphDigest"]:
                raise ValueError("Graf se změnil; vytvořte nový návrh.")
            accepted = {item["nodeId"]: item for item in current["acceptedDocuments"]}
            live = {item["nodeId"]: item for item in current["documents"]}
            for change in old["changes"]:
                observed = {"nodeId": change["nodeId"], "ownerWorkspace": change["ownerWorkspace"],
                            "revision": change["expectedRevision"], "fields": change["before"]}
                if (accepted.get(change["nodeId"]) != change["acceptedBefore"]
                        or live.get(change["nodeId"]) != observed):
                    raise ValueError("Zadání dotčené karty se změnilo; automatický přenos není možný.")
            content = {key: value for key, value in old.items() if key != "id"}
            content.update(parentRevision=expected, supersedes=proposal_id, by=by, createdAt=stamp())
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                return {**repo.insert(content, proposal=True), "accepted": False}
