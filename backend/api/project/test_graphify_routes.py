import hashlib
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.project.maps.graphify_runtime import clean_environment, writable
from backend.project.maps.map_artifacts import ArtifactUnavailable


def test_generate_uses_official_graphify_and_persists_output(tmp_path, real_graphify):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'hello.py').write_text('def hello():\n    return "hello"\n\nhello()\n')
    (root / '.env').write_text('SECRET_SENTINEL=must_not_enter_graph')
    app = create_app(tmp_path / 'state')
    app.state.service.project_hub.settings = lambda project: {'project': {'sourcePath': str(root)}}
    with TestClient(app, base_url='http://127.0.0.1:8740') as client:
        response = client.post('/api/graphify/generate?project=mine', json={}, headers={'Origin': 'http://127.0.0.1:8740'})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['counts']['nodes'] > 0
        assert result['version'] == '0.9.24'
        reread = client.get('/api/graphify/artifact?project=mine').json()
        assert reread['hashes'] == result['hashes']
        assert hashlib.sha256((root / 'graphify-out/graph.html').read_bytes()).hexdigest() == result['hashes']['graph.html']
        assert 'hello' in result['graphJson']
        assert 'SECRET_SENTINEL' not in result['graphJson']
        assert (root / 'graphify-out/GRAPH_REPORT.md').is_file()


def test_graphify_reads_original_output_for_selected_project(tmp_path):
    source = tmp_path / 'source'
    out = source / 'graphify-out'
    out.mkdir(parents=True)
    html = '<!doctype html><html><head></head><body>Original Graphify fixture</body></html>'
    (out / 'graph.html').write_text(html, encoding='utf-8')
    (out / 'graph.json').write_text(json.dumps({'nodes': [{'id': 'file.py'}], 'links': []}))
    app = create_app(tmp_path / 'state')
    def settings(project):
        if project != 'mine':
            raise ValueError('private path must not leak')
        return {'project': {'sourcePath': str(source)}}
    app.state.service.project_hub.settings = settings
    with TestClient(app, base_url='http://127.0.0.1:8740') as client:
        response = client.get('/api/graphify/artifact?project=mine')
        assert response.status_code == 200, response.text
        assert response.json()['html'] == html
        assert response.json()['counts'] == {'nodes': 1, 'edges': 0}
        assert response.json()['sourceRoot'] == str(source.resolve())
        unknown = client.get('/api/graphify/artifact?project=other')
        assert unknown.status_code == 409
        assert 'private path' not in unknown.text
        assert client.post('/api/graphify/generate?project=mine', json={}).status_code == 403


def test_failed_regeneration_preserves_existing_outputs(tmp_path, monkeypatch):
    import backend.project.maps.graphify_runtime as runtime
    root = tmp_path / 'source'
    output = root / 'graphify-out'
    output.mkdir(parents=True)
    (output / 'graph.html').write_text('original')
    service = SimpleNamespace(lock=threading.RLock(), project_hub=SimpleNamespace(settings=lambda project: {'project': {'sourcePath': str(root)}}))
    def fail(*args):
        raise ArtifactUnavailable('Controlled failure')
    monkeypatch.setattr(runtime, 'run_original', fail)
    with pytest.raises(ArtifactUnavailable):
        runtime.generate_graph(service, 'mine')
    assert (output / 'graph.html').read_text() == 'original'
    assert not runtime.GATE.locked()


def test_graphify_write_path_and_environment_are_bounded(tmp_path, monkeypatch):
    for name in ('../escape', 'graphify-out/../escape', 'graphify-out/C:bad', 'graphify-out/x/y'):
        with pytest.raises(ArtifactUnavailable):
            writable(tmp_path, name)
    keys = ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY')
    for key in keys:
        monkeypatch.setenv(key, 'secret-fixture')
    assert all(key not in clean_environment() for key in keys)


