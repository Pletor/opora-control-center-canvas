"""Explicit human review atomically writes native history and advances accepted content."""
from backend.canvas.authority import acts_as_human
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_content_changes import (
    OporaContentChanges,
    content_conflicts,
    entry_key,
    index,
)
from backend.canvas.opora_content_sources import capture_content, write_changes_in_transaction
from backend.canvas.opora_graph_records import preserved_manifest
from backend.canvas.opora_proposal_acceptance_guard import guard, seal
from backend.canvas.payload_errors import exact_fields
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords


class OporaContentAcceptance:
    def __init__(self, canvas):
        self.canvas, self.proposals = canvas, OporaContentChanges(canvas)

    def accept(self, identifier, payload, by):
        exact_fields(payload, {"project", "workspace", "expectedAcceptedHead", "reviewedProposalId", "adoptBaseContentDigest"},
                     "Přijetí změny obsahu", {"project": "<projectId>", "workspace": "draft",
                                               "expectedAcceptedHead": "<heads.acceptedHead>",
                                               "reviewedProposalId": "<id návrhu>",
                                               "adoptBaseContentDigest": "<baseContentDigest návrhu nebo null>"})
        author = _author(by, allow_agent=True)
        if not acts_as_human(author["kind"]) or payload["reviewedProposalId"] != identifier:
            raise ValueError("Explicit human review of this exact content proposal is required.")
        project, workspace = scope(payload)
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                repo, specs = ContentRecords(db, project, workspace), ChangesetRepository(db, project, workspace)
                proposal = repo.read(identifier)
                previous = repo.accepted(identifier)
                if previous:
                    return specs.read(previous)
                current = self.proposals.current(project, workspace)
                if current["acceptedHead"] != payload["expectedAcceptedHead"] or proposal["parentRevision"] != current["acceptedHead"]:
                    raise ValueError("Accepted content head changed; explicitly rebase the proposal.")
                if proposal["graphDigest"] != current["graphDigest"] or content_conflicts(proposal, current):
                    raise ValueError("Reviewed content preconditions changed; explicitly rebase the proposal.")
                adoption = proposal["baseContentDigest"] if proposal["requiresBaseContentAdoption"] else None
                if payload["adoptBaseContentDigest"] != adoption:
                    raise ValueError("Explicit adoption of the complete displayed base content is required.")
                if proposal["requiresBaseContentAdoption"] and current["entries"] != proposal["baseContent"]:
                    raise ValueError("Complete base content changed; explicitly rebase the proposal.")
                authorization = guard(db, project, workspace, "content", identifier)
                entries = index(proposal["baseContent"] if adoption else current["acceptedEntries"])
                write_changes_in_transaction(self.canvas, db, project, workspace, proposal["changes"], author["kind"], current["graph"])
                updated, _ = capture_content(self.canvas, project, workspace, current["graph"])
                live = index(updated)
                for item in proposal["changes"]:
                    entries[entry_key(item)] = live[entry_key(item)]
                manifest = repo.insert({"schemaVersion": 1, "kind": "content-manifest", "project": project,
                                        "workspace": workspace, "entries": sorted(entries.values(),
                                        key=lambda item: (*entry_key(item), item["ownerWorkspace"]))}, manifest=True)
                parent = specs.read(current["acceptedHead"])
                result = specs.insert({"project": project, "workspace": workspace, "kind": "acceptance",
                    "parentRevision": current["acceptedHead"], "proposalId": identifier, "subject": proposal["subject"],
                    "by": author, "createdAt": stamp(), "documents": parent["documents"],
                    **preserved_manifest(specs, current["acceptedHead"]), "contentManifestId": manifest["id"]})
                specs.advance(current["acceptedHead"], result["id"])
                seal(db, project, workspace, authorization, result)
                return result
