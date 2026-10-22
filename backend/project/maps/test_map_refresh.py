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


def stable(path):
    # Stabilní sada už existuje; projekt tedy nečeká na počáteční běh.
    (path / 'graphify-out').mkdir()
    (path / 'graphify-out/graph.json').write_text('{}')
    (path / 'archify-out').mkdir()
    (path / 'archify-out/deliver-receipt.json').write_text('{}')
    return path


def two_projects(tmp_path, *, with_maps=True):
    app = create_app(tmp_path / 'state')
    service = app.state.service
    a = repository(tmp_path / 'a', 'alpha')
    b = repository(tmp_path / 'b', 'beta')
    if with_maps:
        stable(a), stable(b)
    pa = service.project_hub.local_project({'name': 'A', 'path': str(a), 'confirmed': True})['id']
    pb = service.project_hub.local_project({'name': 'B', 'path': str(b), 'confirmed': True})['id']
    return app, service, (a, pa), (b, pb)


def test_main_merge_queues_only_its_project_and_claim_is_exclusive(tmp_path):
    from backend.project.maps.map_refresh import MapRefresh
    app, service, (a, pa), (b, pb) = two_projects(tmp_path)
    manager = app.state.map_refresh
    manager.scan()
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
    from backend.project.maps.map_refresh_snapshot import snapshot_main
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
    app, service, (a, pa), (b, pb) = two_projects(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1:8740') as client:
        result = client.post('/api/map-refresh/settings', json={'project': pa, 'tool': 'graphify', 'automatic': False}, headers={'Origin':'http://127.0.0.1:8740'})
        assert result.status_code == 200, result.text
        assert client.get('/api/map-refresh/status',params={'project':pa}).json()['automatic'] == {'graphify':False,'archify':True}
        assert client.get('/api/map-refresh/status',params={'project':pb}).json()['automatic'] == {'graphify':True,'archify':True}


def test_automation_is_on_by_default_and_global_switch_persists(tmp_path):
    app = create_app(tmp_path)
    origin = {'Origin': 'http://127.0.0.1:8740'}
    with TestClient(app, base_url='http://127.0.0.1:8740') as client:
        response = client.get('/api/map-refresh/status?project=draft')
        assert response.status_code == 200
        assert response.json()['enabled'] is True
        assert response.json()['status'] == 'unavailable'
        assert client.get('/api/map-refresh/config').json() == {'enabled': True}
        assert client.post('/api/map-refresh/configure', json={'enabled': False}, headers=origin).json() == {'enabled': False}
        assert client.get('/api/map-refresh/config').json() == {'enabled': False}
    from backend.project.maps.map_refresh import MapRefresh
    reopened = MapRefresh(app.state.service)
    assert reopened.enabled() is False
    reopened.close()


def test_old_default_off_is_migrated_once(tmp_path):
    import sqlite3
    from types import SimpleNamespace

    from backend.project.maps.map_refresh import MapRefresh
    (tmp_path / 'map-refresh').mkdir()
    old = sqlite3.connect(tmp_path / 'map-refresh/state.sqlite')
    old.executescript('CREATE TABLE config(id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL); INSERT INTO config VALUES(1,0);')
    old.close()
    service = SimpleNamespace(root=tmp_path)
    manager = MapRefresh(service)
    assert manager.enabled() is True
    manager.set_enabled(False, start=False)
    manager.close()
    manager = MapRefresh(service)
    assert manager.enabled() is False
    manager.close()


def test_missing_stable_maps_queue_one_initial_run_per_automatic_tool(tmp_path):
    app, service, (a, pa), (b, pb) = two_projects(tmp_path, with_maps=False)
    stable(b)
    manager = app.state.map_refresh
    manager.scan()
    assert manager.status(pb)['status'] == 'watching'
    assert manager.status(pa)['status'] == 'queued'
    job = manager.claim()
    assert job['project'] == pa and job['tools'] == ['graphify', 'archify'] and job['manual'] is False
    manager.finish(job, 'failed', 'Controlled failure')
    manager.scan()
    # Selhaný počáteční běh se sám neopakuje; jinak by worker každých 5 s volal Sonnet.
    assert manager.status(pa)['status'] == 'failed'
    manager.close()
    service.close()


def test_initial_run_respects_manual_only_tool(tmp_path):
    app, service, (a, pa), _ = two_projects(tmp_path, with_maps=False)
    manager = app.state.map_refresh
    manager.settings(pa, 'archify', False)
    manager.scan()
    job = manager.claim()
    assert job['project'] == pa and job['tools'] == ['graphify']
    manager.close()
    service.close()


def test_update_now_runs_while_tool_and_global_automation_are_off(tmp_path):
    app, service, (a, pa), _ = two_projects(tmp_path)
    manager = app.state.map_refresh
    manager.settings(pa, 'archify', False)
    manager.set_enabled(False, start=False)
    seen = []
    manager.builder = lambda job, owner: seen.append((job['tools'], owner.current(job)))
    manager.retry(pa, 'archify')
    assert manager.status(pa)['status'] == 'queued'
    assert manager.run_one()['project'] == pa
    assert seen == [(['archify'], True)]
    assert manager.status(pa)['status'] == 'succeeded'
    assert manager.status(pa)['versions']['archify'] == git(a, 'rev-parse', 'refs/heads/main')
    # Bez výslovné volby se při vypnuté automatice nic dalšího nezařadí.
    assert manager.claim() is None
    manager.close()
    service.close()


def test_publish_rewrites_stable_files_in_place_and_excludes_them_from_git(tmp_path):
    from backend.project.maps.map_artifacts import FILES, publish
    root = repository(tmp_path / 'repo', 'alpha')
    graph, archify = tmp_path / 'graph', tmp_path / 'archify'
    graph.mkdir(), archify.mkdir()
    for name in FILES['graphify']:
        (graph / name).write_text('graph ' + name)
    for name in (*FILES['archify'], 'validate-receipt.json', 'evidence.json'):
        (archify / name).write_text('first ' + name)
    revision = git(root, 'rev-parse', 'refs/heads/main')
    publish(root, revision, {'graphify': graph, 'archify': archify})
    (archify / 'SPEC.md').write_text('second')
    publish(root, revision, {'archify': archify})
    assert sorted(p.name for p in (root / 'archify-out').iterdir()) == sorted(FILES['archify'])
    assert (root / 'archify-out/SPEC.md').read_text() == 'second'
    assert sorted(p.name for p in (root / 'graphify-out').iterdir()) == sorted(FILES['graphify'])
    assert sorted(p.name for p in root.iterdir()) == ['.git', 'archify-out', 'graphify-out', 'module.py']
    exclude = (root / '.git/info/exclude').read_text().splitlines()
    assert '/graphify-out/' in exclude and '/archify-out/' in exclude
    assert git(root, 'status', '--porcelain') == ''


def test_incomplete_output_does_not_overwrite_previous_set(tmp_path):
    import pytest

    from backend.project.maps.map_artifacts import FILES, publish
    root = tmp_path / 'root'
    (root / 'archify-out').mkdir(parents=True)
    (root / 'archify-out/SPEC.md').write_text('previous')
    partial = tmp_path / 'partial'
    partial.mkdir()
    for name in FILES['archify'][:-1]:
        (partial / name).write_text('new')
    with pytest.raises(ValueError):
        publish(root, 'a' * 40, {'archify': partial})
    assert (root / 'archify-out/SPEC.md').read_text() == 'previous'
    assert sorted(p.name for p in (root / 'archify-out').iterdir()) == ['SPEC.md']


def test_real_graphify_refresh_publishes_only_selected_project(tmp_path, real_graphify):
    from backend.api.project.graphify_routes import load_graph
    app, service, (a, pa), (b, pb) = two_projects(tmp_path, with_maps=False)
    manager = app.state.map_refresh
    manager.retry(pa, 'graphify')
    manager.run_one()
    assert manager.status(pa)['status'] == 'succeeded', manager.status(pa)
    # Ruční běh A projekt B nepozoruje ani nezařadí: bez scan() nemá B řádek, proto 'unavailable'.
    # ('watching' by B mít nemohl ani po scan(): bez stabilní sady by šel do počátečního běhu.)
    assert manager.status(pb)['status'] == 'unavailable'
    value = load_graph(service, pa)
    assert 'alpha' in value['graphJson']
    assert 'beta' not in value['graphJson']
    assert not (b / 'graphify-out/graph.json').exists()
    assert not (a / 'archify-out').exists()
    manager.close()
    service.close()
