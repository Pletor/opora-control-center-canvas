import hashlib
import json
import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.archify_routes import create_archify_router


def delivery(root):
    folder = root / 'docs/architecture/archify'
    folder.mkdir(parents=True)
    html = b'<!doctype html><html><head></head><body><svg><text>REAL FILE</text></svg></body></html>'
    spec = b'{"diagram_type":"architecture","components":[],"connections":[],"boundaries":[]}'
    receipt = {'ok': True, 'command': 'deliver', 'type': 'architecture',
               'input': 'P:/original/map.architecture.json', 'output': 'P:/original/map.architecture.html',
               'artifact': {'sha256': hashlib.sha256(html).hexdigest(), 'bytes': len(html)},
               'specification': {'sha256': hashlib.sha256(spec).hexdigest(), 'bytes': len(spec)},
               'validation': {'checksPassed': 9, 'checkCount': 9, 'errors': 0, 'warnings': 0, 'compositionProfile': 'showcase'}}
    (folder / 'map.architecture.html').write_bytes(html)
    (folder / 'map.architecture.json').write_bytes(spec)
    (folder / 'deliver-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    return html, receipt


def client_for(root):
    def settings(project):
        if project != 'mine':
            raise ValueError('Private internal error')
        return {'project': {'id': project, 'sourceKind': 'local', 'sourcePath': str(root)}}
    service = SimpleNamespace(lock=threading.RLock(), project_hub=SimpleNamespace(settings=settings))
    app = FastAPI()
    app.include_router(create_archify_router(service))
    return TestClient(app)


def test_map_reads_exact_file_without_a_renderer(tmp_path):
    html, receipt = delivery(tmp_path)
    client = client_for(tmp_path)
    r = client.get('/api/archify/artifact?project=mine')
    assert r.status_code == 200, r.text
    value = r.json()
    assert value['html'].encode() == html
    assert value['artifact'] == receipt['artifact']
    assert value['freshness'] == 'unknown'
    assert 'original' not in json.dumps(value)
    assert client.post('/api/archify/render', json={'specification': {}}).status_code in {404, 405}


def test_map_rejects_modified_html_and_does_not_return_stale_data(tmp_path):
    delivery(tmp_path)
    path = tmp_path / 'docs/architecture/archify/map.architecture.html'
    path.write_bytes(path.read_bytes() + b'changed')
    response = client_for(tmp_path).get('/api/archify/artifact?project=mine')
    assert response.status_code == 409
    assert 'html' not in response.json()


def test_map_handles_missing_unknown_and_oversized_identity(tmp_path):
    client = client_for(tmp_path)
    assert client.get('/api/archify/artifact?project=mine').status_code == 404
    response = client.get('/api/archify/artifact?project=other')
    assert response.status_code == 409
    assert 'Private' not in response.text
    assert client.get('/api/archify/artifact', params={'project': 'x' * 65}).status_code == 422


def test_receipt_cannot_grant_access_outside_artifact_directory(tmp_path):
    html, receipt = delivery(tmp_path)
    receipt['output'] = str(tmp_path / 'secret.html')
    (tmp_path / 'secret.html').write_bytes(html)
    (tmp_path / 'docs/architecture/archify/deliver-receipt.json').write_text(json.dumps(receipt))
    assert client_for(tmp_path).get('/api/archify/artifact?project=mine').status_code == 404


def test_artifact_has_a_read_size_limit(tmp_path):
    from backend.archify_routes import MAX_HTML
    delivery(tmp_path)
    (tmp_path / 'docs/architecture/archify/map.architecture.html').write_bytes(b'x' * (MAX_HTML + 1))
    assert client_for(tmp_path).get('/api/archify/artifact?project=mine').status_code == 409


def test_linked_worktree_reads_main_artifact_without_copying(tmp_path):
    from backend.gitio import git
    main = tmp_path / 'main'
    main.mkdir()
    git(main, 'init', '--initial-branch=main')
    git(main, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '--allow-empty', '-m', 'fixture')
    linked = tmp_path / 'linked'
    git(main, 'worktree', 'add', '-b', 'other', str(linked))
    html, _ = delivery(main)
    response = client_for(linked).get('/api/archify/artifact?project=mine')
    assert response.status_code == 200, response.text
    assert response.json()['html'].encode() == html
    assert response.json()['sourceRoot'] == str(main.resolve())
    assert not (linked / 'docs/architecture/archify').exists()


def test_symlink_artifact_is_never_opened(tmp_path):
    import pytest
    delivery(tmp_path)
    target = tmp_path / 'outside.html'
    path = tmp_path / 'docs/architecture/archify/map.architecture.html'
    path.replace(target)
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip('Symlink oprávnění není dostupné.')
    assert client_for(tmp_path).get('/api/archify/artifact?project=mine').status_code == 409
