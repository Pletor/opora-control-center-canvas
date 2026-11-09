"""Manual research maps need no synthetic question to protect source-bound work."""
import pytest

from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, edge, post
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_graph_changes import approve
from backend.canvas.test_opora_executions import credentials
from backend.editor.research.test_fragment_evidence import setup, fragment_plan


@pytest.mark.parametrize('change', ['finding', 'archive', 'archive_aba', 'edge'])
def test_direct_finding_decision_source_pins_without_question_target_only(tmp_path, change):
    with client_with_sector(tmp_path) as client:
        sparse, imported = setup(client)
        graphs, authority, refs = sparse
        source = imported['continuation']['sourceFragmentId']
        # Remove the importer question's original link: actual manual M3 findings have no questionIds.
        assert post(client, [card('rc_login', kind='question', expectedRevision=1)], 'unlink-question').status_code == 200
        finding = card('manual-finding')
        decision = card('manual-decision', kind='decision')
        foreign = card('foreign-finding')
        finding['refs']['fragmentIds'] = decision['refs']['fragmentIds'] = [source]
        foreign['refs']['fragmentIds'] = ['a-different-original']
        assert finding['refs']['questionIds'] == decision['refs']['questionIds'] == []
        direct_edge = edge(id='manual-link', fromId='manual-finding', toId='manual-decision', evidenceIds=['manual-finding'])
        boundary = edge(id='foreign-link', fromId='manual-decision', toId='foreign-finding')
        assert post(client, [finding, decision, foreign, direct_edge, boundary], 'manual-import').status_code == 200
        request, _ = fragment_plan(client, sparse, imported['continuation'])
        proposal = graphs.create(request, {'kind': 'agent', 'name': 'heart'})
        evidence = proposal['contentInputs']['researchEvidenceByNode'][refs['a']][0]['evidence']
        assert evidence['mappedQuestions'] == []
        assert {item['id'] for item in evidence['items']} == {'manual-finding', 'manual-decision', 'manual-link'}
        approve(OporaGraphChanges(authority.canvas), proposal)
        affected = claimed(sparse)
        unrelated = claimed(sparse, node='b', request='unrelated')
        # A source-specific boundary must not pick up the linked foreign original.
        assert post(client, [{**foreign, 'expectedRevision': 1, 'content': 'Foreign edit'}], 'foreign-edit').status_code == 200
        authority.heartbeat(affected['executionId'], {**credentials(affected), 'ttlSeconds': 60})
        if change == 'finding':
            operations = [{**finding, 'expectedRevision': 1, 'content': 'Changed source finding'}]
        elif change == 'edge':
            operations = [{**direct_edge, 'expectedRevision': 1, 'reason': 'Different evidence relation'}]
        else:
            operations = [{'op': 'archive', 'entity': 'card', 'id': 'manual-decision', 'expectedRevision': 1, 'archived': True}]
        assert post(client, operations, 'source-edit').status_code == 200
        if change == 'archive_aba':
            assert post(client, [{'op': 'archive', 'entity': 'card', 'id': 'manual-decision', 'expectedRevision': 2,
                                  'archived': False}], 'source-restore').status_code == 200
        with pytest.raises(ValueError, match='Research evidence changed'):
            authority.heartbeat(affected['executionId'], {**credentials(affected), 'ttlSeconds': 60})
        assert authority.heartbeat(unrelated['executionId'], {**credentials(unrelated), 'ttlSeconds': 60})['state'] == 'running'
        assert graphs.read('draft', 'draft', proposal['id'])['contentInputs']['researchEvidenceByNode'][refs['a']][0]['evidence'] == evidence
