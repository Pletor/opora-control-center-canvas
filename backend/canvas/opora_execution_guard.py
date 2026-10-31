"""Permanent enrollment prevents late legacy state/results from bypassing fencing."""
from backend.canvas.authority import acts_as_human
from backend.canvas.graph import digest


def enrolled(db, project, workspace):
    return {row[0] for row in db.execute("SELECT node_id FROM opora_execution_epochs"
                                       " WHERE project_id=? AND workspace_id=?", (project, workspace))}


def legacy_lease(db, project, workspace, node):
    if node in enrolled(db, project, workspace):
        raise ValueError("Enrolled cards require the OporaHub execution protocol.")


# A card without stored state gets this skeleton when it is closed (same as the UI close).
SKELETON = {"phase": "discover", "criteria": [], "steps": []}


def closes_only(before, after):
    """The server close of one card: unchanged, or the same card (a missing one as `SKELETON`) newly confirmed."""
    if digest(before) == digest(after):
        return True
    def rest(node):
        return {key: value for key, value in (node or {}).items() if key != "done"}
    return (after is not None and (after.get("done") or {}).get("confirmed") is True
            and digest(rest(before) if before is not None else SKELETON) == digest(rest(after)))


def state_write(db, project, workspace, before, after, graph, actor):
    if actor == "human":
        return
    cards = enrolled(db, project, workspace)
    if not cards:
        return
    changed = any(digest(before["nodes"].get(node)) != digest(after["nodes"].get(node)) for node in cards)
    edges = {edge["id"] for edge in graph["edges"] if cards.intersection((edge["source"], edge["target"]))}
    changed |= any(digest(before.get("edges", {}).get(edge)) != digest(after.get("edges", {}).get(edge)) for edge in edges)
    def decisions(state):
        return [item for item in state["decisions"] if item.get("nodeId") in cards]
    if actor == "opora":  # the server's deterministic close (opora_card_auto_close) may change `done` and nothing else
        if (any(not closes_only(before["nodes"].get(node), after["nodes"].get(node)) for node in cards)
                or any(digest(before.get("edges", {}).get(edge)) != digest(after.get("edges", {}).get(edge)) for edge in edges)
                or digest(decisions(before)) != digest(decisions(after))):
            raise ValueError("The server close changes only the done mark of an enrolled card.")
        return
    if (changed or digest(decisions(before)) != digest(decisions(after))) and not acts_as_human(actor):
        raise ValueError("Enrolled cards accept execution receipts, not legacy state changes.")
