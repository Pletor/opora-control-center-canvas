"""Regrese DDL, neměnných hitů a neblokujících čtení."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from backend.canvas.canvas_service import CanvasService
from backend.canvas.read_cache import ReadCache, database_stamp, scope_stamp
from backend.canvas.sync_report import SyncReport
from backend.editor.canvas_versions.canvas_versions import CanvasVersions
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state


def test_ddl_invalidates_cached_schema_value():
    with sqlite3.connect(':memory:') as db:
        cache = ReadCache()
        before = database_stamp(db)
        cache.put('schema', before, db.execute('PRAGMA table_info(example)').fetchall())
        db.execute('CREATE TABLE example(value TEXT)')
        assert cache.get('schema', database_stamp(db)) is None
        assert db.execute('PRAGMA table_info(example)').fetchone()[1] == 'value'


def test_git_scope_does_not_resolve_location():
    def forbidden(*args):
        pytest.fail('Git scope nesmí sahat na soubor ani dohledávat workspace.')
    with sqlite3.connect(':memory:') as db:
        canvas = SimpleNamespace(db=db, db_for=lambda _: db, location=forbidden,
                                 project_hub=SimpleNamespace(source_info=lambda _: {'sourceKind': 'git'}))
        assert scope_stamp(canvas, 'git-project', 'workspace') is None


@pytest.mark.parametrize('operation', ['view', 'state', 'settings', 'versions'])
def test_warm_snapshot_decode_outside_canvas_lock(tmp_path, monkeypatch, operation):
    canvas = CanvasService(tmp_path)
    try:
        state = DesktopV3State(canvas)
        state.save({'project': 'draft', 'workspace': 'draft', 'expectedRevision': 0, 'state': default_state()})
        versions = CanvasVersions(canvas)
        read = {'versions': lambda: versions.list('draft', 'draft'), 'view': lambda: canvas.view('draft', 'draft'),
                'state': lambda: state.read('draft', 'draft'),
                'settings': lambda: canvas.project_hub.settings('draft')}[operation]
        read()
        original = ReadCache.decode
        calls = []
        def checked(snapshot):
            if snapshot is not None:
                assert not canvas.lock._is_owned(), 'JSON kopie pod globálním zámkem'
                calls.append(1)
            return original(snapshot)
        monkeypatch.setattr(ReadCache, 'decode', staticmethod(checked))
        original_put = ReadCache.put
        def checked_put(cache, *args):
            assert not canvas.lock._is_owned(), 'JSON serializace pod globálním zámkem'
            return original_put(cache, *args)
        monkeypatch.setattr(ReadCache, 'put', checked_put)
        read()
        assert calls
    finally:
        canvas.close()


def test_history_two_projects_reach_git_concurrently(tmp_path, monkeypatch):
    from backend.canvas import sync_evidence
    canvas = CanvasService(tmp_path)
    rendezvous = Barrier(2)
    try:
        report = SyncReport(canvas)
        monkeypatch.setattr(canvas, 'db_for', lambda _: canvas.db)
        def commits(root, head):
            rendezvous.wait(timeout=3)
            return [{'sha': head}]
        monkeypatch.setattr(sync_evidence, 'commits_in_main', commits)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(report._history, pid, 'draft', tmp_path, pid, 'graph')
                       for pid in ('first', 'second')]
            assert [f.result(timeout=5) for f in futures] == [[{'sha': 'first'}], [{'sha': 'second'}]]
    finally:
        canvas.close()
