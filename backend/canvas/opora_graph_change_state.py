"""Reviewed removal effects and transactional current-state cleanup; histories remain intact."""
from copy import deepcopy

from backend.canvas.architecture_graph import split
from backend.canvas.graph import digest, encode, valid_id
from backend.canvas.opora_graph_change_safety import preflight
from backend.editor.agent_memory.decision_versions import preserve_versions
from backend.editor.agent_memory.desktop_v3_state import (
    DesktopV3State,
    branch_targets,
    check_node_branches,
    now,
    validate_state,
)

KEYS = {"revision", "before", "after", "beforeDigest", "affectedDigest", "effects",
        "removedNodeIds", "removedEdgeIds", "rewiredEdgeIds", "checkedNodeIds"}


def _ids(values):
    if not isinstance(values, list) or not all(map(valid_id, values)) or len(values) != len(set(values)):
        raise ValueError("State cleanup requires unique explicit identifiers.")
    return set(values)


def _cleanup(before, nodes, edges, rewired):
    after = deepcopy(before)
    effects = {"removedNodes": {key: deepcopy(before["nodes"][key]) for key in sorted(nodes) if key in before["nodes"]},
               "removedEdges": {key: deepcopy(before.get("edges", {})[key]) for key in sorted(edges) if key in before.get("edges", {})},
               "clearedEdgeReports": {key: deepcopy(before.get("edges", {})[key]) for key in sorted(rewired) if key in before.get("edges", {})},
               "removedRules": [], "removedDecisions": [], "removedAutonomy": {}, "unassignedTickets": []}
    for key in nodes:
        after["nodes"].pop(key, None)
    for key in edges | rewired:
        after.get("edges", {}).pop(key, None)
    for collection, predicate in (("rules", lambda item: item["scope"] == "node" and item["target"] in nodes),
                                  ("decisions", lambda item: item["nodeId"] in nodes)):
        effects["removed" + collection.title()] = [deepcopy(item) for item in before[collection] if predicate(item)]
        after[collection] = [item for item in after[collection] if not predicate(item)]
    for key in nodes:
        if key in after.get("autonomy", {}):
            effects["removedAutonomy"][key] = after["autonomy"].pop(key)
    for ticket in after["tickets"]:
        if ticket["nodeId"] in nodes:
            effects["unassignedTickets"].append({"id": ticket["id"], "before": ticket["nodeId"], "after": ""})
            ticket["nodeId"] = ""
    return after, effects


def _affected(before, nodes, edges, rewired, checked):
    _, effects = _cleanup(before, nodes, edges, rewired)
    return digest({"cleanup": effects,
                   "checked": {key: before["nodes"].get(key) for key in sorted(checked)},
                   "references": [list(item) for item in branch_targets(before) if item[3] in nodes]})


def prepare_state(canvas, project, workspace, acceptedGraph, workingGraph, resultGraph, acceptedResultGraph,
                  removedNodeIds, removedEdgeIds, rewiredEdgeIds, *, adopt_architecture=False):
    nodes, edges, rewired = (_ids(list(values)) for values in (removedNodeIds, removedEdgeIds, rewiredEdgeIds))
    if edges & rewired:
        raise ValueError("An edge cannot be removed and rewired in the same review.")
    stored = DesktopV3State(canvas).current(project, workspace)
    before = deepcopy(stored["state"])
    checked, memberships = preflight(acceptedGraph, workingGraph, resultGraph, acceptedResultGraph,
                                     before, nodes, edges, adopt_architecture=adopt_architecture)
    changed_edges = set()
    for old, new in ((acceptedGraph, acceptedResultGraph), (workingGraph, resultGraph)):
        old_edges = {item["id"]: item for item in old["edges"]}
        boundary = ({item["id"] for item in split(old)[0]["edges"] + split(new)[0]["edges"]}
                    if adopt_architecture and old is acceptedGraph else set())
        changed_edges.update(item["id"] for item in new["edges"] if item["id"] in old_edges
                             and item["id"] not in boundary and digest(item) != digest(old_edges[item["id"]]))
    if rewired != changed_edges:
        raise ValueError("Rewired edge reports require an exact reviewed cleanup set.")
    after, effects = _cleanup(before, nodes, edges, rewired)
    effects["areaMembershipChanges"] = memberships
    validate_state(after)
    check_node_branches(after, {item["id"] for item in resultGraph["nodes"]})
    preserve_versions(before["decisions"], after["decisions"])
    return {"revision": stored["revision"], "before": before, "after": after,
            "beforeDigest": digest(before), "affectedDigest": _affected(before, nodes, edges, rewired, checked),
            "effects": effects, "removedNodeIds": sorted(nodes), "removedEdgeIds": sorted(edges),
            "rewiredEdgeIds": sorted(rewired), "checkedNodeIds": checked}


def validate_review(review):
    if not isinstance(review, dict) or set(review) != KEYS or type(review["revision"]) is not int or review["revision"] < 0:
        raise ValueError("Invalid state cleanup review.")
    nodes, edges, rewired, checked = (_ids(review[key]) for key in
                                    ("removedNodeIds", "removedEdgeIds", "rewiredEdgeIds", "checkedNodeIds"))
    if edges & rewired:
        raise ValueError("Conflicting edge cleanup review.")
    validate_state(review["before"])
    validate_state(review["after"])
    after, effects = _cleanup(review["before"], nodes, edges, rewired)
    if not isinstance(review["effects"], dict) or set(review["effects"]) != {*effects, "areaMembershipChanges"}:
        raise ValueError("Invalid reviewed state effects.")
    memberships = review["effects"]["areaMembershipChanges"]
    if not isinstance(memberships, list):
        raise ValueError("Invalid reviewed area membership effects.")  # noqa: TRY004 -- domain conflict, HTTP 409.
    for item in memberships:
        if (not isinstance(item, dict) or set(item) != {"graph", "nodeId", "before", "after"}
                or item["graph"] not in ("accepted", "working") or not valid_id(item["nodeId"])
                or any(item[key] is not None and not valid_id(item[key]) for key in ("before", "after"))):
            raise ValueError("Invalid reviewed area membership effect.")
    if (digest(after) != digest(review["after"]) or review["beforeDigest"] != digest(review["before"])
            or review["affectedDigest"] != _affected(review["before"], nodes, edges, rewired, checked)
            or digest(effects) != digest({key: value for key, value in review["effects"].items() if key != "areaMembershipChanges"})):
        raise ValueError("State cleanup review integrity mismatch.")
    return review


def persist_state(canvas, db, project, workspace, review, resultGraph, *, actor):
    if actor != "human":
        raise ValueError("Reviewed graph state cleanup requires a human.")
    if not db.in_transaction:
        raise RuntimeError("State cleanup requires the caller's transaction.")
    validate_review(review)
    current = DesktopV3State(canvas).current(project, workspace)
    if current["revision"] != review["revision"] or digest(current["state"]) != review["beforeDigest"]:
        raise ValueError("Reviewed state changed; rebase the graph proposal.")
    after = review["after"]
    check_node_branches(after, {item["id"] for item in resultGraph["nodes"]})
    preserve_versions(current["state"]["decisions"], after["decisions"])
    if digest(after) == review["beforeDigest"]:
        return current["revision"]
    revision = current["revision"] + 1
    db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
               (project, workspace, revision, encode(after), now()))
    return revision
