"""Deterministic card close (docs/oporahub-plan-steps.md, "Jediná definice hotovo").

Once every other requirement of the single definition of done is met (`steps`, `card_acceptance`,
`gate_ready`, `merged`, `plan_written_back`, `journeys`), the server closes the card itself: `done.confirmed`
with `by: "opora"`. No human, no agent, no model. The write goes the internal state path (`save_node` →
`closure_gate`, never HTTP), is idempotent (a closed or not closable card is left alone) and is recorded in
the activity log as agent `opora` with the card's `nodeIds`.

`sweep` is a step of the execution PR loop (opora_execution_pr_manager): every merged link still marked
`awaitingHumanClose` (the name stays) is re-evaluated, so cards waiting before a restart close on its first
tick. `close_card` is also called by `deliver` right after the merge and checks.
"""
import copy
import logging
from datetime import UTC, datetime

from backend.canvas import opora_card_done as card_done

LOGGER = logging.getLogger(__name__)
ACTOR = "opora"
NOTE = "Uzavřeno serverem: definice hotovo splněná (docs/oporahub-plan-steps.md)."
PATH = "opora:card-auto-close"


def waiting(service, project):
    """`[(workspace, nodeId)]` of merged links awaiting the close, in a stable order."""
    with service.graph_lock_for(project), service.lock_for(project):
        rows = service.db_for(project).execute(
            "SELECT DISTINCT workspace_id,node_id FROM opora_execution_pull_requests WHERE project_id=? AND"
            " state='merged' AND awaiting_human_close=1 ORDER BY workspace_id,node_id", (project,)).fetchall()
    return [(row[0], row[1]) for row in rows]


def _record(service, project, workspace, node):
    from backend.canvas.activity_log import ActivityLog
    try:
        ActivityLog(service).record(actor="agent", agent=ACTOR, method="POST", path=PATH, status=200, described={
            "project": project, "workspace": workspace, "nodeIds": [node],
            "summary": "card_auto_close done.confirmed by=opora"})
    except Exception:  # noqa: BLE001 - the log is an addition, never a condition of the close
        LOGGER.warning("Activity log of the card auto close failed for %s.", node)


def close_card(service, project, workspace, node, note=NOTE):
    """True when this call closed the card; False when it is already closed, has no accepted steps or the
    definition of done still misses anything but the close. The graph lock spans read and write."""
    from backend.canvas.opora_execution_deliver import done_state
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

    store = getattr(service, "desktop_v3_state", None) or DesktopV3State(service)
    with service.graph_lock_for(project):
        stored = store.read(project, workspace)
        if stored["readOnly"]:
            return False
        current = stored["state"]["nodes"].get(node)
        if (current or {}).get("done", {}).get("confirmed"):
            return False
        state = done_state(service, project, workspace, node)
        if state is None or not card_done.closable(state):
            return False
        value = copy.deepcopy(current) if current else {"phase": "discover", "criteria": [], "steps": []}
        at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        value["done"] = {"confirmed": True, "by": ACTOR, "at": at, "note": note[:2000]}
        store.save_node({"project": project, "workspace": workspace, "expectedRevision": stored["revision"],
                         "nodeId": node, "node": value}, actor="system", execution_actor=ACTOR)
    _record(service, project, workspace, node)
    return True


def sweep(service, project):
    """Close every closable card of `project` with a merged link awaiting the close; returns closed nodeIds.
    Already closed cards are skipped on one state read per workspace; a card that fails (concurrent write,
    missing node) stays for the next tick."""
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

    store = getattr(service, "desktop_v3_state", None) or DesktopV3State(service)
    closed, nodes_by_workspace = [], {}
    for workspace, node in waiting(service, project):
        if workspace not in nodes_by_workspace:
            nodes_by_workspace[workspace] = store.read(project, workspace)["state"]["nodes"]
        if nodes_by_workspace[workspace].get(node, {}).get("done", {}).get("confirmed"):
            continue
        try:
            if close_card(service, project, workspace, node):
                closed.append(node)
        except ValueError as error:
            LOGGER.info("Card %s not auto-closed yet: %s", node, error)
    return closed
