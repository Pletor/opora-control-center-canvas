"""Apply a three-way merge verdict for one stale proposal of each native kind.

Each function runs inside the caller's lock and transaction and returns
`(outcome, result_id_or_None, conflict_items, reason)`. A clean merge inserts a new
immutable proposal (new ID, `supersedes` the old one, author `system`); the old record
is never changed. Precondition failures that are not same-field conflicts raise ValueError."""
from copy import deepcopy

from backend.canvas import opora_auto_rebase_merge as merge
from backend.canvas.opora_change_validation import check_changes
from backend.canvas.opora_changesets import OporaChangesets, stamp
from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.opora_graph_build import place, validate_application
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_graph_records import combined
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords
from database.repositories.opora_graph_changes import GraphChanges

# Records validate authors against the shared AUTHORS tuple; `orchestrator` never accepts plans.
SYSTEM = {"kind": "orchestrator", "name": "system"}


def spec(canvas, project, workspace, proposal_id):
    repo = ChangesetRepository(canvas.db_for(project), project, workspace)
    old = repo.read(proposal_id, proposal=True)
    context = OporaChangesets(canvas).context(project, workspace)
    if context["readOnly"]:
        raise ValueError("read_only_workspace")
    outcome, conflicts, merged = merge.spec(old, context["acceptedDocuments"])
    if outcome != "clean":
        return outcome, None, conflicts, "three_way_" + outcome
    live = {item["nodeId"]: item for item in context["documents"]}
    missing = [item["nodeId"] for item in merged if item["nodeId"] not in live]
    if missing:
        raise ValueError("card_missing_in_working_canvas")
    changes = check_changes({"project": project, "workspace": workspace, "changes": [
        {"nodeId": item["nodeId"], "expectedRevision": live[item["nodeId"]]["revision"], "fields": item["fields"]}
        for item in merged]}, context["acceptedDocuments"], context["documents"])
    record = repo.insert({"project": project, "workspace": workspace, "parentRevision": context["acceptedHead"],
                          "graphDigest": context["graphDigest"], "subject": old["subject"], "by": SYSTEM,
                          "createdAt": stamp(), "changes": changes, "supersedes": proposal_id}, proposal=True)
    return "rebased", record["id"], [], "three_way_clean"


def content(canvas, project, workspace, proposal_id):
    service = OporaContentChanges(canvas)
    repo = ContentRecords(canvas.db_for(project), project, workspace)
    old, current = repo.read(proposal_id), service.current(project, workspace)
    outcome, conflicts, kept = merge.content(old, current["acceptedEntries"])
    if outcome != "clean":
        return outcome, None, conflicts, "three_way_" + outcome
    record = service.derive(project, workspace, current, kept, SYSTEM, old["subject"], proposal_id)
    return "rebased", repo.insert(record)["id"], [], "three_way_clean"


def graph(canvas, project, workspace, proposal_id):
    edits = OporaGraphChanges(canvas)
    repo = GraphChanges(canvas.db_for(project), project, workspace)
    old = repo.read(proposal_id)
    context, working, manifest = edits.observed(project, workspace)
    if context["readOnly"]:
        raise ValueError("read_only_workspace")
    accepted = combined(manifest) if manifest else {"nodes": [], "edges": []}
    outcome, conflicts = merge.graph(old, accepted)
    if outcome != "clean":
        return outcome, None, conflicts, "three_way_" + outcome
    if old["kind"] == "graph-changes":
        plan = old["plan"]
        context, working, manifest = edits.current_change(project, workspace, plan["removeNodes"],
                                                          plan["adoptArchitectureContext"])
        derived = edits.derive(project, workspace, working, manifest, plan)
        record = edits.change_record(project, workspace, context, manifest, derived, SYSTEM, old["subject"], proposal_id)
    else:
        additions_service = OporaGraphProposals(canvas)
        context, working, manifest, missing = additions_service.current(project, workspace)
        if not any(old["additions"].values()) and (manifest is not None or not working["nodes"]):
            raise ValueError("adoption_only_proposal_obsolete")
        additions = {key: deepcopy(old[key]) for key in ("additions", "refs", "inside", "positions", "anchors",
                                                          "specifications")}
        validate_application(canvas, project, workspace, working, additions, combined(manifest) if manifest else None)
        place(additions["additions"], working, additions["inside"], additions["positions"])
        record = additions_service.record(project, workspace, context, working, manifest, missing, additions, SYSTEM,
                                          old["subject"], proposal_id)
    return "rebased", repo.insert(record)["id"], [], "three_way_clean"


APPLY = {"spec": spec, "content": content, "graph": graph}
