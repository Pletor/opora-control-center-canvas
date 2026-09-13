"""Nezávislá integrační oracle: kresba rodiče se dostane beze změny do zmrazeného snímku."""
import json

from fastapi.testclient import TestClient
from backend.project.workspace.test_workspace_sources import attach

from backend.app.factory import create_app

ORIGIN = 'http://127.0.0.1:8740'
HEADERS = {'origin': ORIGIN}


def test_ancestor_drawing_reaches_the_exact_frozen_agent_payload(tmp_path):
    source = tmp_path / 'source'
    (source / 'src').mkdir(parents=True)
    (source / 'src/editor.ts').write_text('// Actual source stays unchanged', encoding='utf-8')
    app = create_app(tmp_path / 'data')
    with TestClient(app, base_url=ORIGIN) as client:
        project = attach(client, source)
        scope = {'project': project, 'workspace': 'draft'}
        view = client.get('/api/view', params=scope).json()
        graph = {'nodes': [
            {'id': 'human-workspace', 'kind': 'sector', 'name': 'Pracovní prostor Člověka', 'purpose': 'Přesné podklady', 'parentId': None, 'x': 0, 'y': 0},
            {'id': 'editor', 'kind': 'node', 'name': 'Editor', 'purpose': 'Canvas je hlavní', 'parentId': 'human-workspace', 'x': 0, 'y': 0},
        ], 'edges': []}
        saved = client.post('/api/graph', headers=HEADERS, json={**scope, 'digest': view['digest'], 'graph': graph})
        assert saved.status_code == 200, saved.text
        parent = {**scope, 'layer': 'human-workspace'}
        scene = {'elements': [{'id': 'design-text', 'type': 'text', 'x': 20, 'y': 30, 'width': 170, 'height': 24, 'text': 'Struktura · Text · Kreslení · Mapa'}]}
        drawing = client.post('/api/drawing', headers=HEADERS, json={**parent, 'expected_revision': 0, 'scene': scene})
        assert drawing.status_code == 200, drawing.text
        request = {**scope, 'nodeId': 'editor', 'path': '', 'sessionId': '', 'references': ['src/editor.ts'], 'note': 'Vyřešit Editor podle kresby rodiče.'}
        preview = client.post('/api/desktop-v3/packet/preview', headers=HEADERS, json=request)
        assert preview.status_code == 200, preview.text
        rendered = preview.json()
        assert rendered['packet']['schema'] == 'opora.packet/1'
        manifest = rendered['packet']['sourceManifest']
        assert any(row['ownerId'] == 'human-workspace' and row['included'] and row['revision'] == 1 for row in manifest)
        assert 'Struktura · Text · Kreslení · Mapa' in json.dumps(rendered['packet'], ensure_ascii=False)
        frozen = client.post('/api/desktop-v3/packet/snapshot', headers=HEADERS, json={**request, 'digest': rendered['digest']})
        assert frozen.status_code == 200, frozen.text
        snapshot = frozen.json()
        assert snapshot['packet'] == rendered['packet']
        reread = client.get('/api/desktop-v3/packet/snapshots/' + snapshot['id'], params=scope)
        assert reread.status_code == 200, reread.text
        assert reread.json()['packet'] == snapshot['packet']
        assert 'session' not in snapshot['packet']['context'], 'Podklady už nevkládají žádný běh modelu.'
        assert (source / 'src/editor.ts').read_text(encoding='utf-8') == '// Actual source stays unchanged'


def test_project_packet_can_be_previewed_without_selecting_a_node(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    app = create_app(tmp_path / 'data')
    with TestClient(app, base_url=ORIGIN) as client:
        project = attach(client, source)
        request = {'project': project, 'workspace': 'draft', 'nodeId': '', 'path': '', 'sessionId': '', 'references': [], 'note': 'Zadání projektu bez vybraného uzlu.'}
        response = client.post('/api/desktop-v3/packet/preview', headers=HEADERS, json=request)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['packet']['scope']['nodeId'] == ''
        assert body['packet']['context']['project']['id'] == project
        assert body['packet']['task']['kind'] == 'project', 'Rozsah projektu se nesmí vydávat za existující uzel.'
        frozen = client.post('/api/desktop-v3/packet/snapshot', headers=HEADERS, json={**request, 'digest': body['digest']})
        assert frozen.status_code == 200, frozen.text
        assert frozen.json()['packet'] == body['packet']
        prepare = client.post('/api/desktop-v3/packet/snapshots/' + frozen.json()['id'] + '/prepare', headers=HEADERS, json={'project': project, 'workspace': 'draft', 'task': 'x'})
        assert prepare.status_code in (404, 405), 'Příprava handoffu přes Hermes byla odstraněna.'
