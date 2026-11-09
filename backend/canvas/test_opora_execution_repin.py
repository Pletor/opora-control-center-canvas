"""Re-pin po vlastní dávce plánu: nový neměnný pin, původní zůstává; bez živého běhu dávka beze změny."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_execution_start_deliver import AGENT, ready, start
from backend.app.test_local_merge_autonomy import ok
from backend.canvas.opora_execution_repin import plan_with_repin
from backend.canvas.test_canvas_plan import ORIGIN
from database.repositories import opora_execution_contexts as private
import pytest


def test_without_live_executions_the_plan_is_untouched(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _, scope, _ = ready(client, tmp_path)
        canvas = client.app.state.service
        assert plan_with_repin(canvas, {**scope}, "agent:nikdo", lambda: {"ok": 1}) == {"ok": 1}
        assert plan_with_repin(canvas, {**scope, "dryRun": True}, "agent:t", lambda: {"ok": 2}) == {"ok": 2}


@pytest.mark.parametrize('durable', [False, True])
def test_repin_adds_a_new_pin_and_keeps_the_origin(tmp_path, durable):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        identifier = started["executionId"]
        digest = ok(client.get("/api/view", params=scope))["digest"]
        plan = {"nodes": [{"ref": "pod", "kind": "node", "parent": "@" + card, "name": "Podkarta"}],
                "edges": [], "decisions": []}
        assert ok(client.post("/api/canvas-plan", headers=AGENT,
                              json={**scope, "digest": digest, "plan": plan,
                                    **({'operationId': 'http-repin'} if durable else {})}))["rePinned"] == [identifier]
        db = client.app.state.service.db_for(scope["project"])
        with db:
            db.execute("BEGIN")
            origin = private.read(db, scope["project"], scope["workspace"], identifier)
            fresh = private.read(db, scope["project"], scope["workspace"], identifier + ":repin1")
        assert origin["contextVersion"] == started["contextVersion"] != fresh["contextVersion"]
        record = ok(client.get("/api/oporahub/executions", params={**scope, "nodeId": card}, headers=AGENT))["executions"][0]
        assert record["contextRepins"] == 1 and record["state"] == "running", record


@pytest.mark.parametrize('phase', ['before_repin', 'after_repin', 'expired_lease', 'changed_assignment'])
def test_durable_plan_repin_replays_exact_outcome_without_enrolling_new_candidates(tmp_path, monkeypatch, phase):
    from backend.canvas.canvas_plan import apply_plan
    from backend.canvas.operation_receipts import Receipt
    from backend.canvas.payload_errors import NextStep
    from backend.canvas.canvas_service import CanvasService
    import backend.canvas.opora_execution_repin as module
    with TestClient(create_app(tmp_path / 'data'), base_url=ORIGIN) as client:
        _, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        canvas = client.app.state.service
        db = canvas.db_for(scope['project'])
        import json
        record = json.loads(db.execute('SELECT record FROM opora_executions WHERE id=?', (started['executionId'],)).fetchone()[0])
        owner = db.execute('SELECT owner FROM opora_executions WHERE id=?', (started['executionId'],)).fetchone()[0]
        body = {**scope, 'operationId': 'durable-repin', 'digest': canvas.view(scope['project'], scope['workspace'])['digest'],
                'plan': {'nodes': [{'ref': 'child', 'kind': 'node', 'parent': '@' + card, 'name': 'Child'}]}}

        def crash(*args, **kwargs):
            raise RuntimeError('crash')

        with monkeypatch.context() as patch:
            patch.setattr(Receipt if phase == 'after_repin' else module,
                          'complete' if phase == 'after_repin' else 'finish_candidates', crash)
            with pytest.raises(NextStep, match='durable-repin.*incomplete') as failure:
                apply_plan(canvas, body, actor='agent', repin_owner=owner)
        assert failure.value.code == 'operation_incomplete'
        assert 'durable-repin' in failure.value.hint and 'identical POST' in failure.value.hint
        assert isinstance(failure.value.__cause__, RuntimeError)
        assert db.execute('SELECT status FROM canvas_operation_receipts').fetchone()[0] == 'pending'
        saved_graph = canvas.view(scope['project'], scope['workspace'])['graph']
        child = next(node for node in saved_graph['nodes'] if node['name'] == 'Child')
        assert sum(node['name'] == 'Child' for node in saved_graph['nodes']) == 1
        # Reconstruct the native service from disk: pending outcome is durable, not an in-memory retry.
        canvas.close()
        canvas = CanvasService(tmp_path / 'data')
        db = canvas.db_for(scope['project'])
        if phase in ('expired_lease', 'changed_assignment'):
            with db:
                if phase == 'expired_lease':
                    db.execute('UPDATE card_leases SET expires_at=0 WHERE node_id=?', (card,))
                else:
                    revised = {**record, 'assignmentDigest': 'changed'}
                    db.execute('UPDATE opora_executions SET record=? WHERE id=?', (json.dumps(revised), started['executionId']))
            with pytest.raises(NextStep, match='Original execution'):
                apply_plan(canvas, body, actor='agent', repin_owner=owner)
            assert db.execute('SELECT status FROM canvas_operation_receipts').fetchone()[0] == 'pending'
            current = json.loads(db.execute('SELECT record FROM opora_executions WHERE id=?', (started['executionId'],)).fetchone()[0])
            assert current.get('contextRepins', 0) == 0
            assert canvas.view(scope['project'], scope['workspace'])['graph'] == saved_graph
            canvas.close()
            return
        with monkeypatch.context() as patch:
            patch.setattr(module, 'freeze_candidates', crash)  # retry cannot enroll a newly started execution
            result = apply_plan(canvas, body, actor='agent', repin_owner=owner)
        assert result['rePinned'] == [started['executionId']]
        assert apply_plan(canvas, body, actor='agent', repin_owner=owner) == result
        current = json.loads(db.execute('SELECT record FROM opora_executions WHERE id=?', (started['executionId'],)).fetchone()[0])
        assert current['contextRepins'] == 1
        assert current['assignment']['researchEvidence'] == record['assignment']['researchEvidence']
        assert result['refs']['child'] == child['id']
        assert canvas.view(scope['project'], scope['workspace'])['graph'] == saved_graph
        assert private.read(db, scope['project'], scope['workspace'], started['executionId'])['contextVersion'] == started['contextVersion']
        canvas.close()
