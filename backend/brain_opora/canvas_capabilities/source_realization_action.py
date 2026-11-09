"""Native filesystem-verified working source metadata, never accepted completion."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.canvas.payload_errors import NextStep
from backend.canvas.source_realization import realize_source, source_status
from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

CONTRACTS = {'desktop_v3_routes.write_source_realization': contract(('nodeId', 'digest', 'commit', 'prUrl'),
    ('leaseToken',), effect='draft', replay=True, cas='Native working graph digest, execution guard and actual filesystem/merge evidence',
    output='Verified working sourceRef/realization metadata; accepted product completion is unchanged')}
CONTRACTS['desktop_v3_routes.write_source_realization']['test'] = 'backend/api/brain_opora/test_canvas_capability_source_realization.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    state = DesktopV3State(service)
    def snapshot():
        view = service.view(project, workspace)
        stored = state.read(project, workspace)
        return {'view': {'graph': view['graph'], 'digest': view['digest']},
                'state': {'state': stored['state'], 'revision': stored['revision']}}
    def action():
        CardLeases(service).require(project, workspace, data['nodeId'], 'agent', data.get('leaseToken'))
        payload = {'project': project, 'workspace': workspace, **{key: value for key, value in data.items() if key != 'leaseToken'}}
        return realize_source(state, payload, actor='agent')
    def verify(before, after, result):
        node = next((n for n in after['view']['graph']['nodes'] if n['id'] == data['nodeId']), None)
        status = source_status(service, project, workspace)['nodes'].get(data['nodeId'], {})
        if (after['view']['graph'] != result['graph'] or node is None or node['sourceRef']['origin'] != 'existing'
                or node['realization']['commit'] != data['commit'] or node['realization']['prUrl'] != data['prUrl']
                or status.get('status') != 'present'):
            raise NextStep('Native source realization readback failed.', code='operation_incomplete', hint='Inspect working metadata and source filesystem.')
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=action, verify=verify)
