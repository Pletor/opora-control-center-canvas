"""Explicit native revision preserves pending identities and observes current research pins."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_graph_change_plan import heart_scope
from backend.canvas.payload_errors import NextStep

CONTRACTS = {'opora_graph_routes.revise': contract(
    ('identifier', 'expectedAcceptedHead', 'expectedGraphDigest', 'subject', 'plan', 'observeResearchSources'),
    effect='proposal', replay=True, cas='native acceptedHead/graph digest and explicit observed source revisions',
    output='New immutable superseding V3 proposal with retained server-owned identities; no acceptance')}
CONTRACTS['opora_graph_routes.revise']['test'] = 'backend/api/brain_opora/test_canvas_capability_revise.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    heart_scope(data['plan'])
    native = OporaGraphProposals(service)
    result = native.revise(data['identifier'], {'project': project, 'workspace': workspace,
        **{key: value for key, value in data.items() if key != 'identifier'}, 'operationId': request_id},
        {'kind': 'agent', 'name': session['worker_name']})
    stored = native.read(project, workspace, result['id'])
    # Receipt records the original pending response; later human acceptance is separate live state.
    if {key: value for key, value in stored.items() if key not in ('accepted', 'supersededBy', 'latestProposalId')} != {key: value for key, value in result.items() if key not in ('accepted', 'supersededBy', 'latestProposalId')}:
        raise NextStep('Revised proposal readback differs.', code='operation_incomplete', hint='Inspect existing revision, do not duplicate it.')
    return {'state': 'persisted', 'verified': True, 'accepted': result['accepted'], 'result': result}
