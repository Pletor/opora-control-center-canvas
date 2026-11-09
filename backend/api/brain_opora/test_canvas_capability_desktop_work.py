"""Actual native working state with CAS, leases, no fabricated actor or completion."""
import copy
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.editor.agent_memory.test_agent_output import prepared, output


def test_node_block_pipeline_and_bulk_state_native_replay(setup):
    client, service, auth = setup
    prepared(client)
    before = client.get('/api/desktop-v3/state', params=SCOPE).json()
    node = copy.deepcopy(before['state']['nodes']['focus']); node['phase'] = 'build'
    data = {'expectedRevision': before['revision'], 'nodeId': 'focus', 'node': node}
    saved = call(client, auth, 'desktop_v3_routes.save_node', data, 'node')
    assert saved.status_code == 200, saved.text
    assert call(client, auth, 'desktop_v3_routes.save_node', data, 'node').json() == saved.json()
    assert call(client, auth, 'desktop_v3_routes.save_node', data, 'stale').status_code == 409
    rev = saved.json()['result']['revision']
    block = call(client, auth, 'desktop_v3_routes.write_block', {'nodeId': 'focus', 'expectedRevision': rev,
        'op': {'kind': 'update', 'blockId': 'b2', 'patch': {'text': 'Native working block'}}}, 'block')
    assert block.status_code == 200, block.text
    rev = block.json()['result']['revision']
    pipeline = call(client, auth, 'desktop_v3_routes.write_pipeline', {'nodeId': 'focus', 'expectedRevision': rev,
        'op': 'route', 'reason': 'Native research validation', 'profile': 'research'}, 'pipeline')
    assert pipeline.status_code == 200, pipeline.text
    current = client.get('/api/desktop-v3/state', params=SCOPE).json()
    proposed = copy.deepcopy(current['state']); proposed['nodes']['focus']['blocks'][1]['text'] = 'Bulk update'
    bulk = call(client, auth, 'desktop_v3_routes.save_state', {'expectedRevision': current['revision'], 'state': proposed}, 'bulk')
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()['result']['state'] == client.get('/api/desktop-v3/state', params=SCOPE).json()['state']


def test_lease_is_required_for_node_and_bulk_and_output_uses_verified_identity(setup):
    client, service, auth = setup
    prepared(client)
    held = call(client, auth, 'desktop_v3_routes.write_lease', {'nodeId': 'focus', 'op': 'claim', 'ttlSeconds': 60}, 'claim')
    assert held.status_code == 200, held.text
    token = held.json()['result']['token']
    current = client.get('/api/desktop-v3/state', params=SCOPE).json()
    node = copy.deepcopy(current['state']['nodes']['focus']); node['phase'] = 'build'
    data = {'nodeId': 'focus', 'node': node, 'expectedRevision': current['revision']}
    assert call(client, auth, 'desktop_v3_routes.save_node', data, 'unleased').status_code == 409
    bulk = copy.deepcopy(current['state']); bulk['nodes']['focus'] = node
    assert call(client, auth, 'desktop_v3_routes.save_state', {'state': bulk, 'expectedRevision': current['revision']}, 'bulk-unleased').status_code == 409
    brief = client.get('/api/desktop-v3/node-brief', params={**SCOPE, 'nodeId': 'focus'}).json()
    data = {'nodeId': 'focus', 'expectedRevision': current['revision'], 'contextVersion': brief['outputContract']['request']['contextVersion'],
            'output': output(), 'leaseToken': token}
    assert call(client, auth, 'desktop_v3_routes.write_agent_output', {**data, 'agent': 'human'}, 'forged').status_code == 422
    accepted = call(client, auth, 'desktop_v3_routes.write_agent_output', data, 'output')
    assert accepted.status_code == 200, accepted.text
    assert call(client, auth, 'desktop_v3_routes.write_agent_output', data, 'output').json() == accepted.json()
    state = client.get('/api/desktop-v3/state', params=SCOPE).json()['state']
    assert state['edges']['e-out']['agent'] == 'heart'
    assert state['nodes']['focus']['done']['confirmed'] is False


