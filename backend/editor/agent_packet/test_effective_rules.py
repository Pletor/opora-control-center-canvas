from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_packet.effective_rules import effective_rules
from backend.editor.agent_packet.test_node_brief import ORIGIN, brief, full_state, save_state, seed_graph


def test_brief_inherits_local_sector_prohibitions_and_names_their_origin(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed_graph(client)
        state = full_state()
        state['nodes']['sektor'] = {'phase': 'discover', 'criteria': [], 'steps': [], 'actions': [],
                                    'rules': [{'id': 'nr1', 'text': 'No external writes', 'kind': 'must_not'}]}
        save_state(client, state)
        data = brief(client).json()
        rows = data['boundaries']['effectiveRules']
        local = next(r for r in rows if r['origin']['nodeId'] == 'sektor')
        assert local['origin'] == {'scope': 'sector', 'nodeId': 'sektor', 'name': 'Sektor', 'path': '', 'storage': 'node'}
        assert local['inherited'] is True
        assert len([r for r in rows if r['id'] == 'nr1']) == 2
        assert any('No external writes' in text for text in data['harness']['stopConditions'])
        assert data['boundaries']['nodeRules'] == state['nodes']['focus']['rules']


def test_rules_follow_exact_path_boundaries_and_ancestor_chain_only():
    graph = {'nodes': [{'id': 's', 'kind': 'sector', 'name': 'S', 'parentId': None},
                       {'id': 'n', 'kind': 'node', 'name': 'N', 'parentId': 's', 'sourceRef': {'path': 'backend/api.py'}}]}
    state = {'nodes': {}, 'rules': [
        {'id': str(i), 'text': 'Rule', 'kind': 'must', 'scope': scope, 'target': target}
        for i, (scope, target) in enumerate([('project', ''), ('path', 'backend'), ('path', 'back'),
                                           ('node', 's'), ('node', 'missing'), ('node', 'n')])
    ]}
    rows = effective_rules(graph, state, 'n')
    assert [r['id'] for r in rows] == ['0', '1', '3', '5']
    assert [r['origin']['scope'] for r in rows] == ['project', 'path', 'sector', 'card']
    assert [r['inherited'] for r in rows] == [True, True, True, False]
