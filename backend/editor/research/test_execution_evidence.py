"""Research changes revoke only scoped evidence; accepted/native history stays immutable."""
import copy

import pytest

from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, edge, post
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_execution_context import claimed, prepared
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_graph_changes import approve
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.editor.node.test_removals import SCOPE
from backend.editor.research.planning_source import pins
from backend.editor.research.test_continuations import imported


def setup(client, finalization=None):
    operations = [card('finding'), card('unrelated', kind='question'),
                  edge(id='evidence-link', fromId='finding', toId='rc_login', evidenceIds=['finding'])]
    _, result, source = imported(client, extra_operations=operations, finalization=finalization)
    service = client.app.state.service
    if finalization is not None:
        from backend.api.editor.test_brief_vault_routes import post as vault
        from backend.editor.research.continuations import wakes
        vault(client, op='research-update', fragmentId=source['id'], expectedRevision=source['revision'],
              note='Completed test research', **finalization)
        assert wakes(service, 'draft', 0)
    graphs = OporaGraphProposals(service)
    other = proposal(graphs, plan={'nodes': [{'ref': 'b', 'kind': 'node', 'name': 'Unrelated task'}]})
    accept(graphs, other)
    context = graphs.context(**SCOPE)
    made = graphs.create({**SCOPE, 'parentRevision': context['acceptedHead'],
        'expectedGraphDigest': context['graphDigest'], 'subject': 'Research implementation',
        'plan': {'draftVersion': 3, 'researchSource': pins(result['continuation']),
                 'nodes': [{'ref': 'a', 'kind': 'node', 'name': 'Affected task'}]}},
        {'kind': 'agent', 'name': 'heart'})
    approve(OporaGraphChanges(service), made)  # Explicit isolated fixture human acceptance.
    return (graphs, ExecutionResults(service), {**made['refs'], **other['refs']}), result


@pytest.mark.parametrize('change', ['finding', 'question', 'edge', 'archive_aba'])
def test_changed_evidence_revokes_affected_only_and_preserves_assignment(tmp_path, change):
    with client_with_sector(tmp_path) as client:
        sparse, result = setup(client)
        _, authority, _ = sparse
        affected = claimed(sparse)
        unrelated = claimed(sparse, node='b', request='other')
        original = copy.deepcopy(affected['assignment'])
        evidence = original['researchEvidence']['records'][0]['evidence']
        assert {item['id'] for item in evidence['items']} == {'rc_login', 'finding', 'evidence-link'}
        assert unrelated['assignment']['researchEvidence']['records'] == []
        if change == 'archive_aba':
            assert post(client, [{'op': 'archive', 'entity': 'card', 'id': 'finding',
                                 'expectedRevision': 1, 'archived': True}], 'archive').status_code == 200
            assert post(client, [{'op': 'archive', 'entity': 'card', 'id': 'finding',
                                 'expectedRevision': 2, 'archived': False}], 'restore').status_code == 200
        elif change == 'edge':
            assert post(client, [edge(id='evidence-link', fromId='finding', toId='rc_login',
                                     evidenceIds=['finding'], expectedRevision=1, reason='Changed')], 'changed').status_code == 200
        else:
            key = 'finding' if change == 'finding' else 'rc_login'
            current = next(item for item in result['cards'] if item['id'] == key)
            from backend.editor.research.model import CARD
            revised = {name: current[name] for name in CARD}
            assert post(client, [{**revised, 'op': 'card', 'id': key, 'expectedRevision': 1,
                                  'content': 'Changed premise'}], 'changed').status_code == 200
        with pytest.raises(ValueError, match='Research evidence changed'):
            authority.heartbeat(affected['executionId'], {**credentials(affected), 'ttlSeconds': 60})
        assert authority.heartbeat(unrelated['executionId'], {**credentials(unrelated), 'ttlSeconds': 60})['state'] == 'running'
        assert authority.read_assignment(affected['executionId'], 'draft', 'draft', affected['token'])['assignment'] == original
        before = authority.canvas.db_for('draft').execute('SELECT COUNT(*) FROM opora_executions').fetchone()[0]
        with pytest.raises(ValueError, match='Research evidence changed'):
            prepared(sparse)
        assert authority.canvas.db_for('draft').execute('SELECT COUNT(*) FROM opora_executions').fetchone()[0] == before


