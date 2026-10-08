from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.canvas_versions.test_canvas_versions import SCOPE, HEADERS, ORIGIN, digest, graph, install_graph, save, versions


def test_versions_record_actor_and_changed_cards_without_becoming_dirty(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph('a', 'b'))
        response = client.post('/api/canvas-versions', headers={**HEADERS, 'X-Opora-Actor': 'agent; name=Tester'},
                               json={**SCOPE, 'digest': digest(client), 'author': 'Tester', 'expectedToken': versions(client)['currentToken']})
        assert response.status_code == 200, response.text
        first = response.json()['version']
        assert first['actor'] == 'agent' and first['changedCardCount'] == 2
        assert versions(client)['dirty'] is False
        assert save(client).json()['version']['changedCardCount'] == 0
        response = client.post('/api/node-text', headers=HEADERS,
                               json={**SCOPE, 'node': 'a', 'expected_revision': 0, 'text': 'New task details'})
        assert response.status_code == 200, response.text
        last = save(client).json()['version']
        assert last['actor'] == 'human' and last['changedCardCount'] == 1
        assert versions(client)['dirty'] is False
        read = client.get('/api/canvas-versions', params={**SCOPE, 'versionId': first['id']})
        assert read.status_code == 200 and read.json()['integrity'] == 'verified'
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert versions(client)['versions'][0]['changedCardCount'] == 1
