"""Native fragment references pin observed research without claiming completed/verified work."""
from copy import deepcopy

import pytest

from backend.api.editor.test_brief_vault_routes import client_with_sector, post as vault
from backend.api.editor.test_research_routes import card, edge, post
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_graph_changes import approve
from backend.canvas.test_opora_executions import credentials
from backend.editor.node.test_removals import SCOPE
from backend.editor.research.test_continuations import imported


def setup(client):
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.canvas.opora_execution_results import ExecutionResults
    from backend.canvas.test_opora_graph_proposals import accept, proposal
    _, result, _ = imported(client, extra_operations=[card('finding'), card('unrelated', kind='question'),
        edge(id='evidence-link', fromId='finding', toId='rc_login', evidenceIds=['finding'])])
    graphs = OporaGraphProposals(client.app.state.service)
    baseline = proposal(graphs, plan={'nodes': [{'ref': 'a', 'kind': 'node', 'name': 'Affected'},
                                               {'ref': 'b', 'kind': 'node', 'name': 'Unrelated'}]})
    accept(graphs, baseline)
    # No continuation researchSource on either task: fragmentRef alone must carry the proof.
    return (graphs, ExecutionResults(graphs.service), baseline['refs']), result


def fragment_plan(client, sparse, source, *, status='assigned', round=2):
    graphs, authority, refs = sparse
    response = vault(client, op='research-update', fragmentId=source['sourceFragmentId'],
                     expectedRevision=source['sourceRevision'], status=status, round=round,
                     approach='Historic result, not freshly verified', note='Prepare explicit research status')
    assert response.status_code == 200, response.text
    fragment = response.json()['fragment']
    context = graphs.context(**SCOPE)
    return {**SCOPE, 'parentRevision': context['acceptedHead'], 'expectedGraphDigest': context['graphDigest'],
            'subject': 'Explicit source-bound task clarification', 'plan': {'draftVersion': 3, 'extend': [{
                'node': '@' + refs['a'], 'expectedRevision': context['stateRevision'],
                'fragmentRef': {'fragmentId': fragment['id'], 'revision': fragment['revision']},
                'text': {'expectedRevision': 0, 'text': 'Verification work based on original research; not an approval.'}}]}}, fragment


@pytest.mark.parametrize('status,round', [('assigned', 2), ('done', 1)])
@pytest.mark.parametrize('change', ['output', 'output_aba', 'map'])
def test_explicit_fragment_pins_real_status_output_and_map_without_promoting_validity(tmp_path, status, round, change):
    with client_with_sector(tmp_path) as client:
        sparse, imported = setup(client)
        graphs, authority, refs = sparse
        request, source = fragment_plan(client, sparse, imported['continuation'], status=status, round=round)
        proposal = graphs.create(request, {'kind': 'agent', 'name': 'heart'})
        pins = deepcopy(proposal['contentInputs']['researchEvidenceByNode'])
        pin = pins[refs['a']][0]
        assert (pin['runStatus'], pin['round'], pin['assessment']) == (status, round, 'observed-unverified')
        assert pin['sourceEvidenceCount'] == 0  # done is not evidence verification
        assert {p['id'] for p in pin['evidence']['items']} == {'rc_login', 'finding', 'evidence-link'}
        assert pin['evidence']['mappedQuestions'] == [{'id': 'rc_login', 'revision': 1}]
        assert pin['evidence']['originalOutput']['detailsRevision'] == pin['detailsRevision']
        approve(OporaGraphChanges(authority.canvas), proposal)
        affected, unrelated = claimed(sparse), claimed(sparse, node='b', request='unrelated')
        frozen = deepcopy(affected['assignment'])
        assert any(r['source'].get('assessment') == 'observed-unverified' for r in frozen['researchEvidence']['records'])
        assert unrelated['assignment']['researchEvidence']['records'] == []
        if change == 'map':
            assert post(client, [card('finding', expectedRevision=1, content='Changed map')], 'changed-map').status_code == 200
        else:
            changed = vault(client, op='research-update', fragmentId=source['id'], expectedRevision=source['revision'],
                            approach='Changed original output only', note='New output')
            assert changed.status_code == 200, changed.text
            if change == 'output_aba':
                assert vault(client, op='research-update', fragmentId=source['id'],
                             expectedRevision=changed.json()['fragment']['revision'],
                             approach='Historic result, not freshly verified', note='Restored').status_code == 200
        with pytest.raises(ValueError, match='research output changed|Research evidence changed'):
            authority.heartbeat(affected['executionId'], {**credentials(affected), 'ttlSeconds': 60})
        assert authority.heartbeat(unrelated['executionId'], {**credentials(unrelated), 'ttlSeconds': 60})['state'] == 'running'
        assert authority.read_assignment(affected['executionId'], 'draft', 'draft', affected['token'])['assignment'] == frozen
        assert graphs.read('draft', 'draft', proposal['id'])['contentInputs']['researchEvidenceByNode'] == pins