def test_unrelated_research_edit_keeps_assignment_and_reopened_authority(tmp_path):
    with client_with_sector(tmp_path) as client:
        sparse, _ = setup(client)
        _, authority, _ = sparse
        record = claimed(sparse)
        assert post(client, [card('unrelated', kind='question', expectedRevision=1, content='Elsewhere')], 'elsewhere').status_code == 200
        from backend.canvas.canvas_service import CanvasService
        root = authority.canvas.root
        authority.canvas.close()
        reopened = CanvasService(root)
        try:
            current = ExecutionResults(reopened).heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})
            assert current['assignment'] == record['assignment']
        finally:
            reopened.close()


def test_closed_unrelated_result_keeps_scoped_verification_across_head_advance(tmp_path):
    from backend.canvas.opora_agent_state import AgentState
    with client_with_sector(tmp_path) as client:
        sparse, _ = setup(client)
        graphs, authority, refs = sparse
        record = claimed(sparse, node='b')
        authority.submit(record['executionId'], {**credentials(record), 'requestId': 'done', 'result': {'summary': 'Done'}})
        later = accept(graphs, proposal(graphs, 'Other work'))
        rows = AgentState(authority.canvas).executions(authority.canvas.db_for('draft'), 'draft', 'draft',
                                                           accepted=later['id'], closed={refs['b']})
        assert next(row for row in rows if row['id'] == record['executionId'])['staleEvidence'] is False


def test_long_accepted_history_without_research_has_no_new_limit(tmp_path):
    from backend.editor.research.execution_evidence import collect
    from database.repositories.opora_changesets import ChangesetRepository
    with client_with_sector(tmp_path) as client:
        db = client.app.state.service.db_for('draft')
        repo = ChangesetRepository(db, 'draft', 'draft')
        head = None
        with db:
            db.execute('BEGIN IMMEDIATE')
            for number in range(260):
                record = repo.insert({**SCOPE, 'kind': 'baseline' if head is None else 'acceptance',
                    'parentRevision': head, 'proposalId': None if head is None else f'{number:040x}',
                    'createdAt': str(number), 'documents': []})
                head = record['id']
        assert collect(db, 'draft', 'draft', head, [])['records'] == []


def test_legacy_private_pin_retains_legacy_coverage_without_backfill(sparse, monkeypatch):
    from backend.canvas import opora_execution_context as context
    from backend.canvas.graph import digest
    native_collect, native_token = context.collect, context.token

    def old_token(secret, projection, accepted, binding):
        return native_token(secret, {key: value for key, value in projection.items() if key != 'researchEvidence'}, accepted, binding)

    def old_collect(*args):
        assignment, pin = native_collect(*args)
        assignment.pop('researchEvidence')
        pin['assignmentDigest'] = digest(assignment)
        return assignment, pin

    with monkeypatch.context() as old:
        old.setattr(context, 'token', old_token)
        old.setattr(context, 'collect', old_collect)
        record = claimed(sparse)
    _, authority, _ = sparse
    current = authority.heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})
    assert current['assignment'] == record['assignment']
    assert 'researchEvidence' not in current['assignment']
    assert current['researchEvidenceCoverage'] == 'legacy-untracked'
    from backend.canvas.opora_execution_repin import repin
    assert repin(authority, 'draft', 'draft', record['executionId']) is True
    legacy = authority.heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})
    assert 'researchEvidence' not in legacy['assignment']
    assert legacy['researchEvidenceCoverage'] == 'legacy-untracked'


