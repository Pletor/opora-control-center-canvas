from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.integrations.gitio import git


def repository(path, name):
    path.mkdir()
    git(path, 'init', '--initial-branch=main')
    git(path, 'config', 'user.name', 'Fixture')
    git(path, 'config', 'user.email', 'fixture@localhost')
    (path / 'module.py').write_text(f'def {name}(): return 1\n')
    git(path, 'add', 'module.py')
    git(path, 'commit', '-m', 'initial')
    return path


def test_main_merge_queues_only_its_project_and_claim_is_exclusive(tmp_path):
    from backend.maps.map_refresh import MapRefresh
    app = create_app(tmp_path / 'state')
    service = app.state.service
    a = repository(tmp_path / 'a', 'alpha')
    b = repository(tmp_path / 'b', 'beta')
    pa = service.project_hub.local_project({'name': 'A', 'path': str(a), 'confirmed': True})['id']
    pb = service.project_hub.local_project({'name': 'B', 'path': str(b), 'confirmed': True})['id']
    manager = app.state.map_refresh
    manager.set_enabled(True, start=False)
    assert manager.claim() is None
    lane = tmp_path / 'lane'
    git(a, 'worktree', 'add', '-b', 'feature', str(lane))
    (lane / 'module.py').write_text('def alpha(): return 2\n')
    git(lane, 'commit', '-am', 'feature change')
    manager.scan()
    assert manager.status(pa)['status'] == 'watching'
    git(a, 'merge', '--ff-only', 'feature')
    manager.scan()
    assert manager.status(pa)['status'] == 'queued'
    assert manager.status(pb)['status'] == 'watching'
    job = manager.claim()
    assert job['project'] == pa
    assert job['revision'] == git(a, 'rev-parse', 'refs/heads/main')
    other = MapRefresh(service)
    assert other.claim() is None
    other.close()
    manager.close()
    service.close()


def test_snapshot_uses_committed_main_and_ignores_other_project_and_secrets(tmp_path):
    from backend.maps.map_refresh_snapshot import snapshot_main
    root = repository(tmp_path / 'repo', 'committed_symbol')
    (root / '.env').write_text('DO_NOT_COPY_SECRET=yes')
    git(root, 'add', '-f', '.env')
    git(root, 'commit', '-m', 'fixture secret exclusion')
    revision = git(root, 'rev-parse', 'refs/heads/main')
    (root / 'module.py').write_text('def dirty_symbol(): return 0\n')
    target = tmp_path / 'snapshot'
    files = snapshot_main(root, revision, target)
    assert files == ['module.py']
    assert 'committed_symbol' in (target / 'module.py').read_text()
    assert 'dirty_symbol' not in (target / 'module.py').read_text()
    assert not (target / '.env').exists()


def test_menu_preferences_are_separate_for_each_project_and_tool(tmp_path):
    app = create_app(tmp_path / 'state')
    service = app.state.service
    a = repository(tmp_path / 'a', 'alpha')
    b = repository(tmp_path / 'b', 'beta')
    pa = service.project_hub.local_project({'name': 'A', 'path': str(a), 'confirmed': True})['id']
    pb = service.project_hub.local_project({'name': 'B', 'path': str(b), 'confirmed': True})['id']
    app.state.map_refresh.set_enabled(True, start=False)
    with TestClient(app, base_url='http://127.0.0.1:8740') as client:
        result = client.post('/api/map-refresh/settings', json={'project': pa, 'tool': 'graphify', 'automatic': False}, headers={'Origin':'http://127.0.0.1:8740'})
        assert result.status_code == 200, result.text
        assert client.get('/api/map-refresh/status',params={'project':pa}).json()['automatic'] == {'graphify':False,'archify':True}
        assert client.get('/api/map-refresh/status',params={'project':pb}).json()['automatic'] == {'graphify':True,'archify':True}


def test_automation_is_off_until_explicitly_enabled(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1:8740') as client:
        response = client.get('/api/map-refresh/status?project=draft')
        assert response.status_code == 200
        assert response.json()['enabled'] is False
        assert response.json()['status'] == 'unavailable'


def test_real_graphify_refresh_publishes_only_selected_project(tmp_path):
    from backend.api.graphify_routes import load_graph
    app = create_app(tmp_path / 'state')
    service = app.state.service
    a = repository(tmp_path / 'a', 'alpha')
    b = repository(tmp_path / 'b', 'beta')
    pa = service.project_hub.local_project({'name':'A','path':str(a),'confirmed':True})['id']
    pb = service.project_hub.local_project({'name':'B','path':str(b),'confirmed':True})['id']
    manager = app.state.map_refresh
    manager.set_enabled(True, start=False)
    manager.retry(pa, 'graphify')
    manager.run_one()
    assert manager.status(pa)['status'] == 'succeeded', manager.status(pa)
    assert manager.status(pb)['status'] == 'watching'
    value = load_graph(service, pa)
    assert 'alpha' in value['graphJson']
    assert 'beta' not in value['graphJson']
    assert not (b / 'graphify-out/graph.json').exists()
    assert not (a / 'docs/architecture/archify').exists()
    manager.close()
    service.close()
