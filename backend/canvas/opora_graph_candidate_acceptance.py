"""Explicit human acceptance of a full graph candidate under native authority/CAS."""
from backend.canvas.architecture_graph import ids, split
from backend.canvas.authority import acts_as_human
from backend.canvas.graph import digest
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_candidate import candidate
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.opora_graph_records import accepted_record, preserved_content_manifest
from backend.canvas.opora_proposal_acceptance_guard import guard, seal
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def accept(canvas, proposal_id, payload, by):
    from backend.canvas.opora_change_validation import scope
    project, workspace = scope(payload)
    if set(payload) != {"project", "workspace", "expectedAcceptedHead", "expectedGraphDigest", "adoptBaseGraphDigest", "reviewedChangesId"}:
        raise ValueError("Full graph acceptance requires exact reviewed candidate and context.")
    author = _author(by)
    if not acts_as_human(author["kind"]) or payload["reviewedChangesId"] != proposal_id:
        raise ValueError("Explicit human review is required.")
    native = OporaGraphChanges(canvas)
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        repo, specs = native.repository(project, workspace), native.specifications.repository(project, workspace)
        with repo.db:
            repo.db.execute("BEGIN IMMEDIATE")
            proposal = repo.read(proposal_id)
            if proposal["schemaVersion"] != 4:
                raise ValueError("Full candidate acceptance requires native candidate record.")
            previous = repo.accepted(proposal_id)
            if previous:
                return accepted_record(specs, previous)
            context, graph, manifest = native.observed(project, workspace)
            native.expect(context, payload["expectedAcceptedHead"], payload["expectedGraphDigest"])
            expected_adoption = proposal["graphDigest"] if proposal["requiresBaseAdoption"] else None
            if payload["adoptBaseGraphDigest"] != expected_adoption:
                raise ValueError("Review the complete candidate including its initial graph authority.")
            if context["readOnly"] or proposal["parentRevision"] != context["acceptedHead"] or graph != proposal["baseGraph"] or proposal["parentGraphManifestId"] != (manifest["id"] if manifest else None):
                raise ValueError("Full candidate is stale; prepare a new explicitly reviewed candidate.")
            architecture = canvas.architecture.read(project)
            if architecture["revision"] != proposal["architectureRevision"]:
                raise ValueError("Shared architecture changed after review.")
            state = DesktopV3State(canvas).current(project, workspace)
            if state["revision"] != proposal["stateEffects"]["revision"] or digest(state["state"]) != proposal["stateEffects"]["beforeDigest"]:
                raise ValueError("Reviewed Desktop state changed.")
            result_graph = candidate(canvas, project, workspace, graph, proposal["resultGraph"], proposal["plan"]["undo"])
            if result_graph != proposal["resultGraph"]:
                raise ValueError("Native candidate normalization changed.")
            authorization = guard(repo.db, project, workspace, "graph-change", proposal_id)
            boundary, content = split(result_graph)
            if boundary != architecture["graph"]:
                canvas.architecture.write(repo.db, project, boundary, architecture["revision"], author["kind"], workspace, ids(content))
            OporaGraphAcceptance(canvas).write_graph(repo.db, project, workspace, content)
            manifest = repo.insert({"schemaVersion": 1, "kind": "graph-manifest", "project": project, "workspace": workspace,
                                    "graph": content, "architectureContext": boundary}, manifest=True)
            # Graph-only approval never adopts unrelated working specifications, text or execution state.
            retained = ids(result_graph)[0]
            documents = [d for d in context["acceptedDocuments"] if d["nodeId"] in retained]
            result = specs.insert({"project": project, "workspace": workspace, "kind": "graph-acceptance",
                "parentRevision": context["acceptedHead"], "proposalId": proposal_id, "subject": proposal["subject"],
                "by": author, "createdAt": stamp(), "graphManifestId": manifest["id"],
                **preserved_content_manifest(specs, context["acceptedHead"]), "documents": documents})
            specs.advance(context["acceptedHead"], result["id"])
            seal(repo.db, project, workspace, authorization, result)
            return result