def test_repin_preserves_frozen_research_and_refuses_stale_evidence(tmp_path):
    from backend.canvas.opora_execution_repin import repin
    with client_with_sector(tmp_path) as client:
        sparse, _ = setup(client)
        _, authority, _ = sparse
        record = claimed(sparse)
        frozen = copy.deepcopy(record['assignment']['researchEvidence'])
        assert repin(authority, 'draft', 'draft', record['executionId']) is True
        current = authority.heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})
        assert current['assignment']['researchEvidence'] == frozen
        assert current['contextRepins'] == 1
        assert post(client, [card('finding', expectedRevision=1, content='Changed premise')], 'repin-stale').status_code == 200
        assert repin(authority, 'draft', 'draft', record['executionId']) is False
        unchanged = authority.read_assignment(record['executionId'], 'draft', 'draft', record['token'])
        assert unchanged['assignment'] == current['assignment']
        with pytest.raises(ValueError, match='Research evidence changed'):
            authority.heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})


def test_existing_finding_is_pinned_but_foreign_question_edge_is_boundary(tmp_path):
    with client_with_sector(tmp_path) as client:
        assert post(client, [card('existing'), card('foreign-evidence')], 'existing').status_code == 200
        operations = [card('other-question', kind='question'),
                      edge(id='existing-link', fromId='existing', toId='rc_login', evidenceIds=['existing']),
                      edge(id='boundary', fromId='existing', toId='other-question', evidenceIds=['foreign-evidence'])]
        _, result, _ = imported(client, extra_operations=operations)
        evidence = result['continuation']['evidence']
        assert {item['id'] for item in evidence['items']} == {'rc_login', 'existing', 'existing-link'}
        assert post(client, [card('existing', expectedRevision=1, content='Different')], 'different').status_code == 200
        from backend.editor.research.planning_source import validate_source
        from backend.editor.research.model import GateError
        with pytest.raises(GateError, match='Research evidence changed'):
            validate_source(client.app.state.service, 'draft', 'draft', pins(result['continuation']))


@pytest.mark.parametrize('input_change', ['question', 'text'])
def test_original_completion_output_is_not_input_change_but_question_aba_is(tmp_path, input_change):
    from backend.api.editor.test_brief_vault_routes import post as vault
    with client_with_sector(tmp_path) as client:
        sparse, result = setup(client)
        _, authority, _ = sparse
        record = claimed(sparse)
        source = result['continuation']
        updated = vault(client, op='research-update', fragmentId=source['sourceFragmentId'],
                        expectedRevision=source['sourceRevision'], note='Research completed', status='done',
                        approach='Completed output, not a changed input').json()['fragment']
        assert authority.heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})['state'] == 'running'
        if input_change == 'text':
            changed = vault(client, op='revise', fragmentId=updated['id'], expectedRevision=updated['revision'],
                            note='Changed input', text='Different input text').json()['fragment']
            vault(client, op='revise', fragmentId=changed['id'], expectedRevision=changed['revision'],
                  note='Restore input', text='Original question')
        else:
            changed = vault(client, op='research-update', fragmentId=updated['id'], expectedRevision=updated['revision'],
                            note='Changed input', question='A different research question').json()['fragment']
            vault(client, op='research-update', fragmentId=changed['id'], expectedRevision=changed['revision'],
                  note='Restore input', question='Versioned vectors?')
        with pytest.raises(ValueError, match='Original research input changed'):
            authority.heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})


def test_new_v1_claim_cannot_bypass_research_pins_but_unrelated_claim_can(tmp_path):
    from backend.canvas.test_opora_executions import claim
    with client_with_sector(tmp_path) as client:
        sparse, _ = setup(client)
        _, authority, refs = sparse
        with pytest.raises(ValueError, match='prepared contextProtocolVersion 2'):
            claim(authority, node=refs['a'])
        assert authority.canvas.db_for('draft').execute('SELECT COUNT(*) FROM opora_executions').fetchone()[0] == 0
        assert claim(authority, node=refs['b'])['nodeId'] == refs['b']
        assert claimed(sparse, request='prepared')['contextProtocolVersion'] == 2


