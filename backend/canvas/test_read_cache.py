"""Revizovaná cache vrací kopie a pozná interní, externí i vrácený zápis."""
import sqlite3

from backend.canvas.canvas_service import CanvasService
from backend.canvas.read_cache import ReadCache, database_stamp, file_stamp
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state


def test_graph_state_and_project_reuse_decoding_until_write(tmp_path, monkeypatch):
    import backend.canvas.canvas_service as module
    service = CanvasService(tmp_path)
    try:
        state = DesktopV3State(service)
        initial = service.view('draft', 'draft')
        original = module.digest
        calls = []
        monkeypatch.setattr(module, 'digest', lambda value: (calls.append(1), original(value))[1])
        assert service.view('draft', 'draft')['digest'] == initial['digest']
        assert calls == []
        changed = {**initial['graph'], 'nodes': [{'id':'n','kind':'node','name':'New','purpose':'','parentId':None,'x':0,'y':0}]}
        assert service.save_graph('draft','draft',changed,initial['digest'])['graph'] == changed
        saved = state.save({'project':'draft','workspace':'draft','expectedRevision':0,'state':default_state()})
        assert state.read('draft','draft')['revision'] == saved['revision']
        data = state.current('draft','draft')
        data['state']['nodes']['injected'] = {}
        assert 'injected' not in state.current('draft','draft')['state']['nodes']
        service.project_hub.save_settings({'project':'draft','expected_revision':0,'name':'Updated','settings':{'goal':'New goal','platform':'web','architecture':'','tenancy':''}})
        assert service.project_hub.settings('draft')['project']['name'] == 'Updated'
    finally:
        service.close()


def test_any_sql_write_and_external_commit_change_generation(tmp_path):
    db = sqlite3.connect(tmp_path / 'cache.sqlite')
    other = sqlite3.connect(tmp_path / 'cache.sqlite')
    try:
        db.execute('CREATE TABLE example(value TEXT)')
        db.commit()
        before = database_stamp(db)
        db.execute("INSERT INTO example VALUES('lease')")
        db.commit()
        assert database_stamp(db) != before
        before = database_stamp(db)
        other.execute("INSERT INTO example VALUES('agent-output')")
        other.commit()
        assert database_stamp(db) != before
        before = database_stamp(db)
        db.execute("INSERT INTO example VALUES('rollback')")
        db.rollback()
        assert database_stamp(db) != before
    finally:
        other.close()
        db.close()


def test_cache_is_bounded_and_revision_mismatch_evicts():
    cache = ReadCache(limit=1)
    cache.put(('p','w'), 1, {'nodes': []})
    value = cache.get(('p','w'),1)
    value['nodes'].append('mutated')
    assert cache.get(('p','w'),1) == {'nodes': []}
    assert cache.get(('p','w'),2) is None
    cache.put(('p','w'),2,{})
    cache.put(('other','w'),1,{})
    assert cache.get(('p','w'),2) is None


def test_file_stamp_observes_source_change(tmp_path):
    path = tmp_path / 'source'
    before = file_stamp(path)
    path.write_text('a')
    assert file_stamp(path) != before
    before = file_stamp(path)
    path.write_text('changed')
    assert file_stamp(path) != before
