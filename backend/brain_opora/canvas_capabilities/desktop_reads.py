"""Addressed Desktop reads reuse native stores and retain native absence semantics."""
from starlette.responses import JSONResponse
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.memory_items import MemoryItems
from backend.editor.agent_memory.agent_workspace import AgentWorkspace
from backend.editor.agent_memory.block_access import BlockAccess
from backend.editor.agent_memory.trace import trace
from backend.editor.agent_memory import pipeline_library
from backend.editor.agent_packet.card_checklist import checklists

PREFIX = 'desktop_v3_routes.'
CONTRACTS = {PREFIX + name: contract(required, optional) for name, required, optional in (
    ('read_rule', ('id',), ()), ('read_decision', ('id',), ()), ('read_trace', ('id',), ()),
    ('read_pipelines', (), ()), ('read_block', ('nodeId', 'blockId'), ()),
    ('read_agent_workspace', ('nodeId',), ()), ('read_agent_workspace_summaries', (), ()),
    ('read_card_checklist', (), ('layer',)), ('read_frontier', (), ('nodeId',)),
)}


for _contract in CONTRACTS.values():
    _contract["test"] = "backend/api/brain_opora/test_canvas_capability_desktop.py"


def read(service, project, workspace, capability, data):
    state = DesktopV3State(service)
    action = capability.removeprefix(PREFIX)
    if action == 'read_frontier':
        from backend.editor.agent_memory.card_leases import CardLeases
        from backend.editor.agent_packet.frontier_read import read_frontier
        return read_frontier(state, AgentWorkspace(service, state), CardLeases(service), project, workspace, data.get('nodeId', ''))
    if action in ('read_rule', 'read_decision'):
        return MemoryItems(state).read('rules' if action == 'read_rule' else 'decisions', project, workspace, data['id'])
    if action == 'read_pipelines':
        return pipeline_library.load()
    if action == 'read_agent_workspace_summaries':
        return AgentWorkspace(service, state).summaries(project, workspace)
    if action == 'read_card_checklist':
        with service.reading(project):
            view = service.view(project, workspace)
            if view['readOnly']:
                return {'nodes': {}}
            graph = view['graph']
            identifiers = {node['id'] for node in graph['nodes'] if (node.get('parentId') or '') == data.get('layer', '')}
            return {'nodes': checklists(service, project, workspace, graph, state.read(project, workspace)['state'], identifiers)}
    if action == 'read_trace':
        found = trace(state.read(project, workspace)['state'], service.view(project, workspace)['graph'], data['id'])
    elif action == 'read_block':
        found = BlockAccess(service, state).read(project, workspace, data['nodeId'], data['blockId'])
    elif action == 'read_agent_workspace':
        found = AgentWorkspace(service, state).read(project, workspace, data['nodeId'])
    else:
        raise RuntimeError('No addressed Desktop adapter.')
    return found if found is not None else JSONResponse({'error': 'Entity does not exist in this project/workspace.'}, status_code=404)
