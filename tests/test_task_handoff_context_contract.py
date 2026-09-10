"""HTTP důkaz, že dokumentace mapovaného souboru není závislá na ručním nodeId."""
from fastapi.testclient import TestClient
from test_workspace_sources import attach

from backend.app import create_app

ORIGIN = 'http://127.0.0.1:8740'
HEADERS = {'origin': ORIGIN}


def test_mapped_document_without_node_link_is_exported_and_invalidates_start(tmp_path):
    source = tmp_path / 'source'
    (source / 'docs').mkdir(parents=True)
    (source / 'docs' / 'handoff.md').write_text('# Zdroj beze změny', encoding='utf-8')
    app = create_app(tmp_path / 'data')
    # Tento test nikdy nespouští provider; chybný start by byl pouze stavová RED.
    app.state.task_handoffs._run = lambda _handoff: None
    with TestClient(app, base_url=ORIGIN) as client:
        project = attach(client, source)
        scope = {'project': project, 'workspace': 'draft'}
        view = client.get('/api/view', params=scope).json()
        graph = {'nodes': [
            {'id': 'sector', 'kind': 'sector', 'name': 'Dokumentace', 'purpose': 'Podklady', 'parentId': None, 'x': 0, 'y': 0, 'sourceRef': {'origin': 'existing', 'path': 'docs', 'kind': 'directory'}},
            {'id': 'focus', 'kind': 'node', 'name': 'Předání', 'purpose': 'Kontrakt', 'parentId': 'sector', 'x': 0, 'y': 0, 'sourceRef': {'origin': 'existing', 'path': 'docs/handoff.md', 'kind': 'file'}},
        ], 'edges': []}
        assert client.post('/api/graph', headers=HEADERS, json={**scope, 'digest': view['digest'], 'graph': graph}).status_code == 200
        doc_scope = {**scope, 'path': 'docs/handoff.md'}
        initial = client.get('/api/workspace/document', params=doc_scope).json()
        fields = {**initial['fields'], 'notes': 'MAPPED-DOCUMENT-PROOF'}
        saved = client.post('/api/workspace/document', headers=HEADERS, json={**doc_scope, 'expectedRevision': initial['revision'], 'fields': fields, 'nodeId': None})
        assert saved.status_code == 200, saved.text
        packet = client.post('/api/context/packets', headers=HEADERS, json={**scope, 'node': 'focus', 'includeNodeIds': ['sector'], 'includeJournalDays': [], 'maxBytes': 32000})
        assert packet.status_code == 200, packet.text
        prepared = client.post('/api/task-handoffs/prepare', headers=HEADERS, json={'packetId': packet.json()['id'], 'task': 'Vytvoř dokument podle uložené dokumentace.'}).json()
        exported = client.get('/api/task-handoffs/' + prepared['id'] + '/export')
        assert 'MAPPED-DOCUMENT-PROOF' in exported.text
        changed = client.post('/api/workspace/document', headers=HEADERS, json={**doc_scope, 'expectedRevision': saved.json()['revision'], 'fields': {**fields, 'notes': 'NOVÁ VERZE'}, 'nodeId': None})
        assert changed.status_code == 200, changed.text
        refused = client.post('/api/task-handoffs/' + prepared['id'] + '/start', headers=HEADERS, json={'digest': prepared['digest'], 'confirmed': True})
        assert refused.status_code == 409, refused.text
