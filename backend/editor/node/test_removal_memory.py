"""Removing a card must not leave its rules and decisions in agent context."""

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.node.test_removal_recovery import remove, restore
from backend.editor.node.test_removals import (
    HEADERS, ORIGIN, SCOPE, desktop_state, install_desktop_state, install_graph, nested_graph,
)


def test_removal_cascades_memory_and_undo_preserves_later_edits(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, nested_graph())
        state = desktop_state()
        state['rules'] = [
            {'id': key, 'text': key, 'kind': 'must', 'scope': scope, 'target': target}
            for key, scope, target in [('global', 'project', ''), ('child-rule', 'node', 'deep'),
                                       ('keep-rule', 'node', 'keep'), ('path-rule', 'path', 'backend')]
        ]
        state['decisions'] = [
            {'id': key, 'text': key, 'pinned': True, 'path': '', 'nodeId': target,
             'createdAt': '2026-10-07T08:00:00+00:00', 'by': 'agent'}
            for key, target in [('global-decision', ''), ('child-decision', 'deep'),
                                ('keep-decision', 'keep')]
        ]
        install_desktop_state(client, state)
        _, removed = remove(client, 'node', 'sector')
        stored = client.get('/api/desktop-v3/state', params=SCOPE).json()
        assert [r['id'] for r in stored['state']['rules']] == ['global', 'keep-rule', 'path-rule']
        assert [d['id'] for d in stored['state']['decisions']] == ['global-decision', 'keep-decision']
        stored['state']['rules'][0]['text'] = 'New global rule'
        response = client.post('/api/desktop-v3/state', headers=HEADERS, json={
            **SCOPE, 'expectedRevision': stored['revision'], 'state': stored['state'],
        })
        assert response.status_code == 200, response.text
        response = restore(client, removed['recoveryId'])
        assert response.status_code == 200, response.text
        restored = client.get('/api/desktop-v3/state', params=SCOPE).json()['state']
        assert {r['id'] for r in restored['rules']} == {r['id'] for r in state['rules']}
        assert next(r for r in restored['rules'] if r['id'] == 'global')['text'] == 'New global rule'
        assert {d['id'] for d in restored['decisions']} == {d['id'] for d in state['decisions']}
