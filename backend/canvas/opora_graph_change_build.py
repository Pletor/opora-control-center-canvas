"""Two independent graph applications with stable additions and explicit review."""
from copy import deepcopy

from backend.canvas.architecture_graph import split
from backend.canvas.graph import validate_graph
from backend.canvas.opora_graph_build import merge, place, prepare
from backend.canvas.opora_graph_change_architecture import adoption
from backend.canvas.opora_graph_change_diff import changes, preconditions
from backend.canvas.opora_graph_change_plan import apply, normalize, validate_targets


def build(accepted, working, raw_plan, state, *, previous=None):
    plan = normalize(raw_plan)
    dependency, architecture = adoption(accepted, working, plan["adoptArchitectureContext"])
    validate_targets(dependency, working, plan)
    approved, result = apply(dependency, plan), apply(working, plan)
    for before, after in ((dependency, approved), (working, result)):
        if split(before)[0] != split(after)[0]:
            raise ValueError("Graph changes cannot mutate shared architecture.")
        validate_graph(after)
    additive = {key: plan[key] for key in ("nodes", "edges")}
    if previous:
        additions = {key: deepcopy(previous[key]) for key in ("additions", "refs", "inside", "positions", "specifications")}
        place(additions["additions"], result, additions["inside"], additions["positions"])
    elif any(additive.values()):
        additions = prepare(additive, result, state)
        additions.pop("anchors")
    else:
        additions = {"additions": {"nodes": [], "edges": []}, "refs": {}, "inside": {}, "positions": {}, "specifications": []}
    approved, result = merge(approved, additions["additions"]), merge(result, additions["additions"])
    review = changes(accepted, working, approved, result, plan, additions["additions"])
    conditions = {"accepted": preconditions(accepted, plan, additions["additions"], additions["inside"]),
                  "working": preconditions(working, plan, additions["additions"], additions["inside"]),
                  "areaMembership": review["areaMembership"]}
    if architecture is not None:
        conditions["architecture"] = {key: architecture[key] for key in ("acceptedBefore", "workingBefore")}
    if previous and conditions != previous["preconditions"]:
        raise ValueError("Affected graph fields, references or deletion closure changed; create a new proposal.")
    if accepted == approved and working == result:
        raise ValueError("Graph change proposal has no effective changes.")
    for before, after in ((dependency, approved), (working, result)):
        if split(before)[0] != split(after)[0]:
            raise ValueError("Graph changes cannot mutate shared architecture.")
    review["architectureContext"] = architecture
    if any(item["operation"] == "update" and item["acceptedBefore"] == item["proposedAccepted"]
           and item["workingBefore"] == item["proposedWorking"] for key in ("nodes", "edges") for item in review[key]):
        raise ValueError("Every graph update operation must change an explicit field.")
    return {**additions, "plan": plan, "acceptedGraph": deepcopy(accepted), "baseGraph": deepcopy(working),
            "resultGraph": result, "acceptedResultGraph": approved, "preconditions": conditions,
            "changes": review}


def validate_sources(service, project, workspace, record):
    service._verify_source_refs(project, workspace, record["baseGraph"], record["resultGraph"])
    service._verify_source_refs(project, workspace, record["acceptedGraph"], record["acceptedResultGraph"])
