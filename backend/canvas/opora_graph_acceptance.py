"""Human graph/specification/manifest acceptance under one accepted-reference transaction."""
from backend.canvas.architecture_graph import split
from backend.canvas.authority import acts_as_human
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_build import merge, validate_application
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_graph_records import accepted_record, combined, preserved_content_manifest
from backend.canvas.opora_hub_store import canonical
from backend.canvas.opora_proposal_acceptance_guard import guard, seal
from backend.canvas.payload_errors import exact_fields
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority


class OporaGraphAcceptance:
    def __init__(self, service):
        self.service = service
        self.proposals = OporaGraphProposals(service)

    def accept(self, proposal_id, payload, by):
        from backend.canvas.opora_graph_change_acceptance import OporaGraphChangeAcceptance
        project, workspace = scope(payload)
        with self.service.lock_for(project):
            kind = self.proposals.repository(project, workspace).read(proposal_id)["kind"]
        if kind == "graph-changes":
            return OporaGraphChangeAcceptance(self.service).accept(proposal_id, payload, by)
        exact_fields(payload, {"project", "workspace", "expectedAcceptedHead", "expectedGraphDigest", "adoptBaseGraphDigest"},
                     "Přijetí návrhu grafu", {"project": "<projectId>", "workspace": "draft",
                                               "expectedAcceptedHead": "<heads.acceptedHead nebo null>",
                                               "expectedGraphDigest": "<heads.graphDigest>",
                                               "adoptBaseGraphDigest": "<graphDigest návrhu, když hlava nemá graf; jinak null>"})
        project, workspace = scope(payload)
        author = _author(by)
        if not acts_as_human(author["kind"]):
            raise ValueError("Graph additions require explicit human acceptance.")
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.proposals.repository(project, workspace)
            specs = self.proposals.specifications.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                proposal = repo.read(proposal_id)
                previous = repo.accepted(proposal_id)
                if previous:
                    result = accepted_record(specs, previous)
                    if result.get("kind") not in ("graph-acceptance", "graph-baseline"):
                        raise ValueError("Invalid graph acceptance record.")
                    repo.read(result["graphManifestId"], manifest=True)
                    return result
                context, graph, manifest, missing = self.proposals.current(project, workspace)
                self.proposals.expect(context, payload["expectedAcceptedHead"], payload["expectedGraphDigest"])
                if (proposal["parentRevision"] != context["acceptedHead"] or proposal["graphDigest"] != context["graphDigest"]
                        or proposal["parentGraphManifestId"] != (manifest["id"] if manifest else None)):
                    raise ValueError("Graph proposal requires explicit rebase.")
                expected_adoption = proposal["graphDigest"] if manifest is None else None
                if payload["adoptBaseGraphDigest"] != expected_adoption:
                    raise ValueError("Explicit adoption of the displayed base graph is required.")
                if proposal["adoptionDocuments"] != (missing if manifest is None else []):
                    raise ValueError("Base adoption documents changed; create a rebased proposal.")
                accepted_graph = combined(manifest) if manifest else None
                updated = validate_application(self.service, project, workspace, graph, proposal, accepted_graph)
                approved = merge(accepted_graph if manifest else graph, proposal["additions"])
                architecture, content = split(updated)
                if architecture != split(graph)[0]:
                    raise ValueError("Graph additions cannot mutate shared architecture.")
                authorization = guard(repo.db, project, workspace, "graph-addition", proposal_id)
                self.write_graph(repo.db, project, workspace, content)
                documents = {item["nodeId"]: item for item in context["acceptedDocuments"]}
                for item in proposal["adoptionDocuments"]:
                    documents[item["nodeId"]] = item
                for item in proposal["specifications"]:
                    saved = self.service.specs.save_in_transaction((project, workspace, item["nodeId"]), 0, item["fields"])
                    documents[item["nodeId"]] = {"nodeId": item["nodeId"], "ownerWorkspace": workspace,
                                                 "revision": saved["revision"], "fields": saved["fields"]}
                boundary, approved_content = split(approved)
                graph_manifest = repo.insert({"schemaVersion": 1, "kind": "graph-manifest", "project": project,
                                              "workspace": workspace, "graph": approved_content,
                                              "architectureContext": boundary}, manifest=True)
                kind = "graph-acceptance" if context["acceptedHead"] else "graph-baseline"
                result = specs.insert({"project": project, "workspace": workspace, "kind": kind,
                                       "parentRevision": context["acceptedHead"], "proposalId": proposal_id,
                                       "subject": proposal["subject"], "by": author, "createdAt": stamp(),
                                       "graphManifestId": graph_manifest["id"],
                                       **preserved_content_manifest(specs, context["acceptedHead"]),
                                       "documents": [documents[key] for key in sorted(documents)]})
                specs.advance(context["acceptedHead"], result["id"])
                seal(repo.db, project, workspace, authorization, result)
            return result

    def write_graph(self, db, project, workspace, content):
        if project == "draft" or self.service.project_hub.source_info(self.service.row("projects", project))["sourceKind"] != "git":
            from backend.canvas.opora_context_graph_storage import save_sql_draft
            if save_sql_draft(self.service, project, workspace, content):
                return
            changed = db.execute("UPDATE drafts SET graph=? WHERE id=?", (canonical(content), project))
            if changed.rowcount != 1:
                raise ValueError("Workspace graph no longer exists.")
        else:
            authority = WorkspaceGraphAuthority(db, project, workspace)
            current = authority.read()
            if current is None:
                authority.enroll(content)
            else:
                authority.write(content, expected_revision=current["revision"])
