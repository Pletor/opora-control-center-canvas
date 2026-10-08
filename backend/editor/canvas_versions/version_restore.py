"""Preflight and transactional restore of existing workspace-owned stores."""
from backend.canvas.graph import validate_graph
from backend.editor.agent_memory.desktop_v3_state import (
    check_node_branches,
    check_phase_transitions,
    validate_state,
)

from .version_assets import prepare_assets, replace_bytes
from .version_content import SCHEMA, empty_data, restore_records, validate_records


def preflight(canvas, db, project, workspace, graph, state, snapshot, current, stored):
    validate_graph(graph)
    validate_state(state)
    check_node_branches(state, {node["id"] for node in graph["nodes"]})
    try:
        check_phase_transitions(stored["state"], state)
    except ValueError as error:
        raise ValueError("Verzi nelze obnovit kvůli pravidlům pracovního postupu: " + str(error)) from error
    canvas._verify_source_refs(project, workspace, current["graph"], graph)
    # Same closed-card rule as DesktopV3State.save, before any graph or recovery write.
    for node_id, previous in stored["state"]["nodes"].items():
        node = state["nodes"].get(node_id)
        if (node is not None and previous.get("done", {}).get("confirmed")
                and node.get("done", {}).get("confirmed")
                and previous.get("blocks", []) != node.get("blocks", [])):
            raise ValueError("Uzavřená karta má bloky a porty jen ke čtení; nejprve ji otevřete.")
    if snapshot is None:
        return {}, []
    if snapshot.get("schema") != SCHEMA:
        raise ValueError("Nepodporovaná verze pracovního prostoru.")
    validate_records(snapshot["records"], project, workspace)
    return prepare_assets(canvas, db, project, snapshot["assets"])


def check_closed_records(state, target_state, target, current):
    """Content restoration cannot silently write through a card that stays closed."""
    for name in ("specs", "texts", "journals", "agentWorkspaces", "drawings"):
        before = {tuple(row["key"]): row["data"] for row in current[name]}
        after = {tuple(row["key"]): row["data"] for row in target[name]}
        for key in before.keys() | after.keys():
            node_id = key[0]
            old = state["nodes"].get(node_id, {})
            new = target_state["nodes"].get(node_id, {})
            if (old.get("done", {}).get("confirmed") and new.get("done", {}).get("confirmed")
                    and before.get(key, empty_data(name)) != after.get(key, empty_data(name))):
                raise ValueError("Uzavřená karta má obsah jen ke čtení; nejprve ji otevřete.")


def write_content(db, project, workspace, snapshot, current_snapshot, files, drawings, timestamp):
    if snapshot is not None:
        restore_records(db, project, workspace, snapshot["records"], current_snapshot["records"], timestamp)
    for file_id, mime, data in drawings:
        db.execute("INSERT INTO drawing_files VALUES(?,?,?,?,?)", (project, file_id, mime, data, timestamp))
    for path, data in files.items():
        replace_bytes(path, data)
