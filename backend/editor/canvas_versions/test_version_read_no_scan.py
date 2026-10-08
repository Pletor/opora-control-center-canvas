"""Historie nesmí pro validaci cache třikrát procházet strom materiálů."""
from pathlib import Path

from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import encode
from backend.editor.agent_memory.desktop_v3_state import default_state
from backend.editor.canvas_versions.canvas_versions import CanvasVersions


def test_version_list_does_not_scan_material_tree(tmp_path, monkeypatch):
    canvas = CanvasService(tmp_path)
    try:
        versions = CanvasVersions(canvas)
        def forbidden(*args, **kwargs):
            raise AssertionError('Výpis historie nesmí procházet strom kvůli cache.')
        monkeypatch.setattr(Path, 'rglob', forbidden)
        first = versions.list('draft', 'draft')
        versions.save({'project': 'draft', 'workspace': 'draft',
                       'digest': canvas.view('draft', 'draft')['digest'], 'author': 'New'})
        second = versions.list('draft', 'draft')
        assert first['versions'] == []
        assert second['versions'][0]['author'] == 'New'
    finally:
        canvas.close()


def _install_upload(canvas):
    filename = '20261005-101010-12345678.png'
    path = canvas.folder('draft').canvas / 'materials' / 'a' / filename
    path.parent.mkdir(parents=True)
    path.write_bytes(b'old-upload')
    state = default_state()
    state['nodes']['a'] = {'materials': [{'kind': 'upload', 'path': filename}]}
    db = canvas.db_for('draft')
    db.execute('INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)',
               ('draft', 'draft', 1, encode(state), 'now'))
    db.commit()
    return path


def test_version_list_retries_when_referenced_upload_changes_after_capture(tmp_path, monkeypatch):
    canvas = CanvasService(tmp_path)
    try:
        versions = CanvasVersions(canvas)
        path = _install_upload(canvas)
        saved = versions.save({'project': 'draft', 'workspace': 'draft',
                               'digest': canvas.view('draft', 'draft')['digest'], 'author': 'New'})
        original = Path.read_bytes
        reads = []

        def replace_after_read(candidate):
            data = original(candidate)
            if candidate == path and not reads:
                reads.append(data)
                candidate.write_bytes(b'new-upload')
            return data

        monkeypatch.setattr(Path, 'read_bytes', replace_after_read)
        result = versions.list('draft', 'draft')

        assert reads == [b'old-upload']
        assert result['dirty'] is True
        assert result['currentToken'] != saved['currentToken']
    finally:
        canvas.close()


def test_version_list_does_not_cache_summaries_during_open_transaction(tmp_path, monkeypatch):
    canvas = CanvasService(tmp_path)
    try:
        versions = CanvasVersions(canvas)
        versions.save({'project': 'draft', 'workspace': 'draft',
                       'digest': canvas.view('draft', 'draft')['digest'], 'author': 'New'})
        db = canvas.db_for('draft')
        db.execute('BEGIN')
        try:
            def forbidden(*args, **kwargs):
                raise AssertionError('Otevřená transakce nesmí číst summaries cache.')
            monkeypatch.setattr(versions._read_cache, 'get_snapshot', forbidden)
            result = versions.list('draft', 'draft')
            assert result['versions'][0]['author'] == 'New'
            assert versions._read_cache.entries == {}
        finally:
            db.rollback()
    finally:
        canvas.close()


def test_version_list_does_not_cache_summaries_during_canvas_transaction(tmp_path):
    canvas = CanvasService(tmp_path)
    try:
        versions = CanvasVersions(canvas)
        versions.save({'project': 'draft', 'workspace': 'draft',
                       'digest': canvas.view('draft', 'draft')['digest'], 'author': 'New'})
        canvas.db.execute('BEGIN')
        try:
            result = versions.list('draft', 'draft')
            assert result['versions'][0]['author'] == 'New'
            assert versions._read_cache.entries == {}
        finally:
            canvas.db.rollback()
    finally:
        canvas.close()