def test_initial_draft_retains_research_provenance_after_native_acceptance(tmp_path):
    from backend.canvas.canvas_plan import apply_plan
    with client_with_sector(tmp_path) as client:
        _, result, _ = imported(client, accepted_context=False, extra_operations=[
            card('finding'), edge(id='evidence-link', fromId='finding', toId='rc_login', evidenceIds=['finding'])])
        service = client.app.state.service
        made = apply_plan(service, {**SCOPE, 'digest': service.view('draft', 'draft')['digest'],
            'operationId': result['continuation']['operationId'], 'researchSource': pins(result['continuation']),
            'plan': {'nodes': [{'ref': 'a', 'kind': 'node', 'name': 'Initial task'}]}},
            actor='agent', operation_actor={'kind': 'agent', 'name': 'heart'})
        graphs = OporaGraphProposals(service)
        accepted = proposal(graphs, plan={'nodes': [{'ref': 'b', 'kind': 'node', 'name': 'Other task'}]})
        accept(graphs, accepted)  # Explicit isolated human baseline adoption.
        sparse = (graphs, ExecutionResults(service), {**made['refs'], **accepted['refs']})
        record = claimed(sparse)
        assert record['assignment']['researchEvidence']['records'][0]['operationId'] == result['continuation']['operationId']
        assert claimed(sparse, node='b', request='other')['assignment']['researchEvidence']['records'] == []
        assert post(client, [card('finding', expectedRevision=1, content='Changed')], 'change').status_code == 200
        with pytest.raises(ValueError, match='Research evidence changed'):
            sparse[1].heartbeat(record['executionId'], {**credentials(record), 'ttlSeconds': 60})


def test_pending_proposal_cannot_be_accepted_after_finding_changed(tmp_path):
    with client_with_sector(tmp_path) as client:
        sparse, result = setup(client)
        graphs, _, _ = sparse
        context = graphs.context(**SCOPE)
        pending = graphs.create({**SCOPE, 'parentRevision': context['acceptedHead'],
            'expectedGraphDigest': context['graphDigest'], 'subject': 'Pending work',
            'plan': {'draftVersion': 3, 'researchSource': pins(result['continuation']),
                     'nodes': [{'ref': 'pending', 'kind': 'node', 'name': 'Pending task'}]}},
            {'kind': 'agent', 'name': 'heart'})
        assert post(client, [card('finding', expectedRevision=1, content='Changed')], 'changed').status_code == 200
        with pytest.raises(ValueError, match='Research evidence changed'):
            approve(OporaGraphChanges(graphs.service), pending)
        assert graphs.context(**SCOPE)['acceptedHead'] == context['acceptedHead']


def test_closed_affected_result_needs_reassessment_without_resetting_other_result(tmp_path):
    from backend.canvas.opora_agent_state import AgentState
    with client_with_sector(tmp_path) as client:
        sparse, _ = setup(client)
        graphs, authority, refs = sparse
        records = [claimed(sparse, node=key, request=key) for key in ('a', 'b')]
        for record in records:
            authority.submit(record['executionId'], {**credentials(record), 'requestId': record['nodeId'],
                                                     'result': {'summary': 'Done'}})
        assert post(client, [card('finding', expectedRevision=1, content='Changed')], 'changed').status_code == 200
        rows = AgentState(authority.canvas).executions(authority.canvas.db_for('draft'), 'draft', 'draft',
            accepted=graphs.context(**SCOPE)['acceptedHead'], closed=set(refs.values()))
        by_node = {row['nodeId']: row for row in rows}
        assert by_node[refs['a']]['staleEvidence'] is True
        assert by_node[refs['b']]['staleEvidence'] is False
        assert by_node[refs['a']]['results'] == by_node[refs['b']]['results'] == 1
