from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.brain_opora.determinism import tokens
from backend.canvas.test_graph_source_ref import node, sector, view, post_graph
from backend.project.workspace.test_workspace_sources import attach, ORIGIN
from backend.editor.agent_memory.test_completion_evidence import evidence


def test_realization_uses_real_merge_and_disk_with_exact_replay(setup, tmp_path, monkeypatch):
    client, service, auth = setup
    source = tmp_path / 'source'; source.mkdir()
    pid = attach(client, source)
    scope = {'project': pid, 'workspace': 'draft'}
    _, token = tokens.issue_heart(service, pid, 'draft')
    auth = {**auth, tokens.HEADER: token}
    graph = {'nodes': [sector(), node(source_ref={'origin': 'planned', 'path': 'result.py', 'kind': 'file'})], 'edges': []}
    assert post_graph(client, pid, graph, view(client, pid)['digest']).status_code == 200
    data = {'nodeId': 'node-1', 'digest': view(client, pid)['digest'], 'commit': 'abc1234', 'prUrl': 'https://git.example/pr/1'}
    op = 'desktop_v3_routes.write_source_realization'
    assert call(client, auth, op, data, 'realize', scope).status_code == 409
    stored = client.get('/api/desktop-v3/state', params=scope).json()
    proof = evidence(); proof['merge'] = {'status': 'passed', 'url': data['prUrl'], 'note': 'Merged'}
    stored['state']['nodes']['node-1'] = {'phase': 'discover', 'criteria': [], 'steps': [], 'evidence': proof}
    assert client.post('/api/desktop-v3/state', headers={'origin': ORIGIN}, json={**scope,
        'expectedRevision': stored['revision'], 'state': stored['state']}).status_code == 200
    assert call(client, auth, op, data, 'realize', scope).status_code == 409
    (source / 'result.py').write_text('pass', encoding='utf-8')
    done = call(client, auth, op, data, 'realize', scope)
    assert done.status_code == 200, done.text
    changed = next(n for n in done.json()['result']['graph']['nodes'] if n['id'] == 'node-1')
    assert changed['sourceRef']['origin'] == 'existing'
    assert changed['realization']['commit'] == 'abc1234'
    assert call(client, auth, op, data, 'new-stale', scope).status_code == 409
    (source / 'result.py').unlink()
    assert call(client, auth, op, data, 'realize', scope).json() == done.json()
    assert client.get('/api/desktop-v3/source-status', params=scope).json()['nodes']['node-1']['status'] == 'missing'
