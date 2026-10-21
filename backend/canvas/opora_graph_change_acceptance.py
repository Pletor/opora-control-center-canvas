"""Graph edits, reviewed state, specifications and accepted reference commit together."""
from backend.canvas.architecture_graph import split
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_change_state import persist_state
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.opora_graph_records import accepted_record, preserved_content_manifest


class OporaGraphChangeAcceptance(OporaGraphAcceptance):
    def __init__(self, service):
        self.service, self.proposals = service, OporaGraphChanges(service)

    def accept(self, proposal_id, payload, by):
        if set(payload) != {"project", "workspace", "expectedAcceptedHead", "expectedGraphDigest",
                            "adoptBaseGraphDigest", "reviewedChangesId"}:
            raise ValueError("Invalid graph change acceptance fields.")
        project, workspace = scope(payload)
        author = _author(by)
        if author["kind"] != "human" or payload["reviewedChangesId"] != proposal_id or payload["adoptBaseGraphDigest"] is not None:
            raise ValueError("Explicit human review of these graph changes is required.")
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.proposals.repository(project, workspace)
            specs = self.proposals.specifications.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                proposal = repo.read(proposal_id)
                if proposal["kind"] != "graph-changes":
                    raise ValueError("Graph change acceptance requires a v2 proposal.")
                previous = repo.accepted(proposal_id)
                if previous:
                    return accepted_record(specs, previous)
                context, graph, manifest = self.proposals.current_change(project, workspace, proposal["plan"]["removeNodes"],
                                                                        proposal["plan"]["adoptArchitectureContext"])
                self.proposals.expect(context, payload["expectedAcceptedHead"], payload["expectedGraphDigest"])
                if (proposal["parentRevision"] != context["acceptedHead"] or proposal["graphDigest"] != context["graphDigest"]
                        or proposal["parentGraphManifestId"] != manifest["id"]):
                    raise ValueError("Graph change proposal requires explicit rebase.")
                derived = self.proposals.derive(project, workspace, graph, manifest, proposal["plan"], previous=proposal)
                if any(derived[key] != proposal[key] for key in derived):
                    raise ValueError("Reviewed graph or state changed; rebase the proposal.")
                self.write_graph(repo.db, project, workspace, split(proposal["resultGraph"])[1])
                persist_state(self.service, repo.db, project, workspace, proposal["stateEffects"], proposal["resultGraph"], actor=author["kind"])
                removed = set(proposal["plan"]["removeNodes"])
                if proposal["plan"]["adoptArchitectureContext"]:
                    removed.update(node["id"] for node in manifest["architectureContext"]["nodes"])
                documents = {item["nodeId"]: item for item in context["acceptedDocuments"] if item["nodeId"] not in removed}
                documents.update({item["nodeId"]: item for item in proposal["architectureDocuments"]})
                for item in proposal["specifications"]:
                    saved = self.service.specs.save_in_transaction((project, workspace, item["nodeId"]), 0, item["fields"])
                    documents[item["nodeId"]] = {"nodeId": item["nodeId"], "ownerWorkspace": workspace,
                                                 "revision": saved["revision"], "fields": saved["fields"]}
                boundary, approved = split(proposal["acceptedResultGraph"])
                accepted_manifest = repo.insert({"schemaVersion": 1, "kind": "graph-manifest", "project": project,
                    "workspace": workspace, "graph": approved, "architectureContext": boundary}, manifest=True)
                result = specs.insert({"project": project, "workspace": workspace, "kind": "graph-acceptance",
                    "parentRevision": context["acceptedHead"], "proposalId": proposal_id, "subject": proposal["subject"],
                    "by": author, "createdAt": stamp(), "graphManifestId": accepted_manifest["id"],
                    **preserved_content_manifest(specs, context["acceptedHead"]),
                    "documents": [documents[key] for key in sorted(documents)]})
                specs.advance(context["acceptedHead"], result["id"])
                return result
