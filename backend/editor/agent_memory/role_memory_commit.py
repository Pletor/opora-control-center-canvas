"""Optional role memory projection shared by native HTTP and capability writes."""

def node_role(node):
    value = node.get('agentRole') if isinstance(node, dict) else None
    return value if isinstance(value, str) and value else None


def confirmed_nodes(state_payload):
    nodes = state_payload.get('nodes', {}) if isinstance(state_payload, dict) else {}
    return {node_id for node_id, node in nodes.items()
            if isinstance(node, dict) and bool(node.get('done', {}).get('confirmed', False))}


def commit_card(memory_service, agent_workspace, project, workspace, state, node_id):
    role = node_role(state['nodes'].get(node_id, {}))
    if role is None:
        return
    space = agent_workspace.read(project, workspace, node_id) or {}
    sections = {key: value for key, value in (space.get('workspace') or {}).items()
                if key not in ('updatedAt', 'by')}
    memory_service.commit_card(role, project, node_id, sections)


def remember_closed(memory_service, agent_workspace, project, workspace, before, after):
    if memory_service is None:
        return
    for node_id in sorted(confirmed_nodes(after) - confirmed_nodes(before)):
        try:
            commit_card(memory_service, agent_workspace, project, workspace, after, node_id)
        except Exception:  # noqa: BLE001, S110 - optional native projection must not affect save
            pass  # Same native policy: optional projection cannot undo a successful save.
