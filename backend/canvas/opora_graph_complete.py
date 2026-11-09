"""Complete immutable V3 proposals use the native reviewed graph transaction."""
from copy import deepcopy
from uuid import uuid4

from backend.canvas.graph import digest
from backend.canvas.opora_graph_change_state import _cleanup, prepare_state, validate_review
from backend.canvas.opora_graph_complete_build import compile_plan, normalize_complete
from backend.canvas.opora_graph_complete_content import apply_inputs, observe
from backend.canvas.opora_graph_records import combined
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def derive(canvas, project, workspace, graph, manifest, plan, previous=None, *, identity_seed=None, identity_allocation=None):
    if "researchSource" in plan:
        from backend.canvas.research_plan_source import validate_source
        validate_source(canvas, project, workspace, plan["researchSource"])
    stored = DesktopV3State(canvas).current(project, workspace)
    from backend.canvas.opora_graph_complete_base import observe as observe_base
    base = observe_base(canvas, project, workspace, graph)
    if previous and previous.get("contentBase") != base:
        raise ValueError("Reviewed base content revision changed or is missing; create an explicitly reviewed proposal.")
    if previous and (stored["revision"] != previous["stateEffects"]["revision"]
                     or digest(stored["state"]) != previous["stateEffects"]["beforeDigest"]):
        raise ValueError("Complete proposal state changed; create an explicitly revised proposal.")
    seed = previous["identitySeed"] if previous else identity_seed or str(uuid4())
    allocation = deepcopy(previous.get("identityAllocation") if previous else identity_allocation)
    built, record = compile_plan(plan, combined(manifest), graph, stored["state"], seed,
                                 identities=allocation["ids"] if allocation is not None else None)
    if previous and record["preconditions"] != previous["preconditions"]:
        raise ValueError("Affected graph fields or extension targets changed; create a new proposal.")
    canvas._verify_source_refs(project, workspace, graph, record["resultGraph"])
    canvas._verify_source_refs(project, workspace, combined(manifest), record["acceptedResultGraph"])
    rewired = [item["id"] for item in plan["updateEdges"]]
    review = prepare_state(canvas, project, workspace, combined(manifest), graph,
        record["resultGraph"], record["acceptedResultGraph"], plan["removeNodes"], plan["removeEdges"], rewired,
        adopt_architecture=plan["adoptArchitectureContext"])
    inputs = observe(canvas, project, workspace, built, stored["revision"],
                     track_research=previous is None or "researchEvidenceByNode" in previous["contentInputs"])
    if previous and inputs != previous["contentInputs"]:
        raise ValueError("Complete proposal document or fragment inputs changed; create an explicitly revised proposal.")
    built.state, _ = _cleanup(built.state, set(plan["removeNodes"]), set(plan["removeEdges"]), set(rewired))
    effects = apply_inputs(project, workspace, built, inputs)
    if graph == record["resultGraph"] and combined(manifest) == record["acceptedResultGraph"] and effects["after"] == stored["state"] and not effects["documents"]:
        raise ValueError("Complete proposal has no effective changes.")
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.opora_graph_change_architecture import documents
    _, architecture = documents(manifest, graph, OporaChangesets(canvas).context(project, workspace), plan["adoptArchitectureContext"])
    return {**record, **({"researchSource": deepcopy(plan["researchSource"])} if "researchSource" in plan else {}),
            "identitySeed": seed, **({"identityAllocation": allocation} if allocation is not None else {}),
            "stateEffects": review, "contentInputs": inputs,
            "contentEffects": effects, "contentBase": base, "architectureDocuments": architecture,
            "specifications": [{"nodeId": item["nodeId"], "fields": item["value"]}
                               for item in effects["documents"] if item["kind"] == "spec"]}


def validate_record(record):
    """Rebuild the complete stored plan using pinned native inputs; never allocate new identities."""
    from backend.canvas.opora_change_validation import identifier, scope
    from backend.canvas.opora_graph_change_safety import preflight
    from backend.canvas.opora_graph_records import validate_documents
    project, workspace = scope(record)
    if "contentBase" in record:
        from backend.canvas.opora_graph_complete_base import validate
        validate(record["contentBase"], project, workspace)
    if record["schemaVersion"] != 3 or record["kind"] != "graph-changes":
        raise ValueError("Invalid complete graph record version.")
    identifier(record["parentRevision"])
    identifier(record["parentGraphManifestId"])
    identifier(record["supersedes"], nullable=True)
    if record["requiresBaseAdoption"] is not False or record["adoptionDocuments"] != []:
        raise ValueError("Complete proposals require accepted graph authority.")
    if digest(record["baseGraph"]) != record["graphDigest"]:
        raise ValueError("Complete graph base digest mismatch.")
    plan = normalize_complete(record["plan"])
    if record.get("researchSource") != plan.get("researchSource"):
        raise ValueError("Complete research provenance differs from the submitted plan.")
    review = validate_review(record["stateEffects"])
    allocation = deepcopy(record.get("identityAllocation"))
    if allocation is not None:
        from backend.canvas.opora_graph_revise import validate_allocation
        validate_allocation(allocation, plan)
    built, derived = compile_plan(plan, record["acceptedGraph"], record["baseGraph"], review["before"], record["identitySeed"],
                                  identities=allocation["ids"] if allocation is not None else None)
    if allocation != record.get("identityAllocation"):
        raise ValueError("Incomplete named identity allocation.")
    if any(record[key] != value for key, value in derived.items()):
        raise ValueError("Complete graph derived evidence mismatch.")
    if any(expected != review["revision"] for expected in built.extend_revisions):
        raise ValueError("Complete extension revision mismatch.")
    checked, memberships = preflight(record["acceptedGraph"], record["baseGraph"], record["resultGraph"],
        record["acceptedResultGraph"], review["before"], set(plan["removeNodes"]), set(plan["removeEdges"]),
        adopt_architecture=plan["adoptArchitectureContext"])
    if checked != review["checkedNodeIds"] or memberships != review["effects"]["areaMembershipChanges"]:
        raise ValueError("Complete state safety evidence mismatch.")
    if any(sorted(review[key]) != sorted(plan[operation]) for key, operation in
           (("removedNodeIds", "removeNodes"), ("removedEdgeIds", "removeEdges"))):
        raise ValueError("Complete cleanup does not match plan.")
    if sorted(review["rewiredEdgeIds"]) != sorted(item["id"] for item in plan["updateEdges"]):
        raise ValueError("Complete rewire cleanup does not match plan.")
    built.state, _ = _cleanup(built.state, set(plan["removeNodes"]), set(plan["removeEdges"]), set(review["rewiredEdgeIds"]))
    effects = apply_inputs(project, workspace, built, record["contentInputs"])
    if effects != record["contentEffects"]:
        raise ValueError("Complete content differs from original plan.")
    specs = [{"nodeId": item["nodeId"], "fields": item["value"]} for item in effects["documents"] if item["kind"] == "spec"]
    if specs != record["specifications"]:
        raise ValueError("Complete specification evidence mismatch.")
    validate_documents(record["architectureDocuments"], project, workspace)
