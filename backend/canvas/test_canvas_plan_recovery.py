"""Crash recovery must replay one frozen operation, never synthesize a second plan."""
import json
from copy import deepcopy

import pytest

from backend.canvas.canvas_plan import apply_plan
from backend.canvas.canvas_service import CanvasService
from backend.canvas.operation_receipts import Receipt
from backend.canvas.payload_errors import NextStep
from backend.canvas.test_operation_receipts import payload
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414


def intent(service):
    return json.loads(service.db_for('draft').execute('SELECT response FROM canvas_operation_receipts').fetchone()[0])


def fail(*args, **kwargs):
    raise RuntimeError('crash')


@pytest.mark.parametrize('stage', ['readback', 'complete'])
def test_http_postcommit_oserror_explicitly_resumes_same_frozen_operation(tmp_path, monkeypatch, stage):
    from fastapi.testclient import TestClient
    from backend.app.factory import create_app
    from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
    with TestClient(create_app(tmp_path / 'data'), base_url=ORIGIN) as client:
        service = client.app.state.service
        body = payload(service)
        def unavailable(*args, **kwargs):
            raise OSError('injected after native commit')
        with monkeypatch.context() as patch:
            patch.setattr('backend.canvas.operation_readback.verify_plan' if stage == 'readback'
                          else 'backend.canvas.operation_receipts.Receipt.complete', unavailable)
            first = client.post('/api/canvas-plan', headers=HEADERS, json=body)
        assert first.status_code == 409, first.text
        assert first.json()['code'] == 'operation_incomplete'
        assert body['operationId'] in first.json()['hint'] and 'identical POST' in first.json()['hint']
        frozen = intent(service)
        assert service.db_for('draft').execute('SELECT status FROM canvas_operation_receipts').fetchone()[0] == 'pending'
        identifiers = frozen['prepared']['refs']
        assert set(identifiers.values()) <= {node['id'] for node in service.view('draft', 'draft')['graph']['nodes']}
        resumed = client.post('/api/canvas-plan', headers=HEADERS, json=body)
        assert resumed.status_code == 200 and resumed.json()['refs'] == identifiers
        assert client.post('/api/canvas-plan', headers=HEADERS, json=body).json() == resumed.json()
        assert service.texts.read(('draft', 'draft', identifiers['task']))['revision'] == 1


@pytest.mark.parametrize('phase', ['before_write', 'sql_committed', 'complete'])
def test_restart_reuses_frozen_ids_and_revision_once(tmp_path, monkeypatch, phase):
    root = tmp_path / 'data'
    service = CanvasService(root)
    body = payload(service)
    with monkeypatch.context() as patch:
        target = {'before_write': 'backend.canvas.canvas_plan._write',
                  'sql_committed': 'backend.canvas.operation_readback.verify_plan',
                  'complete': 'backend.canvas.operation_receipts.Receipt.complete'}[phase]
        patch.setattr(target, fail)
        with pytest.raises(NextStep, match='incomplete') as failure:
            apply_plan(service, body)
    assert failure.value.code == "operation_incomplete"
    assert body["operationId"] in failure.value.hint and "identical POST" in failure.value.hint
    frozen = intent(service)
    service.close()
    service = CanvasService(root)
    result = apply_plan(service, body)
    assert result['refs'] == frozen['prepared']['refs']
    assert apply_plan(service, body) == result
    node = result['refs']['task']
    assert service.texts.read(('draft', 'draft', node))['revision'] == 1
    assert service.specs.read(('draft', 'draft', node))['revision'] == 1
    service.close()


