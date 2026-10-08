"""Retry historie při souběžném writeru a změně materiálů."""
import sqlite3

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.editor.canvas_versions.canvas_versions import CanvasVersions
from backend.editor.canvas_versions import version_read_cache as module


@pytest.mark.parametrize('failure', ['busy', 'asset'])
def test_transient_read_failure_retries_without_caching_old_data(tmp_path, monkeypatch, failure):
    canvas = CanvasService(tmp_path)
    try:
        versions = CanvasVersions(canvas)
        versions.save({'project': 'draft', 'workspace': 'draft', 'digest': canvas.view('draft', 'draft')['digest'], 'author': 'New'})
        calls = []
        target = module.sqlite3 if failure == 'busy' else versions
        name = 'connect' if failure == 'busy' else '_capture'
        original = getattr(target, name)

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                if failure == 'busy':
                    raise sqlite3.OperationalError('database is locked')
                raise PermissionError('material changed during scan')
            return original(*args, **kwargs)

        monkeypatch.setattr(target, name, flaky)
        result = versions.list('draft', 'draft')
        assert result['versions'][0]['author'] == 'New'
        assert len(calls) >= 2
        assert versions.list('draft', 'draft') == result
    finally:
        canvas.close()
