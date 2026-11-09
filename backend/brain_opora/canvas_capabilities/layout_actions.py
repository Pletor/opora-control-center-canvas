"""Native grid layout is a working draft initially, or an explicit reviewed semantic patch."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.brain_opora.canvas_capabilities.proposal_writes import persist
from backend.canvas.canvas_layout import apply_layout, arrange
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.payload_errors import NextStep

CONTRACTS = {'canvas_routes.canvas_layout': contract(
    ('parentRevision', 'expectedGraphDigest', 'subject', 'area', 'order', 'columns'), ('color',),
    effect='draft-or-proposal', replay=True, cas='native acceptedHead and graph digest',
    output='Initial native working layout, or immutable V3 layout proposal with explicit color/parent/position review')}
CONTRACTS['canvas_routes.canvas_layout']['test'] = 'backend/api/brain_opora/test_canvas_capability_layout.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    native = OporaGraphProposals(service)
    def snapshot():
        return {'context': native.context(project, workspace), 'proposals': native.list(project, workspace)}
    def action():
        context = native.context(project, workspace)
        if context['acceptedHead'] != data['parentRevision'] or context['graphDigest'] != data['expectedGraphDigest']:
            raise NextStep('Layout context changed.', code='layout_conflict', hint='Read current context before proposing a new layout.')
        arguments = {key: data[key] for key in ('area', 'order', 'columns', 'color') if key in data}
        if context['acceptedHead'] is None:
            return {'kind': 'working-draft', **apply_layout(service, {'project': project, 'workspace': workspace,
                'digest': data['expectedGraphDigest'], **arguments}, actor='agent')}
        graph = context['workingGraph']
        result = arrange(graph, arguments['area'], arguments['order'], arguments['columns'], arguments.get('color'))
        old = {node['id']: node for node in graph['nodes']}
        updates = []
        for node in result['nodes']:
            fields = {key: value for key, value in node.items() if old[node['id']].get(key) != value}
            if fields:
                updates.append({'id': node['id'], 'fields': fields})
        return {'kind': 'proposal', **persist(service, project, workspace, session,
            {key: data[key] for key in ('parentRevision', 'expectedGraphDigest', 'subject')} |
            {'plan': {'draftVersion': 3, 'updateNodes': updates}}, request_id)}
    def verify(before, after, result):
        if result['kind'] == 'working-draft':
            valid = service.view(project, workspace)['graph'] == result['graph']
        else:
            valid = before['context'] == after['context'] and native.read(project, workspace, result['result']['id']) == result['result']
        if not valid:
            raise NextStep('Native layout readback failed.', code='operation_incomplete', hint='Inspect existing layout/proposal.')
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=action, verify=verify)
