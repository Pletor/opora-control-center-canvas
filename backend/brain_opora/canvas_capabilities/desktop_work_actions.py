"""Native working-state operations retain leases, execution guards and content CAS."""
import json

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.canvas.payload_errors import InvalidPayload, NextStep
from backend.editor.agent_memory.agent_output import AgentOutput
from backend.editor.agent_memory.block_access import BlockAccess
from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.pipeline_routing import PipelineRouting

CONTRACTS = {'desktop_v3_routes.' + name: contract(required, optional, effect='draft', replay=True,
    cas='Native Desktop state expectedRevision, lease token and execution/closed-card guards',
    output='Native working-state result with scoped durable replay; accepted authority unchanged')
    for name, required, optional in (
        ('save_state', ('expectedRevision', 'state'), ('leaseTokens',)),
        ('save_node', ('expectedRevision', 'nodeId', 'node'), ('leaseToken',)),
        ('write_block', ('expectedRevision', 'nodeId', 'op'), ('leaseToken',)),
        ('write_pipeline', ('expectedRevision', 'nodeId', 'op', 'reason'), ('profile', 'stages', 'stageId', 'leaseToken')),
        ('write_agent_output', ('expectedRevision', 'nodeId', 'contextVersion', 'output'), ('leaseToken',)),
    )}
for item in CONTRACTS.values():
    item['test'] = 'backend/api/brain_opora/test_canvas_capability_desktop_work.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    state = DesktopV3State(service)
    action_name = capability.split('.')[1]
    leases = CardLeases(service)
    def snapshot():
        db = service.db_for(project)
        return {'desktop': state.read(project, workspace),
                'results': [dict(row) for row in db.execute(
                    'SELECT * FROM agent_result_records WHERE project_id=? AND workspace_id=? ORDER BY sequence',
                    (project, workspace)).fetchall()]}
    def action():
        fields = {key: value for key, value in data.items() if key not in ('leaseToken', 'leaseTokens')}
        payload = {'project': project, 'workspace': workspace, **fields}
        if action_name == 'save_state':
            tokens = data.get('leaseTokens', {})
            if not isinstance(tokens, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in tokens.items()):
                raise InvalidPayload('leaseTokens must map node IDs to native tokens.', field='leaseTokens')
            old = state.read(project, workspace)['state']
            proposed = data['state']
            if isinstance(proposed, dict) and isinstance(proposed.get('nodes'), dict):
                for node_id in old['nodes'].keys() | proposed['nodes'].keys():
                    if old['nodes'].get(node_id) != proposed['nodes'].get(node_id):
                        leases.require(project, workspace, node_id, 'agent', tokens.get(node_id))
            if isinstance(proposed, dict) and isinstance(proposed.get('edges', {}), dict):
                changed = {key for key in old.get('edges', {}).keys() | proposed.get('edges', {}).keys()
                           if old.get('edges', {}).get(key) != proposed.get('edges', {}).get(key)}
                for edge in service.view(project, workspace)['graph']['edges']:
                    if edge['id'] in changed:
                        leases.require(project, workspace, edge['source'], 'agent', tokens.get(edge['source']))
            saved = state.save(payload, actor='agent')
            _remember(service, project, workspace, old, saved['state'])
            return saved
        leases.require(project, workspace, data['nodeId'], 'agent', data.get('leaseToken'))
        if action_name == 'save_node':
            old = state.read(project, workspace)['state']
            saved = state.save_node(payload, actor='agent')
            _remember(service, project, workspace, old, {'nodes': {saved['nodeId']: saved['node']}})
            return saved
        if action_name == 'write_block':
            return BlockAccess(service, state).apply(payload, actor='agent')
        if action_name == 'write_pipeline':
            return PipelineRouting(service, state).apply(payload, actor='agent', agent=session['worker_name'])
        return AgentOutput(service, state).apply({**payload, 'agent': session['worker_name']})
    def verify(before, after, result):
        stored = after['desktop']
        valid = stored['revision'] == result['revision']
        if 'state' in result:
            valid = valid and stored['state'] == result['state']
        if 'node' in result:
            valid = valid and stored['state']['nodes'].get(data['nodeId']) == result['node']
        if 'stages' in result:
            valid = valid and stored['state']['nodes'].get(data['nodeId'], {}).get('stages') == result['stages']
        if 'acceptedResult' in result:
            from backend.editor.agent_packet.desktop_v3_packets import redact_deep
            row = next((row for row in after['results'] if row['id'] == result['acceptedResult']['id']), None)
            record = json.loads(row['record']) if row else None
            valid = valid and record is not None and redact_deep(record) == result['acceptedResult']
            valid = valid and record['output'] == data['output'] and record['contextVersion'] == data['contextVersion']
            valid = valid and record['agent'] == session['worker_name'] and record['nodeId'] == data['nodeId']
        if not valid:
            raise NextStep('Native Desktop readback failed.', code='operation_incomplete', hint='Inspect native state before retry.')
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=action, verify=verify)


def _remember(service, project, workspace, before, after):
    from backend.editor.agent_memory.agent_workspace import AgentWorkspace
    from backend.editor.agent_memory.role_memory_commit import remember_closed
    remember_closed(getattr(service, 'memory_service', None), AgentWorkspace(service), project, workspace, before, after)
