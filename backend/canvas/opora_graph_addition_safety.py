"""Legacy additive proposals recheck current completed-card protection without writes."""
from backend.canvas.opora_graph_change_safety import preflight
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def validate_additions(service, project, workspace, working, result, accepted, approved):
    from backend.app import guards  # líně: balíček backend.app načítá factory (cyklus importů)
    state = DesktopV3State(service).current(project, workspace)["state"]
    preflight(accepted, working, result, approved, state, set(), set(), project=project)
    for before, after in ((working, result), (accepted, approved)):
        existing = {node["id"] for node in before["nodes"]}
        nodes = {node["id"]: node for node in after["nodes"]}
        for node in after["nodes"]:
            if node["id"] in existing:
                continue
            cursor, seen = node.get("parentId"), set()
            while cursor in nodes and cursor not in seen:
                if state["nodes"].get(cursor, {}).get("done", {}).get("confirmed") and guards.check(
                        "confirmed_reopen", project, blocked=True, subject=cursor,
                        message=f"Nová karta pod potvrzeným předkem {cursor}."):
                    raise ValueError("A human must reopen confirmed ancestors before adding new children.")
                seen.add(cursor)
                cursor = nodes[cursor].get("parentId")
