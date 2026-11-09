"""HTTP changeset adapters exercise native proposals, human fixtures and replay before stale CAS."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import baseline, accept, FIELDS
from backend.canvas.opora_changesets import OporaChangesets


def test_native_changesets_read_propose_rebase_and_replay_preserve_authority(setup):
    client, service, auth = setup
    view = service.view('draft', 'draft')
    service.save_graph('draft', 'draft', {'nodes': [node('a'), node('b')], 'edges': []}, view['digest'])
    initial = baseline(service)  # Explicit human fixture only.
    native = OporaChangesets(service)
    context = native.context('draft', 'draft')
    documents = {item['nodeId']: item for item in context['documents']}
    proposals = []
    for name in ('a', 'b'):
        payload = {'parentRevision': initial['id'], 'expectedGraphDigest': context['graphDigest'],
                   'subject': 'Proposed ' + name, 'changes': [{'nodeId': name,
                   'expectedRevision': documents[name]['revision'], 'fields': FIELDS}]}
        response = call(client, auth, 'opora_changeset_routes.propose', payload, 'proposal-' + name)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['verified'] and result['acceptedHead'] == initial['id']
        assert result['result']['by']['kind'] == 'agent' and not result['result']['accepted']
        assert call(client, auth, 'opora_changeset_routes.propose', payload, 'proposal-' + name).json() == result
        assert call(client, auth, 'opora_changeset_routes.propose', {**payload, 'subject': 'Changed'}, 'proposal-' + name).status_code == 409
        proposals.append((payload, result))
    assert native.context('draft', 'draft') == context
    revision = accept(service, proposals[0][1]['result'], initial['id'])
    # Replay survives the accepted head advancing; no refreshed payload or duplicate proposal.
    assert call(client, auth, 'opora_changeset_routes.propose', proposals[1][0], 'proposal-b').json() == proposals[1][1]
    assert call(client, auth, 'opora_changeset_routes.propose', proposals[1][0], 'stale').status_code == 409
    data = {'identifier': proposals[1][1]['result']['id'], 'expectedAcceptedHead': revision['id']}
    moved = call(client, auth, 'opora_changeset_routes.rebase', data, 'rebase')
    assert moved.status_code == 200, moved.text
    result = moved.json()['result']
    assert not result['accepted'] and result['supersedes'] == data['identifier']
    assert result['parentRevision'] == revision['id']
    assert call(client, auth, 'opora_changeset_routes.rebase', data, 'rebase').json() == moved.json()
    for action, inputs, expected in (
        ('context', {}, native.context('draft', 'draft')),
        ('history', {}, native.list('draft', 'draft')),
        ('read', {'identifier': result['id']}, result),
        ('revision', {'identifier': revision['id']}, revision),
    ):
        response = call(client, auth, 'opora_changeset_routes.' + action, inputs)
        assert response.status_code == 200 and response.json()['result'] == expected, response.text
    assert service.node_spec('draft', 'draft', 'b')['revision'] == 0
    assert native.context('draft', 'draft')['acceptedHead'] == revision['id']
    assert call(client, auth, 'opora_changeset_routes.read', {'identifier': 'foreign-id'}).status_code == 409


def test_native_graph_rebase_preserves_pending_ids_and_full_readback(setup):
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.canvas.test_opora_graph_proposals import proposal, accept as accept_graph
    client, service, auth = setup
    native = OporaGraphProposals(service)
    left, right = proposal(native, 'Left'), proposal(native, 'Right')
    accept_graph(native, left)
    context = native.context('draft', 'draft')
    payload = {'identifier': right['id'], 'expectedAcceptedHead': context['acceptedHead'],
               'expectedGraphDigest': context['graphDigest']}
    response = call(client, auth, 'opora_graph_routes.rebase', payload, 'graph-rebase')
    assert response.status_code == 200 and response.json()['verified'], response.text
    result = response.json()['result']
    assert result['refs'] == right['refs'] and result['supersedes'] == right['id'] and not result['accepted']
    assert native.read('draft', 'draft', result['id']) == result
    assert native.context('draft', 'draft') == context
    assert call(client, auth, 'opora_graph_routes.rebase', payload, 'graph-rebase').json() == response.json()
    assert call(client, auth, 'opora_graph_routes.rebase', {**payload, 'expectedGraphDigest': 'stale'}, 'graph-rebase').status_code == 409
