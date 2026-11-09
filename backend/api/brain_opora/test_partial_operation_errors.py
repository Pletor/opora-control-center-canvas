"""First HTTP failure must disclose partial native writes, not only a retry."""
import pytest

from backend.api.brain_opora.test_canvas_capability_routes import ORIGIN, SCOPE, call, setup
from backend.canvas.operation_receipts import Receipt
from backend.editor.brief_vault import operation_reviews as vault
from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.brief_vault.test_operation_reviews import seed
from backend.editor.node import removal_reviews
from backend.editor.node.test_removal_reviews import data

__all__ = ['setup']
WRITE = 'brief_vault_routes.brief_vault_write'
COMMAND = {'op': 'create', 'title': 'Preserved', 'text': 'Exact source', 'discipline': 'be', 'scopeNodeId': ''}


def incomplete(response, identifier):
    assert response.status_code == 409, response.text
    body = response.json()
    assert body['code'] == 'operation_incomplete'
    assert identifier in body['hint'] and 'reconcile' in body['hint']
    assert 'nebyly' not in body['error']


@pytest.mark.parametrize('human', [False, True])
@pytest.mark.parametrize('point', ['readback', 'receipt'])
@pytest.mark.parametrize('fault', [RuntimeError, OSError])
def test_vault_first_error_reports_partial_write_and_retry_never_duplicates(setup, monkeypatch, human, point, fault):
    client, service, auth = setup
    seed(service)
    key = 'partial-vault'
    if human:
        fragment = call(client, auth, WRITE, {'operation': COMMAND}, 'seed').json()['result']['fragment']
        operation = {'op': 'delete', 'fragmentId': fragment['id'], 'expectedRevision': 1, 'note': 'Explicit deletion'}
        intent = call(client, auth, WRITE, {'operation': operation}, key).json()['result']
        def request():
            return client.post(f'/api/brief-vault/reviews/{key}/accept', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': intent['digest']})
    else:
        def request():
            return call(client, auth, WRITE, {'operation': COMMAND}, key)
    def fail(*args, **kwargs):
        raise fault('Injected after native commit')
    if point == 'readback':
        monkeypatch.setattr(vault, 'verify_result', fail)
    else:
        original = Receipt.complete
        def complete(self, db, response):
            if self.scope[2] == (vault.DECISION if human else vault.KIND):
                fail()
            return original(self, db, response)
        monkeypatch.setattr(Receipt, 'complete', complete)
    incomplete(request(), key)
    db = service.db_for('draft')
    count = db.execute('SELECT count(*) FROM brief_fragment_revisions').fetchone()[0]
    if human:
        assert BriefVault(service).fragment('draft', 'draft', fragment['id'])['fragment']['deleted']
        assert client.get(f'/api/brief-vault/reviews/{key}', params=SCOPE).json()['decision']['status'] == 'pending'
    else:
        assert count == 1
    assert request().json()['code'] == 'operation_incomplete'
    assert db.execute('SELECT count(*) FROM brief_fragment_revisions').fetchone()[0] == count


@pytest.mark.parametrize('point', ['native', 'readback', 'receipt'])
def test_working_removal_first_error_retains_exact_recovery(setup, monkeypatch, point):
    client, service, auth = setup
    seed(service)
    operation = data(service)
    def fail(*args, **kwargs):
        raise OSError('Injected after native recovery save')
    if point == 'native':
        monkeypatch.setattr(service, 'save_graph', fail)
    elif point == 'readback':
        monkeypatch.setattr(removal_reviews, 'verify', fail)
    else:
        monkeypatch.setattr(Receipt, 'complete', fail)
    first = call(client, auth, 'canvas_routes.remove_item', operation, 'partial-remove')
    incomplete(first, 'partial-remove')
    db = service.db_for('draft')
    assert db.execute('SELECT count(*) FROM removal_restores').fetchone()[0] == 1
    second = call(client, auth, 'canvas_routes.remove_item', operation, 'partial-remove')
    assert second.json()['code'] == 'operation_incomplete'
    assert db.execute('SELECT count(*) FROM removal_restores').fetchone()[0] == 1


def test_unchanged_vault_validation_error_preserved_and_receipt_discarded(setup, monkeypatch):
    client, service, auth = setup
    seed(service)
    def invalid(*args, **kwargs):
        raise ValueError('Exact native validation message')
    monkeypatch.setattr(BriefVault, 'apply', invalid)
    result = call(client, auth, WRITE, {'operation': COMMAND}, 'invalid')
    assert result.json() == {'error': 'Exact native validation message'}
    assert service.db_for('draft').execute("SELECT count(*) FROM canvas_operation_receipts WHERE operation_id='invalid'").fetchone()[0] == 0

@pytest.mark.parametrize('point', ['native', 'receipt'])
def test_desktop_first_oserror_reports_persisted_state(setup, monkeypatch, point):
    from backend.api.brain_opora.test_canvas_capability_desktop_reviews import prepare_autonomy
    from backend.canvas.test_canvas_plan import seed as desktop_seed
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    client, _service, auth = setup
    desktop_seed(client)
    review, _ = prepare_autonomy(client, auth, 'partial-desktop')
    original = DesktopV3State.set_autonomy
    def fail(*args, **kwargs):
        raise OSError('Injected after native autonomy save')
    if point == 'native':
        def native(self, payload):
            original(self, payload)
            fail()
        monkeypatch.setattr(DesktopV3State, 'set_autonomy', native)
    else:
        monkeypatch.setattr(Receipt, 'complete', fail)
    def request():
        return client.post('/api/desktop-reviews/partial-desktop/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']})
    incomplete(request(), 'partial-desktop')
    saved = client.get('/api/desktop-v3/state', params=SCOPE).json()
    assert saved['state']['autonomy']['s0']['note'] == 'Only this sector'
    assert client.get('/api/desktop-reviews/partial-desktop', params=SCOPE).json()['state'] == 'incomplete'
    assert request().json()['code'] == 'operation_incomplete'
    assert client.get('/api/desktop-v3/state', params=SCOPE).json() == saved

@pytest.mark.parametrize('owner', ['desktop', 'removal'])
def test_unchanged_native_validation_stays_original(setup, monkeypatch, owner):
    client, service, auth = setup
    def invalid(*args, **kwargs):
        raise ValueError('Exact native validation message')
    if owner == 'desktop':
        from backend.api.brain_opora.test_canvas_capability_desktop_reviews import prepare_autonomy
        from backend.canvas.test_canvas_plan import seed as desktop_seed
        from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
        desktop_seed(client)
        review, _ = prepare_autonomy(client, auth, 'unchanged')
        monkeypatch.setattr(DesktopV3State, 'set_autonomy', invalid)
        result = client.post('/api/desktop-reviews/unchanged/apply', headers={'origin': ORIGIN}, json={**SCOPE, 'digest': review['digest']})
        kind = 'desktop-human-application'
    else:
        seed(service)
        operation = data(service)
        monkeypatch.setattr(removal_reviews, '_action', invalid)
        result = call(client, auth, 'canvas_routes.remove_item', operation, 'unchanged')
        kind = 'canvas-review.remove_item'
    assert result.json() == {'error': 'Exact native validation message'}
    assert service.db_for('draft').execute("SELECT count(*) FROM canvas_operation_receipts WHERE operation_id='unchanged' AND operation_kind=?", (kind,)).fetchone()[0] == 0