def test_closed_card_and_bulk_edge_lease_cannot_be_bypassed(setup):
    client, service, auth = setup
    prepared(client)
    current = client.get('/api/desktop-v3/state', params=SCOPE).json()
    closing = copy.deepcopy(current['state']['nodes']['focus'])
    closing['done'] = {'confirmed': True, 'at': '2026-11-09T00:00:00Z', 'by': 'human', 'note': 'Forged'}
    refused = call(client, auth, 'desktop_v3_routes.save_node', {'nodeId': 'focus', 'node': closing, 'expectedRevision': current['revision']}, 'close')
    assert refused.status_code == 403, refused.text
    held = call(client, auth, 'desktop_v3_routes.write_lease', {'nodeId': 'focus', 'op': 'claim', 'ttlSeconds': 60}, 'claim')
    assert held.status_code == 200, held.text
    state = copy.deepcopy(current['state'])
    state['edges']['e-out'] = {'log': '', 'summary': '', 'handoff': 'Bypass attempt', 'improvements': '', 'errors': '',
                             'updatedAt': '2026-11-09T00:00:00Z', 'by': 'agent', 'agent': 'heart'}
    denied = call(client, auth, 'desktop_v3_routes.save_state', {'state': state, 'expectedRevision': current['revision']}, 'edge-unleased')
    assert denied.status_code == 409, denied.text
    assert client.get('/api/desktop-v3/state', params=SCOPE).json() == current


def test_foreign_card_token_and_closed_card_native_guards(setup):
    client, service, auth = setup
    prepared(client)
    held = call(client, auth, 'desktop_v3_routes.write_lease', {'nodeId': 'focus', 'op': 'claim', 'ttlSeconds': 60}, 'focus')
    other = call(client, auth, 'desktop_v3_routes.write_lease', {'nodeId': 'dalsi', 'op': 'claim', 'ttlSeconds': 60}, 'other')
    assert held.status_code == other.status_code == 200
    current = client.get('/api/desktop-v3/state', params=SCOPE).json()
    block = {'nodeId': 'focus', 'expectedRevision': current['revision'], 'op': {'kind': 'update', 'blockId': 'b2', 'patch': {'text': 'wrong token'}},
             'leaseToken': other.json()['result']['token']}
    assert call(client, auth, 'desktop_v3_routes.write_block', block, 'foreign-token').status_code == 409
    node = copy.deepcopy(current['state']['nodes']['focus'])
    from backend.editor.agent_memory.test_completion_evidence import evidence
    node['evidence'] = evidence()
    node['done'] = {'confirmed': True, 'at': '2026-11-09T00:00:00Z', 'by': 'human', 'note': 'Fixture closed by human'}
    closed = client.post('/api/desktop-v3/node', headers={'origin': 'http://127.0.0.1:8740'}, json={**SCOPE,
        'nodeId': 'focus', 'node': node, 'expectedRevision': current['revision']})
    assert closed.status_code == 200, closed.text
    block.update(expectedRevision=closed.json()['revision'], leaseToken=held.json()['result']['token'])
    assert call(client, auth, 'desktop_v3_routes.write_block', block, 'closed').status_code == 409


def test_output_readback_checks_immutable_content_not_only_id(setup, monkeypatch):
    from backend.editor.agent_memory.agent_output import AgentOutput
    client, service, auth = setup
    prepared(client)
    current = client.get('/api/desktop-v3/state', params=SCOPE).json()
    brief = client.get('/api/desktop-v3/node-brief', params={**SCOPE, 'nodeId': 'focus'}).json()
    original = AgentOutput.apply
    def corrupt(self, payload):
        saved = original(self, payload)
        saved['acceptedResult']['output']['done']['note'] = 'Corrupted readback only'
        return saved
    monkeypatch.setattr(AgentOutput, 'apply', corrupt)
    data = {'nodeId': 'focus', 'expectedRevision': current['revision'], 'contextVersion': brief['outputContract']['request']['contextVersion'], 'output': output()}
    rejected = call(client, auth, 'desktop_v3_routes.write_agent_output', data, 'corrupt')
    assert rejected.status_code == 409 and rejected.json()['code'] == 'operation_incomplete', rejected.text
    retry = call(client, auth, 'desktop_v3_routes.write_agent_output', data, 'corrupt')
    assert retry.status_code == 409 and retry.json()['code'] == 'operation_incomplete'
