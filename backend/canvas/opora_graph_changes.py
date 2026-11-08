"""Immutable graph edits use separate accepted and working preimages."""
from backend.canvas.opora_change_validation import scope, subject
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_build import unchanged_specifications
from backend.canvas.opora_graph_change_architecture import documents as architecture_documents
from backend.canvas.opora_graph_change_build import build, validate_sources
from backend.canvas.opora_graph_change_state import prepare_state
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_graph_records import accepted_record, combined
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.opora_graph_changes import GraphChanges


def rewired(record):
    return sorted(item["id"] for item in record["changes"]["edges"] if item["operation"] == "update"
                  and (item["acceptedBefore"] != item["proposedAccepted"] or item["workingBefore"] != item["proposedWorking"]))


class OporaGraphChanges(OporaGraphProposals):
    def repository(self, project, workspace):
        return GraphChanges(self.service.db_for(project), project, workspace)

    def observed(self, project, workspace):
        context = self.specifications.context(project, workspace)
        revision = accepted_record(self.specifications.repository(project, workspace), context["acceptedHead"]) if context["acceptedHead"] else {}
        manifest_id = revision.get("graphManifestId")
        manifest = self.repository(project, workspace).read(manifest_id, manifest=True) if manifest_id else None
        graph = self.service.view(project, workspace)["graph"]
        return context, graph, manifest

    def context(self, project, workspace):
        from backend.canvas.opora_graph_change_architecture import context as architecture_context
        scope({"project": project, "workspace": workspace})
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            context, graph, manifest = self.observed(project, workspace)
            accepted = combined(manifest) if manifest else None
            ids = {item["nodeId"] for item in context["acceptedDocuments"]}
            missing = [item for item in context["documents"] if item["nodeId"] not in ids]
            return {**{key: context[key] for key in ("acceptedHead", "graphDigest", "readOnly")},
                    "graphManifestId": manifest["id"] if manifest else None, "requiresBaseAdoption": manifest is None,
                    "adoptionDocuments": missing if manifest is None else [], "acceptedGraph": accepted, "workingGraph": graph,
                    "architectureContext": architecture_context(accepted, graph),
                    "stateRevision": DesktopV3State(self.service).current(project, workspace)["revision"]}

    def current_change(self, project, workspace, removed, adopt_architecture=False):
        context, graph, manifest = self.observed(project, workspace)
        if context["readOnly"] or manifest is None:
            raise ValueError("Graph changes require a writable workspace with an accepted graph manifest.")
        dependency_ids, _ = architecture_documents(manifest, graph, context, adopt_architecture)
        omitted = set(removed) | dependency_ids
        unchanged_specifications([item for item in context["acceptedDocuments"] if item["nodeId"] not in omitted], context["documents"])
        return context, graph, manifest

    def derive(self, project, workspace, graph, manifest, plan, previous=None):
        state = DesktopV3State(self.service).current(project, workspace)["state"]
        record = build(combined(manifest), graph, plan, state, previous=previous)
        context = self.specifications.context(project, workspace)
        _, record["architectureDocuments"] = architecture_documents(manifest, graph, context, record["plan"]["adoptArchitectureContext"])
        if previous and previous["architectureDocuments"] != record["architectureDocuments"]:
            raise ValueError("Architecture dependency documents changed; create a new proposal.")
        validate_sources(self.service, project, workspace, record)
        record["stateEffects"] = prepare_state(self.service, project, workspace, record["acceptedGraph"], graph,
            record["resultGraph"], record["acceptedResultGraph"], record["plan"]["removeNodes"], record["plan"]["removeEdges"], rewired(record),
            adopt_architecture=record["plan"]["adoptArchitectureContext"])
        if previous and record["stateEffects"]["affectedDigest"] != previous["stateEffects"]["affectedDigest"]:
            raise ValueError("Affected state inputs changed; create a new graph proposal.")
        return record

    @staticmethod
    def change_record(project, workspace, context, manifest, derived, author, label, supersedes=None):
        return {"schemaVersion": 2, "kind": "graph-changes", "project": project, "workspace": workspace,
                "parentRevision": context["acceptedHead"], "parentGraphManifestId": manifest["id"],
                "graphDigest": context["graphDigest"], "requiresBaseAdoption": False, "adoptionDocuments": [],
                "subject": label, "by": author, "createdAt": stamp(), "supersedes": supersedes, **derived}

    def create(self, payload, by):
        from backend.canvas.opora_graph_change_plan import normalize
        if set(payload) - {"operationId"} != {"project", "workspace", "parentRevision", "expectedGraphDigest", "subject", "plan"}:
            raise ValueError("Invalid graph change proposal fields.")
        project, workspace = scope(payload)
        author, label, plan = _author(by, allow_agent=True), subject(payload), normalize(payload["plan"])
        from backend.canvas.operation_receipts import Receipt
        receipt = Receipt(payload, "graph-proposal", author) if "operationId" in payload else None
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                if receipt:
                    replay = receipt.replay(repo.db)
                    if replay is not None:
                        return replay
                context, graph, manifest = self.current_change(project, workspace, plan["removeNodes"], plan["adoptArchitectureContext"])
                self.expect(context, payload["parentRevision"], payload["expectedGraphDigest"])
                derived = self.derive(project, workspace, graph, manifest, plan)
                record = self.change_record(project, workspace, context, manifest, derived, author, label)
                result = {**repo.insert(record), "accepted": False}
                if receipt:
                    receipt.begin(repo.db)
                    receipt.complete(repo.db, result)
                return result

    def rebase(self, record_id, payload, by):
        if set(payload) != {"project", "workspace", "expectedAcceptedHead", "expectedGraphDigest"}:
            raise ValueError("Invalid graph rebase fields.")
        project, workspace = scope(payload)
        author = _author(by, allow_agent=True)
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                old = repo.read(record_id)
                if old["kind"] != "graph-changes" or repo.accepted(record_id):
                    raise ValueError("Rebase requires an unaccepted graph change proposal.")
                context, graph, manifest = self.current_change(project, workspace, old["plan"]["removeNodes"], old["plan"]["adoptArchitectureContext"])
                self.expect(context, payload["expectedAcceptedHead"], payload["expectedGraphDigest"])
                derived = self.derive(project, workspace, graph, manifest, old["plan"], previous=old)
                if (old["parentRevision"] == context["acceptedHead"] and old["graphDigest"] == context["graphDigest"]
                        and old["stateEffects"] == derived["stateEffects"]):
                    raise ValueError("Rebase requires changed context.")
                record = self.change_record(project, workspace, context, manifest, derived, author, old["subject"], record_id)
                return {**repo.insert(record), "accepted": False}
