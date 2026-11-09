"""Named revise is distinct from rebase and preserves pending card identity and old history."""
from copy import deepcopy
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.test_opora_graph_proposals import proposal, accept
from backend.canvas.test_opora_graph_complete import full_plan
from backend.canvas.test_opora_graph_changes import approve


def test_revise_native_ids_history_scope_and_exact_replay_after_acceptance(setup):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    accept(native, proposal(native))
    old = proposal(native, plan=full_plan())
    context = native.context('draft', 'draft')
    plan = deepcopy(old['plan'])
    plan['nodes'][0].update(name='Readable research verification', text='Full revised explanation')
    data = {'identifier': old['id'], 'expectedAcceptedHead': context['acceptedHead'],
            'expectedGraphDigest': context['graphDigest'], 'subject': 'Reviewed revision',
            'plan': plan, 'observeResearchSources': True}
    response = call(client, auth, 'opora_graph_routes.revise', data, 'revise')
    assert response.status_code == 200, response.text
    saved = response.json()
    new = saved['result']
    assert new['refs'] == old['refs'] and new['supersedes'] == old['id'] and not new['accepted']
    historical = native.read('draft', 'draft', old['id'])
    assert {key: value for key, value in historical.items() if key not in ('supersededBy', 'latestProposalId')} == old
    assert historical['latestProposalId'] == new['id']
    assert native.context('draft', 'draft') == context
    assert call(client, auth, 'opora_graph_routes.revise', data, 'revise').json() == saved
    assert call(client, auth, 'opora_graph_routes.revise', {**data, 'subject': 'conflict'}, 'revise').status_code == 409
    assert call(client, auth, 'opora_graph_routes.revise', data, 'foreign', scope={'project':'foreign','workspace':'draft'}).status_code == 403
    approve(OporaGraphChanges(service), new)
    assert call(client, auth, 'opora_graph_routes.revise', data, 'revise').json() == saved
    assert service.texts.read(('draft', 'draft', old['refs']['source']))['text'] == 'Full revised explanation'


def test_original_create_replay_after_revision_keeps_immutable_response(setup):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    accept(native, proposal(native))
    context = native.context('draft', 'draft')
    data = {'parentRevision': context['acceptedHead'], 'expectedGraphDigest': context['graphDigest'],
            'subject': 'Original', 'plan': full_plan()}
    initial = call(client, auth, 'opora_graph_routes.create', data, 'original')
    assert initial.status_code == 200, initial.text
    original = initial.json()
    plan = deepcopy(data['plan'])
    plan['nodes'][0]['name'] = 'Revised readable name'
    revised = call(client, auth, 'opora_graph_routes.revise', {
        'identifier': original['result']['id'], 'expectedAcceptedHead': context['acceptedHead'],
        'expectedGraphDigest': context['graphDigest'], 'subject': 'Revision',
        'plan': plan, 'observeResearchSources': True}, 'revision')
    assert revised.status_code == 200, revised.text
    assert revised.json()['result']['refs'] == original['result']['refs']
    replay = call(client, auth, 'opora_graph_routes.create', data, 'original')
    assert replay.status_code == 200 and replay.json() == original
    assert native.read('draft', 'draft', original['result']['id'])['latestProposalId'] == revised.json()['result']['id']