def test_graphify_refuses_output_symlink(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'root'
    root.mkdir()
    try:
        (root / 'graphify-out').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlinks are unavailable to this Windows user.')
    with pytest.raises(ArtifactUnavailable):
        writable(root, 'graphify-out/graph.html')


def test_manual_generate_writes_the_same_stable_set_atomically(tmp_path, monkeypatch):
    import backend.project.maps.graphify_runtime as runtime
    from backend.project.maps.map_artifacts import FILES
    root = tmp_path / 'source'
    (root / 'graphify-out').mkdir(parents=True)
    (root / 'graphify-out/graph.html').write_text('previous')
    service = SimpleNamespace(lock=threading.RLock(), project_hub=SimpleNamespace(settings=lambda project: {'project': {'sourcePath': str(root)}}))
    def fake(source, output):
        produced = output / 'graphify-out'
        produced.mkdir()
        (produced / 'graph.json').write_text(json.dumps({'nodes': [{'id': 'a'}], 'links': []}))
        (produced / 'graph.html').write_text('<html>new</html>')
        (produced / 'GRAPH_REPORT.md').write_text('# report')
        (output / 'graphify.log').write_text('{"codeFiles": 1}\n')
    monkeypatch.setattr(runtime, 'run_original', fake)
    runtime.generate_graph(service, 'mine')
    names = sorted(p.name for p in (root / 'graphify-out').iterdir())
    assert names == sorted([*FILES['graphify'], 'opora-build.lock'])
    assert (root / 'graphify-out/graph.html').read_text() == '<html>new</html>'
    receipt = json.loads((root / 'graphify-out/opora-receipt.json').read_text())
    assert receipt['hashes']['graph.html'] == hashlib.sha256(b'<html>new</html>').hexdigest()


def test_graphify_overview_reads_only_graph_json(tmp_path, monkeypatch):
    import backend.api.project.graphify_routes as routes
    source = tmp_path / 'source'
    out = source / 'graphify-out'
    out.mkdir(parents=True)
    raw = json.dumps({'nodes': [
        {'id': 'a', 'label': 'a.ts', 'community': 0, 'source_file': 'frontend/map/a.ts', 'file_type': 'code'},
        {'id': 'b', 'label': 'b.ts', 'community': 0, 'source_file': 'frontend/map/b.ts', 'file_type': 'code'},
        {'id': 'c', 'label': 'c.py', 'community': 1, 'source_file': 'backend/c.py', 'file_type': 'code'},
    ], 'links': [{'source': 'a', 'target': 'b', 'weight': 1}, {'source': 'a', 'target': 'c', 'weight': 3}]})
    (out / 'graph.json').write_text(raw, encoding='utf-8')
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    (out / 'opora-receipt.json').write_text(json.dumps({'hashes': {'graph.json': digest, 'graph.html': 'x'},
                                                        'generatedAt': '2026-10-14T10:00:00Z', 'version': '0.9.24'}))
    read = routes.read_output
    names = []
    monkeypatch.setattr(routes, 'read_output', lambda service, root, name: names.append(name) or read(service, root, name))
    app = create_app(tmp_path / 'state')
    app.state.service.project_hub.settings = lambda project: {'project': {'sourcePath': str(source)}}
    with TestClient(app, base_url='http://127.0.0.1:8740') as client:
        response = client.get('/api/graphify/overview?project=mine')
        assert response.status_code == 200, response.text
        value = response.json()
        assert 'graph.html' not in names
        assert value['project'] == 'mine' and value['version'] == '0.9.24'
        assert value['generatedAt'] == '2026-10-14T10:00:00Z'
        assert value['counts'] == {'nodes': 3, 'edges': 2, 'communities': 2}
        assert [item['name'] for item in value['communities']] == ['frontend/map', 'backend/c.py']
        assert value['edges'] == [{'source': 0, 'target': 1, 'weight': 3.0, 'count': 1}]
        assert value['truncated'] is False
        (out / 'graph.json').unlink()
        assert client.get('/api/graphify/overview?project=mine').status_code == 404
        (out / 'graph.json').write_text('{"nodes": [], "links": []}')
        assert client.get('/api/graphify/overview?project=mine').status_code == 409
