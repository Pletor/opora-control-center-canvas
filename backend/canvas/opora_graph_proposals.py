"""Immutable graph additions; creation and explicit rebase never mutate Canvas."""
from copy import deepcopy

from backend.canvas.opora_change_validation import scope, subject
from backend.canvas.opora_changesets import OporaChangesets, stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_build import (
    graph_digest,
    place,
    prepare,
    unchanged_specifications,
    validate_application,
)
from backend.canvas.opora_graph_records import accepted_record, combined
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.opora_graph_changes import GraphChanges as GraphProposals


class OporaGraphProposals:
    def __init__(self, service):
        self.service = service
        self.specifications = OporaChangesets(service)

    def repository(self, project, workspace):
        return GraphProposals(self.service.db_for(project), project, workspace)

    def current(self, project, workspace):
        context = self.specifications.context(project, workspace)
        if context["readOnly"]:
            raise ValueError("Graph additions require a writable workspace.")
        revision = accepted_record(self.specifications.repository(project, workspace), context["acceptedHead"]) if context["acceptedHead"] else {}
        manifest_id = revision.get("graphManifestId")
        manifest = self.repository(project, workspace).read(manifest_id, manifest=True) if manifest_id else None
        graph = self.service.view(project, workspace)["graph"]
        missing = unchanged_specifications(context["acceptedDocuments"], context["documents"])
        return context, graph, manifest, missing

    def context(self, project, workspace):
        from backend.canvas.opora_graph_changes import OporaGraphChanges
        return OporaGraphChanges(self.service).context(project, workspace)

    def read(self, project, workspace, record_id):
        scope({"project": project, "workspace": workspace})
        with self.service.lock_for(project):
            repo = self.repository(project, workspace)
            return {**repo.read(record_id), "accepted": repo.accepted(record_id) is not None}

    def list(self, project, workspace):
        scope({"project": project, "workspace": workspace})
        with self.service.lock_for(project):
            return {"items": list(self.repository(project, workspace).summaries()),
                    "acceptedHead": self.specifications.repository(project, workspace).head()}

    def create(self, payload, by):
        from backend.canvas.opora_graph_change_plan import EDIT_KEYS
        from backend.canvas.opora_graph_changes import OporaGraphChanges
        plan = payload.get("plan")
        if isinstance(plan, dict) and (set(plan) & EDIT_KEYS or "adoptArchitectureContext" in plan):
            return OporaGraphChanges(self.service).create(payload, by)
        if set(payload) != {"project", "workspace", "parentRevision", "expectedGraphDigest", "subject", "plan"}:
            raise ValueError("Invalid graph proposal fields.")
        project, workspace = scope(payload)
        author, label = _author(by, allow_agent=True), subject(payload)
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                context, graph, manifest, missing = self.current(project, workspace)
                self.expect(context, payload["parentRevision"], payload["expectedGraphDigest"])
                plan = payload["plan"]
                from backend.canvas.opora_graph_build import validate_plan
                validate_plan(plan)
                if not any(plan.values()) and manifest is None and graph["nodes"]:
                    additions = {"additions": {"nodes": [], "edges": []}, "refs": {}, "inside": {}, "positions": {},
                                 "anchors": {}, "specifications": []}
                else:
                    additions = prepare(plan, graph, DesktopV3State(self.service).read(project, workspace)["state"])
                record = self.record(project, workspace, context, graph, manifest, missing, additions, author, label)
                validate_application(self.service, project, workspace, graph, record, combined(manifest) if manifest else None)
                return {**repo.insert(record), "accepted": False}

    @staticmethod
    def expect(context, parent, graph_digest):
        if context["acceptedHead"] != parent or context["graphDigest"] != graph_digest:
            raise ValueError("Accepted revision or graph changed; refresh context.")

    @staticmethod
    def record(project, workspace, context, graph, manifest, missing, additions, by, label, supersedes=None):
        return {"schemaVersion": 1, "kind": "graph-additions", "project": project, "workspace": workspace,
                "parentRevision": context["acceptedHead"], "graphDigest": context["graphDigest"],
                "parentGraphManifestId": manifest["id"] if manifest else None, "baseGraph": deepcopy(graph),
                "requiresBaseAdoption": manifest is None, "adoptionDocuments": missing if manifest is None else [],
                "subject": label, "by": by, "createdAt": stamp(), "supersedes": supersedes, **additions}

    def rebase(self, record_id, payload, by):
        from backend.canvas.opora_graph_changes import OporaGraphChanges
        project, workspace = scope(payload)
        with self.service.lock_for(project):
            kind = self.repository(project, workspace).read(record_id)["kind"]
        if kind == "graph-changes":
            return OporaGraphChanges(self.service).rebase(record_id, payload, by)
        if set(payload) != {"project", "workspace", "expectedAcceptedHead", "expectedGraphDigest"}:
            raise ValueError("Invalid graph rebase fields.")
        project, workspace = scope(payload)
        author = _author(by, allow_agent=True)
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                old = repo.read(record_id)
                context, graph, manifest, missing = self.current(project, workspace)
                self.expect(context, payload["expectedAcceptedHead"], payload["expectedGraphDigest"])
                if repo.accepted(record_id) or (old["parentRevision"] == context["acceptedHead"]
                                               and old["graphDigest"] == graph_digest(graph)
                                               and old["adoptionDocuments"] == (missing if manifest is None else [])):
                    raise ValueError("Rebase requires an unaccepted proposal with changed context.")
                if not any(old["additions"].values()) and (manifest is not None or not graph["nodes"]):
                    raise ValueError("An adoption-only proposal requires a nonempty graph without an accepted manifest.")
                additions = {key: deepcopy(old[key]) for key in ("additions", "refs", "inside", "positions", "anchors", "specifications")}
                validate_application(self.service, project, workspace, graph, additions, combined(manifest) if manifest else None)
                place(additions["additions"], graph, additions["inside"], additions["positions"])
                record = self.record(project, workspace, context, graph, manifest, missing, additions, author, old["subject"], record_id)
                return {**repo.insert(record), "accepted": False}
