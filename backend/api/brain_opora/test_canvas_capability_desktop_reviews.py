"""Immutable preparations require explicit human native action with unchanged pins."""
from datetime import UTC, datetime, timedelta
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE, ORIGIN
from backend.canvas.test_canvas_plan import seed
from backend.editor.agent_memory.test_memory_items import rule


def prepare_autonomy(client, auth, key='grant'):
    stored = client.get('/api/desktop-v3/state', params=SCOPE).json()
    data = {'expectedRevision': stored['revision'], 'sectorId': 's0',
            'until': (datetime.now(UTC) + timedelta(days=1)).isoformat(), 'note': 'Only this sector'}
    result = call(client, auth, 'desktop_v3_routes.grant_autonomy', data, key)
    assert result.status_code == 200, result.text
    assert call(client, auth, 'desktop_v3_routes.grant_autonomy', data, key).json() == result.json()
    return result.json()['review'], stored


def test_autonomy_exact_human_review_missing_foreign_stale_and_replay(setup):
    client, service, auth = setup
    seed(client)
    review, before = prepare_autonomy(client, auth)
    path = '/api/desktop-reviews/' + review['id']
    assert client.get(path, params=SCOPE).json()['review'] == review
    assert call(client, auth, 'desktop_review_routes.review', {'identifier': review['id']}).json()['result']['review'] == review
    decision = call(client, auth, 'desktop_review_routes.decide', {'identifier': review['id'], 'digest': review['digest']})
    assert decision.status_code == 200 and decision.json()['applied'] is False
    assert call(client, auth, 'desktop_review_routes.decide', {'identifier': review['id'], 'digest': 'edited'}).status_code == 409
    assert client.get('/api/desktop-v3/state', params=SCOPE).json() == before
    assert client.get('/api/desktop-reviews/missing', params=SCOPE).status_code == 409
    assert client.get(path, params={**SCOPE, 'workspace': 'foreign'}, headers=auth).status_code == 403
    assert client.post(path + '/apply', headers=auth, json={**SCOPE, 'digest': review['digest']}).status_code == 403
    assert client.post(path + '/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': 'edited'}).status_code == 409
    applied = client.post(path + '/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']})
    assert applied.status_code == 200, applied.text
    assert applied.json()['nativeState']['state']['autonomy']['s0']['note'] == 'Only this sector'
    readback = client.get(path, params=SCOPE).json()
    assert readback['state'] == 'applied' and readback['applied'] is True
    assert readback['application'] == applied.json()
    assert client.post(path + '/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']}).json() == applied.json()
    assert client.get('/api/desktop-v3/state', params=SCOPE).json() == applied.json()['nativeState']
    from backend.canvas.canvas_service import CanvasService
    from backend.editor.agent_memory.desktop_review import read
    reopened = CanvasService(service.root)
    try:
        durable = read(reopened, 'draft', 'draft', review['id'])
        assert durable['applied'] and durable['application'] == applied.json()
    finally:
        reopened.close()


def test_rule_single_and_batch_preparations_apply_exact_native_preimages(setup):
    client, service, auth = setup
    seed(client)
    for name in ('a', 'b', 'c'):
        result = client.post('/api/desktop-v3/rule', headers=auth,
            json={**SCOPE, 'id': name, 'op': 'add', 'expected': None, 'item': rule(name, 'Proposed ' + name)})
        assert result.status_code == 200, result.text
    stored = client.get('/api/desktop-v3/state', params=SCOPE).json()
    entries = {item['id']: item for item in stored['state']['rules']}
    for key, operation, data in (
        ('single', 'review_rule', {'id': 'a', 'expected': entries['a'], 'decision': 'approve'}),
        ('batch', 'review_rules', {'items': [{'id': n, 'expected': entries[n]} for n in ('b', 'c')], 'decision': 'reject'}),
    ):
        result = call(client, auth, 'desktop_v3_routes.' + operation, data, key)
        assert result.status_code == 200, result.text
        review = result.json()['review']
        applied = client.post('/api/desktop-reviews/' + key + '/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']})
        assert applied.status_code == 200, applied.text
    rules = client.get('/api/desktop-v3/state', params=SCOPE).json()['state']['rules']
    assert len(rules) == 1 and rules[0]['id'] == 'a' and 'by' not in rules[0]


