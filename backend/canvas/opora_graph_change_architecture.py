"""Explicit adoption of separately managed architecture as a reviewed dependency."""
from copy import deepcopy

from backend.canvas.architecture_graph import split


def adoption(accepted, working, enabled):
    previous, content = split(accepted)
    current = split(working)[0]
    if not enabled:
        return deepcopy(accepted), None
    if previous == current:
        raise ValueError("Architecture context adoption has no effective change.")
    graph = {key: [*deepcopy(current[key]), *deepcopy(content[key])] for key in ("nodes", "edges")}
    review = {"acceptedBefore": deepcopy(previous), "workingBefore": deepcopy(current),
              "proposedAccepted": deepcopy(current), "proposedWorking": deepcopy(current)}
    return graph, review


def context(accepted, working):
    previous, current = split(accepted)[0] if accepted is not None else None, split(working)[0]
    return {"accepted": previous, "working": current, "differs": previous is not None and previous != current}


def documents(manifest, working, context, enabled):
    old_ids = {node["id"] for node in manifest["architectureContext"]["nodes"]} if enabled else set()
    current_ids = {node["id"] for node in split(working)[0]["nodes"]} if enabled else set()
    adopted = [deepcopy(item) for item in context["documents"] if item["nodeId"] in current_ids]
    if {item["nodeId"] for item in adopted} != current_ids:
        raise ValueError("Current architecture dependency documents are incomplete.")
    return old_ids | current_ids, adopted