def test_external_graph_only_resumes_sql_without_graph_rewrite(tmp_path, monkeypatch):
    service = CanvasService(tmp_path / 'data')
    body = payload(service)
    with monkeypatch.context() as patch:
        patch.setattr('backend.canvas.canvas_plan._write', fail)
        with pytest.raises(NextStep, match='incomplete'):
            apply_plan(service, body)
    frozen = intent(service)
    # Emulate the exact graph-file stage surviving an SQL rollback.
    from backend.canvas.canvas_plan_recovery import restore
    built = restore(frozen)
    service.save_graph('draft', 'draft', built.new_graph(), body['digest'])
    with monkeypatch.context() as patch:
        patch.setattr(service, 'save_graph', fail)
        result = apply_plan(service, body)
    assert result['refs'] == frozen['prepared']['refs']
    assert service.texts.read(('draft', 'draft', result['refs']['task']))['revision'] == 1


@pytest.mark.parametrize('change', ['graph', 'mixed_sql', 'same_content_new_revision'])
def test_foreign_or_mixed_state_is_never_overwritten(tmp_path, monkeypatch, change):
    service = CanvasService(tmp_path / 'data')
    body = payload(service)
    with monkeypatch.context() as patch:
        patch.setattr('backend.canvas.canvas_plan._write', fail)
        with pytest.raises(NextStep, match='incomplete'):
            apply_plan(service, body)
    frozen = intent(service)
    from backend.canvas.canvas_plan_recovery import restore
    built = restore(frozen)
    if change == 'graph':
        graph = built.new_graph()
        graph['nodes'][0]['name'] = 'Someone else'
        service.save_graph('draft', 'draft', graph, body['digest'])
    else:
        node = built.refs['task']
        db = service.db_for('draft')
        with db:
            db.execute('INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)',
                       ('draft', 'draft', node, 1, built.texts[node], 'test'))
            if change == 'same_content_new_revision':
                db.execute('INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)',
                           ('draft', 'draft', node, 2, built.texts[node], 'test'))
    before = deepcopy(service.view('draft', 'draft'))
    with pytest.raises(NextStep, match='diverged'):
        apply_plan(service, body)
    after = service.view('draft', 'draft')
    assert after['graph'] == before['graph'] and after['digest'] == before['digest']
    assert intent(service) == frozen


def test_legacy_pending_remains_explicitly_unrecoverable(tmp_path):
    service = CanvasService(tmp_path / 'data')
    body = payload(service)
    with service.db_for('draft') as db:
        Receipt(body, 'canvas-plan', {'kind': 'system'}).begin(db, {'prepared': {'refs': {}}, 'baseDigest': body['digest']})
    with pytest.raises(NextStep, match='no safely recoverable'):
        apply_plan(service, body)


def test_partial_repin_commit_resumes_remaining_candidate_once(sparse, monkeypatch):
    import backend.canvas.opora_execution_repin as module
    graphs, authority, refs = sparse
    first = claimed(sparse)
    second = claimed(sparse, node='b', request='second')
    service = graphs.service
    body = {**payload(service), 'plan': {'nodes': [
        {'ref': 'one', 'kind': 'node', 'name': 'One', 'parent': '@' + refs['a']},
        {'ref': 'two', 'kind': 'node', 'name': 'Two', 'parent': '@' + refs['b']}]}}
    native = module.repin

    def crash_after_one(*args, **kwargs):
        assert native(*args, **kwargs) is True
        raise RuntimeError('after one committed pin')

    with monkeypatch.context() as patch:
        patch.setattr(module, 'repin', crash_after_one)
        with pytest.raises(NextStep, match='incomplete'):
            apply_plan(service, body, actor='agent', repin_owner='agent:worker')
    pending = intent(service)
    assert [c['outcome'] for c in pending['repins']].count('repinned') == 1
    result = apply_plan(service, body, actor='agent', repin_owner='agent:worker')
    assert set(result['rePinned']) == {first['executionId'], second['executionId']}
    for record in (first, second):
        stored = json.loads(service.db_for('draft').execute('SELECT record FROM opora_executions WHERE id=?',
                                                           (record['executionId'],)).fetchone()[0])
        assert stored['contextRepins'] == 1
