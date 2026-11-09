"""Addressed Desktop reads retain complete stored content and native not-found behavior."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.editor.agent_memory.test_block_access import prepared, HEADERS
from backend.editor.agent_memory.test_memory_items import rule, decision, write


def test_addressed_desktop_matches_native_http_without_state_writes(setup):
    client, service, auth = setup
    prepared(client)
    for kind, value in (('rule', rule('r', 'Full rule')), ('decision', decision('d', 'Full decision'))):
        assert write(client, kind, 'add', None, value).status_code == 200
    saved = client.post('/api/desktop-v3/agent-workspace', headers=HEADERS, json={**SCOPE,
        'nodeId': 'focus', 'expectedRevision': 0, 'sections': {'frame': 'Original frame ' * 200}, 'by': 'agent'})
    assert saved.status_code == 200, saved.text
    before = client.get('/api/desktop-v3/state', params=SCOPE).json()
    for action, path, data in (
        ('read_rule', 'rule', {'id': 'r'}), ('read_decision', 'decision', {'id': 'd'}),
        ('read_trace', 'trace', {'id': 'focus'}), ('read_pipelines', 'pipelines', {}),
        ('read_block', 'block', {'nodeId': 'focus', 'blockId': 'b1'}),
        ('read_agent_workspace', 'agent-workspace', {'nodeId': 'focus'}),
        ('read_agent_workspace_summaries', 'agent-workspace-summaries', {}),
        ('read_frontier', 'frontier', {}),
        ('read_card_checklist', 'card-checklist', {'layer': ''}),
    ):
        actual = call(client, auth, 'desktop_v3_routes.' + action, data)
        expected = client.get('/api/desktop-v3/' + path, params={**SCOPE, **data})
        assert actual.status_code == expected.status_code == 200, actual.text
        assert actual.json()['result'] == expected.json()
        assert call(client, auth, 'desktop_v3_routes.' + action, {**data, 'unknown': True}).status_code == 422
    assert client.get('/api/desktop-v3/state', params=SCOPE).json() == before
    assert call(client, auth, 'desktop_v3_routes.read_block', {'nodeId': 'focus', 'blockId': 'missing'}).status_code == 404
    assert call(client, auth, 'desktop_v3_routes.read_agent_workspace', {'nodeId': 'missing'}).status_code == 404
    assert call(client, auth, 'desktop_v3_routes.read_trace', {'id': 'missing'}).status_code == 404
