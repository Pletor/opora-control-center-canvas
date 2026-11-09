"""Native claims retain their token and assignment under retries; no forced release."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.editor.agent_memory.test_block_access import prepared


def test_native_claim_heartbeat_release_and_exact_replay(setup):
    client, service, auth = setup
    prepared(client)
    op = 'desktop_v3_routes.write_lease'
    data = {'nodeId': 'focus', 'op': 'claim', 'ttlSeconds': 60}
    claimed = call(client, auth, op, data, 'lease')
    assert claimed.status_code == 200, claimed.text
    result = claimed.json()
    assert call(client, auth, op, data, 'lease').json() == result
    token = result['result']['token']
    assert len(token) == 64 and result['result']['assignment']['id']
    assert call(client, auth, op, {**data, 'owner': 'human'}, 'forged').status_code == 422
    assert call(client, auth, op, {**data, 'ttlSeconds': 120}, 'lease').status_code == 409
    assert call(client, auth, op, {'nodeId': 'focus', 'op': 'release'}, 'forced').status_code == 409
    heartbeat = call(client, auth, op, {'nodeId': 'focus', 'op': 'heartbeat', 'ttlSeconds': 90, 'token': token}, 'beat')
    assert heartbeat.status_code == 200, heartbeat.text
    released = call(client, auth, op, {'nodeId': 'focus', 'op': 'release', 'token': token}, 'release')
    assert released.status_code == 200, released.text
    assert client.get('/api/desktop-v3/leases', params=SCOPE).json()['nodes'] == {}
    assert call(client, auth, op, data, 'lease').json() == result
    assert client.get('/api/desktop-v3/leases', params=SCOPE).json()['nodes'] == {}


def test_claim_snapshot_failure_keeps_pending_receipt_and_does_not_reclaim(setup, monkeypatch):
    from backend.editor.agent_memory import assignment_snapshots
    client, service, auth = setup
    prepared(client)
    def fail(*args, **kwargs):
        raise RuntimeError('injected after native claim commit')
    monkeypatch.setattr(assignment_snapshots, 'snapshot_assignment', fail)
    data = {'nodeId': 'focus', 'op': 'claim', 'ttlSeconds': 60}
    failed = call(client, auth, 'desktop_v3_routes.write_lease', data, 'partial-claim')
    assert failed.status_code == 409 and failed.json()['code'] == 'operation_incomplete'
    assert 'partial-claim' in failed.json()['hint']
    assert service.db_for('draft').execute("SELECT status FROM canvas_operation_receipts WHERE operation_id='partial-claim'").fetchone()[0] == 'pending'
    before = dict(service.db_for('draft').execute('SELECT * FROM card_leases WHERE node_id=?', ('focus',)).fetchone())
    assert before['owner'] == 'heart'
    again = call(client, auth, 'desktop_v3_routes.write_lease', data, 'partial-claim')
    assert again.status_code == 409, again.text
    after = dict(service.db_for('draft').execute('SELECT * FROM card_leases WHERE node_id=?', ('focus',)).fetchone())
    assert after == before
    other_scope = call(client, auth, 'desktop_v3_routes.write_lease', data, 'outside', scope={'project': 'draft', 'workspace': 'foreign'})
    assert other_scope.status_code == 403
    invalid = call(client, {**auth, 'X-Opora-Gate-Token': 'forged'}, 'desktop_v3_routes.write_lease', data, 'invalid')
    assert invalid.status_code == 401
