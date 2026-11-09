"""Unavailable code sources are explicit, never a substituted repository."""
from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_code_context import capture
from backend.project.workspace.workspace_sources import SourceMissing, WorkspaceSources


def test_unavailable_source_is_explicit_and_does_not_run_git(tmp_path, monkeypatch):
    service = CanvasService(tmp_path / 'data')
    def forbidden(*args, **kwargs):
        raise AssertionError('No Git fallback is permitted')
    monkeypatch.setattr('backend.canvas.opora_execution_code_context.git', forbidden)
    monkeypatch.setattr(WorkspaceSources, 'root', lambda *args: None)
    assert capture(service, 'draft', 'draft') == {'available': False, 'reason': 'no_source'}
    def missing(*args):
        raise SourceMissing('missing')
    monkeypatch.setattr(WorkspaceSources, 'root', missing)
    assert capture(service, 'draft', 'draft') == {'available': False, 'reason': 'source_unavailable'}
    service.close()