def test_review_rejects_graph_race_and_after_write_retry_is_inspectable(setup, monkeypatch):
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    client, service, auth = setup
    seed(client)
    review, before = prepare_autonomy(client, auth, 'stale')
    view = client.get('/api/view', params=SCOPE).json()
    view['graph']['nodes'][0]['name'] = 'Changed after review'
    assert client.post('/api/graph', headers={'origin': ORIGIN}, json={**SCOPE, 'graph': view['graph'], 'digest': view['digest']}).status_code == 200
    denied = client.post('/api/desktop-reviews/stale/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']})
    assert denied.status_code == 409
    review, _ = prepare_autonomy(client, auth, 'interrupted')
    original = DesktopV3State.set_autonomy
    def interrupted(self, payload):
        original(self, payload)
        raise RuntimeError('injected after native autonomy save')
    monkeypatch.setattr(DesktopV3State, 'set_autonomy', interrupted)
    first = client.post('/api/desktop-reviews/interrupted/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']})
    assert first.status_code == 409 and first.json()['code'] == 'operation_incomplete'
    assert 'interrupted' in first.json()['hint']
    applied = client.get('/api/desktop-v3/state', params=SCOPE).json()
    assert applied['state']['autonomy']['s0']['note'] == 'Only this sector'
    assert client.get('/api/desktop-reviews/interrupted', params=SCOPE).json()['state'] == 'incomplete'
    retried = client.post('/api/desktop-reviews/interrupted/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']})
    assert retried.status_code == 409
    assert retried.json()['code'] == 'operation_incomplete'
    assert client.get('/api/desktop-v3/state', params=SCOPE).json() == applied


def test_sector_confirmation_is_prepared_then_native_human_applied(setup):
    from backend.editor.agent_memory.test_completion_evidence import evidence
    client, service, auth = setup
    seed(client)
    stored = client.get('/api/desktop-v3/state', params=SCOPE).json()
    node = stored['state']['nodes']['n0']
    node['evidence'] = evidence()
    node['done'] = {'by': 'agent', 'confirmed': False, 'note': 'Ready for review', 'at': '2026-11-09T00:00:00Z'}
    saved = client.post('/api/desktop-v3/state', headers={'origin': ORIGIN}, json={**SCOPE, 'state': stored['state'], 'expectedRevision': stored['revision']})
    assert saved.status_code == 200, saved.text
    prepared = call(client, auth, 'desktop_v3_routes.confirm_sector_proposals', {'sectorId': 's0', 'nodeIds': ['n0'], 'expectedRevision': saved.json()['revision']}, 'confirm')
    assert prepared.status_code == 200, prepared.text
    assert client.get('/api/desktop-v3/state', params=SCOPE).json()['state']['nodes']['n0']['done']['confirmed'] is False
    applied = client.post('/api/desktop-reviews/confirm/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': prepared.json()['review']['digest']})
    assert applied.status_code == 200, applied.text
    assert applied.json()['nativeState']['state']['nodes']['n0']['done']['by'] == 'human'


def test_full_agent_authority_does_not_impersonate_human(setup):
    import pytest
    from backend.canvas.authority import begin, end
    from backend.editor.agent_memory.desktop_review import apply
    from backend.brain_opora.determinism.gate_payloads import GateError
    client, service, auth = setup
    seed(client)
    review, before = prepare_autonomy(client, auth)
    _, token = begin('agent', 'human', 'draft')
    try:
        with pytest.raises(GateError):
            apply(service, 'draft', 'draft', review['id'], review['digest'], 'agent')
    finally:
        end(token)
    assert client.get('/api/desktop-v3/state', params=SCOPE).json() == before
