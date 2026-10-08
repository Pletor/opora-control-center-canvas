import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed


def save(client, stored):
    return client.post('/api/desktop-v3/state', headers=HEADERS, json={
        **SCOPE, 'expectedRevision': stored['revision'], 'state': stored['state']})


def configured(client):
    seed(client)
    stored = client.get('/api/desktop-v3/state', params=SCOPE).json()
    block = stored['state']['nodes']['n0']['blocks'][0]
    block['ports'][0]['onMet'] = {'kind': 'spawn', 'template': {
        'name': '[task] Review', 'purpose': 'Follow up', 'spec': {'goal': 'Review result'}, 'text': 'Instructions'}}
    response = save(client, stored)
    assert response.status_code == 200, response.text
    return response.json()


def test_transition_and_restart_do_not_duplicate(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        stored = configured(client)
        assert len(client.get('/api/view', params=SCOPE).json()['graph']['nodes']) == 3
        stored['state']['nodes']['n0']['blocks'][0]['state']['status'] = 'met'
        response = save(client, stored)
        assert response.status_code == 200, response.text
        graph = client.get('/api/view', params=SCOPE).json()['graph']
        successor = next(n for n in graph['nodes'] if n['name'] == '[task] Review')
        assert successor['parentId'] == 's0'
        assert successor['x'] >= 456 and successor['y'] == 0
        assert graph['edges'][0]['target'] == successor['id']
        assert graph['edges'][0]['sourcePortId'] == 'p0'
        assert save(client, response.json()).status_code == 200
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        stored = client.get('/api/desktop-v3/state', params=SCOPE).json()
        stored['state']['nodes']['n0']['blocks'][0]['state']['status'] = 'open'
        stored = save(client, stored).json()
        stored['state']['nodes']['n0']['blocks'][0]['state']['status'] = 'met'
        assert save(client, stored).status_code == 200
        assert len(client.get('/api/view', params=SCOPE).json()['graph']['nodes']) == 4


@pytest.mark.parametrize('invalid', [True, False])
def test_invalid_template_or_rejected_port_cannot_spawn(tmp_path, invalid):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        stored = configured(client)
        block = stored['state']['nodes']['n0']['blocks'][0]
        block['state']['status'] = 'met'
        if invalid:
            block['ports'][0]['onMet']['template']['name'] = ''
        else:
            block['ports'][0].update(status='rejected', reason='Not needed')
        response = save(client, stored)
        assert response.status_code == (409 if invalid else 200), response.text
        assert len(client.get('/api/view', params=SCOPE).json()['graph']['nodes']) == 3


def test_failed_graph_write_rolls_back_everything(tmp_path, monkeypatch):
    import copy

    from backend.canvas.canvas_service import CanvasService
    from backend.canvas.test_canvas_plan import GRAPH, STATE
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    service = CanvasService(tmp_path / 'data')
    store = DesktopV3State(service)
    service.desktop_v3_state = store
    try:
        digest = service.save_graph('draft', 'draft', GRAPH, service.view('draft', 'draft')['digest'])['digest']
        state = copy.deepcopy(STATE)
        block = state['nodes']['n0']['blocks'][0]
        block['ports'][0]['onMet'] = {'kind': 'spawn', 'template': {'name': 'Follow up', 'spec': {'goal': 'Review'}, 'text': 'Review'}}
        store.save({**SCOPE, 'expectedRevision': 0, 'state': state})
        block['state']['status'] = 'met'
        def fail(*args, **kwargs):
            raise OSError('disk full')
        monkeypatch.setattr(service, 'save_graph', fail)
        with pytest.raises(OSError):
            store.save({**SCOPE, 'expectedRevision': 1, 'state': state})
        assert store.read('draft', 'draft')['revision'] == 1
        assert service.view('draft', 'draft')['digest'] == digest
        for table in ('node_spec_revisions', 'node_text_revisions', 'port_spawns'):
            assert service.db_for('draft').execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
    finally:
        service.close()


def test_plan_configures_port_and_agent_result_spawns(tmp_path):
    from backend.canvas.test_canvas_plan import send as plan_send
    from backend.editor.agent_memory.test_agent_output import output
    from backend.editor.agent_memory.test_agent_output import send as output_send
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        result = plan_send(client, digest, {'extend': [{
            'node': '@n0', 'expectedRevision': 1, 'ports': [{'block': 'b0', 'ports': [
                {'ref': 'review', 'label': 'Review', 'onMet': {'kind': 'spawn', 'template': {'name': 'Review result'}}}]}]}]})
        assert result.status_code == 200, result.text
        brief = client.get('/api/desktop-v3/node-brief', params={**SCOPE, 'nodeId': 'n0'}).json()
        assert any(p.get('onMet') for p in brief['blocks'][0]['ports'])
        stored = client.get('/api/desktop-v3/state', params=SCOPE).json()
        response = output_send(client, {**SCOPE, 'nodeId': 'n0', 'expectedRevision': stored['revision'], 'agent': 'reviewer',
            'output': output(blocks=[{'blockId': 'b0', 'status': 'met', 'note': 'Verified'}], reports=[], decisions=[])})
        assert response.status_code == 200, response.text
        assert response.json()['graphChanged'] is True
        assert len(client.get('/api/view', params=SCOPE).json()['graph']['nodes']) == 4
