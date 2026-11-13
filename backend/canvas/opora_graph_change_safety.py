"""Pure, explicit graph removal closure and completed-card protection."""
from backend.canvas.architecture_graph import split
from backend.canvas.areas import area_of
from backend.canvas.graph import digest, validate_graph
from backend.editor.agent_memory.desktop_v3_state import branch_targets
from backend.editor.agent_packet.desktop_v3_packets import ancestor_ids
from backend.editor.agent_packet.specification_context import _node
from backend.editor.node.removals import descendants


def removal_closure(before, after, removed_nodes, removed_edges):
    existing = {node["id"] for node in before["nodes"]}
    required_nodes = descendants(before["nodes"], removed_nodes & existing)
    surviving = {node["id"]: node for node in after["nodes"]}
    def still_dependent(key):
        if key not in surviving:
            return True
        seen = set()
        cursor = surviving[key]["parentId"]
        while cursor is not None and cursor not in seen:
            if cursor in removed_nodes:
                return True
            seen.add(cursor)
            cursor = surviving.get(cursor, {}).get("parentId")
        return False
    missing_nodes = {key for key in required_nodes - removed_nodes if still_dependent(key)}
    remaining_edges = {edge["id"]: edge for edge in after["edges"]}
    missing_edges = {edge["id"] for edge in before["edges"]
                     if removed_nodes.intersection((edge["source"], edge["target"]))
                     and (edge["id"] not in remaining_edges or removed_nodes.intersection(
                         (remaining_edges[edge["id"]]["source"], remaining_edges[edge["id"]]["target"])))} - removed_edges
    if missing_nodes or missing_edges:
        raise ValueError("Explicit removal closure is incomplete: nodes=" + ",".join(sorted(missing_nodes))
                         + "; edges=" + ",".join(sorted(missing_edges)))


def _changed_cards(before, after):
    old = {node["id"]: _node(node, before["nodes"]) for node in before["nodes"]}
    new = {node["id"]: _node(node, after["nodes"]) for node in after["nodes"]}
    changed = {key for key, value in old.items() if digest(value) != digest(new.get(key))}
    changed.update(new.keys() - old.keys())
    edges_before = {edge["id"]: edge for edge in before["edges"]}
    edges_after = {edge["id"]: edge for edge in after["edges"]}
    for key in edges_before.keys() | edges_after.keys():
        previous, current = edges_before.get(key), edges_after.get(key)
        if digest(previous) != digest(current):
            for edge in (previous, current):
                if edge:
                    changed.update((edge["source"], edge["target"]))
    # A reviewed child edit cannot escape a closed old parent or enter a closed new
    # parent; additions must recheck their full chain even when IDs were prebuilt.
    touched = set(changed)
    for graph in (before, after):
        by_id = {item["id"]: item for item in graph["nodes"]}
        for key in touched & by_id.keys():
            changed.update(ancestor_ids(by_id, key))
    return changed


def _memberships(before, after, label):
    old = {node["id"]: node for node in before["nodes"]}
    changes = []
    for node in after["nodes"]:
        if node["id"] not in old:
            continue
        previous = area_of(old[node["id"]], before["nodes"])
        current = area_of(node, after["nodes"])
        old_id, new_id = previous["id"] if previous else None, current["id"] if current else None
        if old_id != new_id:
            changes.append({"graph": label, "nodeId": node["id"], "before": old_id, "after": new_id})
    return changes


def preflight(accepted, working, result, accepted_result, state, removed_nodes, removed_edges,
              *, adopt_architecture=False, project=None):
    """No cascades, implicit retargeting, architecture changes or completed-card edits.

    `project` jen na živé cestě (návrh, přebudování): tam rozhoduje pojistka `confirmed_reopen`. Přehrání uloženého
    záznamu (`validate_record`) ji nevolá, ať záznam vzniklý ve warn nepřestane být čitelný po návratu na enforce."""
    if type(adopt_architecture) is not bool:
        raise ValueError("Architecture context adoption must be explicit.")
    if adopt_architecture and digest(split(accepted_result)[0]) != digest(split(working)[0]):
        raise ValueError("Accepted architecture context must match the current working boundary exactly.")
    checked, memberships = set(removed_nodes), []
    for before, after, label in ((accepted, accepted_result, "accepted"), (working, result, "working")):
        removal_closure(before, after, removed_nodes, removed_edges)
        for collection, explicit in (("nodes", removed_nodes), ("edges", removed_edges)):
            missing = {item["id"] for item in before[collection]} - {item["id"] for item in after[collection]}
            if label == "accepted" and adopt_architecture:
                missing -= {item["id"] for item in split(before)[0][collection]}
            if missing - explicit:
                raise ValueError("Result contains an unreviewed removal: " + ",".join(sorted(missing - explicit)))
        if (digest(split(before)[0]) != digest(split(after)[0])
                and not (label == "accepted" and adopt_architecture
                         and digest(split(after)[0]) == digest(split(working)[0]))):
            raise ValueError("Graph changes cannot edit shared architecture.")
        validate_graph(after)
        if removed_nodes.intersection(node["id"] for node in after["nodes"]):
            raise ValueError("Explicitly removed nodes survive in the resulting graph.")
        if removed_edges.intersection(edge["id"] for edge in after["edges"]):
            raise ValueError("Explicitly removed edges survive in the resulting graph.")
        checked.update(_changed_cards(before, after))
        memberships.extend(_memberships(before, after, label))
    for node, block, via, target in branch_targets(state):
        if node not in removed_nodes and target in removed_nodes:
            raise ValueError(f"Surviving block reference must be resolved first: {node}/{block}/{via} -> {target}.")
    from backend.app import guards  # líně: balíček backend.app načítá factory (cyklus importů)

    closed = [key for key in sorted(checked)
              if state["nodes"].get(key, {}).get("done", {}).get("confirmed")]
    # OP-F43588.reopen: rozhodne režim pojistky jen na živé cestě; přehrání záznamu má týž vstup, už prověřený
    if project is not None and guards.check("confirmed_reopen", project, blocked=bool(closed), subject=",".join(closed)[:200],
                                            message="Změna grafu sahá na potvrzené karty: " + ",".join(closed)):
        raise ValueError("A human must reopen confirmed cards before these graph changes: " + ",".join(closed))
    return sorted(checked), memberships
