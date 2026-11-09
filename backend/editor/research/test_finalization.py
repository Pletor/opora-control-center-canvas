"""Native completion observation and direct-original output invalidation without another queue."""
import copy

import pytest

from backend.api.editor.test_brief_vault_routes import client_with_sector, post as vault
from backend.canvas.canvas_service import CanvasService
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_executions import credentials
from backend.editor.node.test_removals import HEADERS, SCOPE
from backend.editor.research import continuations
from backend.editor.research.model import GateError
from backend.editor.research.planning_source import pins, validate_source
from backend.editor.research.test_continuations import imported
from backend.editor.research.test_execution_evidence import setup

FIELDS = {'status': 'done', 'verdict': 'unverified', 'confidence': '', 'approach': 'Bounded final result', 'evidence': []}


def finish(client, source, **changes):
    response = vault(client, op='research-update', fragmentId=source['id'], expectedRevision=source['revision'],
                     note='Finalized output', **{**FIELDS, **changes})
    assert response.status_code == 200, response.text
    return response.json()['fragment']


def test_import_waits_for_native_completion_and_restart_observes_lost_response(tmp_path):
    with client_with_sector(tmp_path) as client:
        body, result, source = imported(client, finalization=FIELDS)
        service = client.app.state.service
        assert result['continuation']['status'] == 'awaiting_finalization'
        assert continuations.wakes(service, 'draft', 0) == []
        with pytest.raises(GateError, match='must wait'):
            validate_source(service, 'draft', 'draft', pins(result['continuation']))
        assert client.post('/api/research', headers=HEADERS, json=body).json() == result
        assert continuations.listing(service, 'draft', 'draft')[0]['attempts'] == 0
        finish(client, source)  # Native write succeeded; simulate a crash before any observer/ack call.
        root = service.root
        service.close()
        reopened = CanvasService(root)
        try:
            assert len(continuations.wakes(reopened, 'draft', 1)) == 1
            item = continuations.listing(reopened, 'draft', 'draft')[0]
            assert item['operationId'] == result['continuation']['operationId']
            assert item['evidence']['originalOutput']['detailsRevision'] > item['evidence']['originalInput']['detailsRevision']
            assert item['evidence']['originalSourceCoverage'] == 'semantic-input-and-observed-completed-output'
            validate_source(reopened, 'draft', 'draft', pins(item))
        finally:
            reopened.close()


@pytest.mark.parametrize('restore', [False, True])
def test_direct_original_output_edit_invalidates_only_affected_execution(tmp_path, restore):
    with client_with_sector(tmp_path) as client:
        sparse, result = setup(client, finalization=FIELDS)
        _, authority, _ = sparse
        first, other = claimed(sparse), claimed(sparse, node='b', request='other')
        immutable = copy.deepcopy(first['assignment'])
        identifier = result['continuation']['sourceFragmentId']
        original = client.get('/api/research/originals/' + identifier, params=SCOPE).json()
        changed = finish(client, {'id': identifier, 'revision': original['sourceRevision']}, approach='Changed conclusion')
        if restore:
            finish(client, changed)
        with pytest.raises(ValueError, match='Original research output changed'):
            authority.heartbeat(first['executionId'], {**credentials(first), 'ttlSeconds': 60})
        assert authority.heartbeat(other['executionId'], {**credentials(other), 'ttlSeconds': 60})['state'] == 'running'
        assert authority.read_assignment(first['executionId'], 'draft', 'draft', first['token'])['assignment'] == immutable
        with pytest.raises(GateError, match='Original research output changed'):
            validate_source(authority.canvas, 'draft', 'draft', pins(result['continuation']))


@pytest.mark.parametrize('completed_first', [False, True])
def test_wrong_completion_or_changed_before_observer_never_wakes_planning(tmp_path, completed_first):
    with client_with_sector(tmp_path) as client:
        _, _, source = imported(client, finalization=FIELDS)
        if completed_first:
            source = finish(client, source)
        finish(client, source, approach='Different completion')
        assert continuations.wakes(client.app.state.service, 'draft', 0) == []
        item = continuations.listing(client.app.state.service, 'draft', 'draft')[0]
        assert item['status'] == 'conflict' and item['attempts'] == 0


def test_operational_status_change_after_finalization_does_not_change_output_pin(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, result, source = imported(client, finalization=FIELDS)
        completed = finish(client, source)
        service = client.app.state.service
        assert continuations.wakes(service, 'draft', 0)
        before = continuations.listing(service, 'draft', 'draft')[0]['evidence']['originalOutput']
        vault(client, op='research-update', fragmentId=completed['id'], expectedRevision=completed['revision'],
              note='A new operational round', status='assigned', round=2)
        validate_source(service, 'draft', 'draft', pins(result['continuation']))
        assert continuations.wakes(service, 'draft', 1)
        assert continuations.listing(service, 'draft', 'draft')[0]['evidence']['originalOutput'] == before