@pytest.mark.parametrize('change', ['source', 'mapped_finding'])
def test_changed_source_or_map_cannot_be_accepted_as_current_proof(tmp_path, change):
    with client_with_sector(tmp_path) as client:
        sparse, imported = setup(client)
        graphs, authority, _ = sparse
        request, source = fragment_plan(client, sparse, imported['continuation'])
        proposal = graphs.create(request, {'kind': 'agent', 'name': 'heart'})
        if change == 'source':
            assert vault(client, op='research-update', fragmentId=source['id'], expectedRevision=source['revision'],
                         approach='Changed output', note='Update').status_code == 200
        else:
            assert post(client, [card('finding', expectedRevision=1, content='Changed map evidence')], 'new-finding').status_code == 200
        with pytest.raises(ValueError, match='research|Research|fragment|inputs changed'):
            approve(OporaGraphChanges(authority.canvas), proposal)
        assert graphs.read('draft', 'draft', proposal['id'])['accepted'] is False


def test_old_proposal_keeps_explicit_untracked_fragment_coverage(tmp_path, monkeypatch):
    import backend.canvas.opora_graph_complete as complete
    with client_with_sector(tmp_path) as client:
        sparse, imported = setup(client)
        graphs, authority, _ = sparse
        request, _ = fragment_plan(client, sparse, imported['continuation'])
        original = complete.observe
        with monkeypatch.context() as patch:
            patch.setattr(complete, 'observe', lambda *a, **kw: original(*a, track_research=False))
            legacy = graphs.create(request, {'kind': 'agent', 'name': 'heart'})
        assert 'researchEvidenceByNode' not in legacy['contentInputs']
        approve(OporaGraphChanges(authority.canvas), legacy)
        record = claimed(sparse)
        assert record['assignment']['researchEvidence']['legacyFragments'][0]['coverage'] == 'legacy-fragment-reference-untracked'
        assert 'researchEvidenceByNode' not in graphs.read('draft', 'draft', legacy['id'])['contentInputs']


def test_new_explicit_source_review_supersedes_older_continuation_only_for_target(tmp_path):
    from backend.editor.research.test_execution_evidence import setup as continuation_setup
    with client_with_sector(tmp_path) as client:
        sparse, imported = continuation_setup(client)
        graphs, authority, refs = sparse
        assert post(client, [card('finding', expectedRevision=1, content='New assessed source')], 'reviewed-change').status_code == 200
        request, _ = fragment_plan(client, sparse, imported['continuation'])
        proposal = graphs.create(request, {'kind': 'agent', 'name': 'heart'})
        approve(OporaGraphChanges(authority.canvas), proposal)
        current = claimed(sparse)
        records = current['assignment']['researchEvidence']['records']
        assert len(records) == 1 and records[0]['proposalId'] == proposal['id']
        assert records[0]['nodeIds'] == [refs['a']]
        assert next(p for p in records[0]['evidence']['items'] if p['id'] == 'finding')['revision'] == 2


def test_adding_another_reference_does_not_refresh_existing_source_pins(tmp_path):
    with client_with_sector(tmp_path) as client:
        sparse, imported = setup(client)
        graphs, authority, refs = sparse
        request, source = fragment_plan(client, sparse, imported['continuation'])
        first = graphs.create(request, {'kind': 'agent', 'name': 'heart'})
        approve(OporaGraphChanges(authority.canvas), first)
        made = vault(client, op='research', fragmentId=source['id'], title='Independent research',
                     text='Another input', question='Another question?', status='assigned')
        assert made.status_code == 200, made.text
        other = made.json()['fragment']
        context = graphs.context(**SCOPE)
        request.update(parentRevision=context['acceptedHead'], expectedGraphDigest=context['graphDigest'])
        extension = request['plan']['extend'][0]
        extension.update(expectedRevision=context['stateRevision'], fragmentRef={'fragmentId':other['id'], 'revision':other['revision']})
        extension['text'] = {'expectedRevision': 1, 'text': 'Additional independent input'}
        later = graphs.create(request, {'kind': 'agent', 'name': 'heart'})
        observed = later['contentInputs']['researchEvidenceByNode'][refs['a']]
        assert [pin['sourceId'] for pin in observed] == [other['id']]
        approve(OporaGraphChanges(authority.canvas), later)
        records = claimed(sparse)['assignment']['researchEvidence']['records']
        assert {r['proposalId'] for r in records} == {first['id'], later['id']}
        assert next(r for r in records if r['proposalId'] == first['id'])['evidence'] == first['contentInputs']['researchEvidenceByNode'][refs['a']][0]['evidence']
