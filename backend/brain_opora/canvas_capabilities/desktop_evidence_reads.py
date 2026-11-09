"""Native Desktop evidence and configured packet/brief providers, without lossy copies."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.editor.agent_memory.agent_results import AgentResults
from backend.editor.agent_memory.assignment_snapshots import assignment_comparison
from backend.editor.agent_handoff.external_agent_tasks import ExternalAgentTasks
from backend.canvas.opora_process_links import brief_metadata

PREFIX = 'desktop_v3_routes.'
CONTRACTS = {
    PREFIX + 'read_assignment_comparison': contract(('nodeId', 'id'), ('source',)),
    PREFIX + 'read_node_brief': contract(('nodeId',)),
    PREFIX + 'read_agent_results': contract(('nodeId',), ('before',), types={'before': 'integer'}),
    PREFIX + 'packet_snapshot_read': contract(('snapshot_id',)),
    PREFIX + 'external_read': contract(('snapshot_id', 'nodeId', 'digest')),
}
for _contract in CONTRACTS.values():
    _contract['test'] = 'backend/api/brain_opora/test_canvas_capability_desktop_evidence.py'


def read(service, project, workspace, capability, data):
    if capability.endswith('read_assignment_comparison'):
        return assignment_comparison(service, project, workspace, data['nodeId'], data['id'], data.get('source', 'result'))
    if capability.endswith('read_node_brief'):
        return {**service.node_briefs.build(project, workspace, data['nodeId']),
                'processSync': brief_metadata(project, workspace, data['nodeId'])}
    if capability.endswith('read_agent_results'):
        return AgentResults(service).history(project, workspace, data['nodeId'], data.get('before'))
    if capability.endswith('packet_snapshot_read'):
        stored = service.desktop_packets.load(data['snapshot_id'], project, workspace)
        return {key: stored[key] for key in ('id', 'digest', 'packet', 'createdAt')}
    if capability.endswith('external_read'):
        return ExternalAgentTasks(service.desktop_packets).read(data['snapshot_id'],
            {'project': project, 'workspace': workspace, 'nodeId': data['nodeId'], 'digest': data['digest']})
    raise RuntimeError('No native Desktop evidence reader.')
