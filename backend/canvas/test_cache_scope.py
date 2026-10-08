"""Cache odděluje projekty i workspace a respektuje druhé spojení a rollback."""
import json
import sqlite3

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
from backend.editor.canvas_versions.canvas_versions import CanvasVersions


def test_project_and_workspace_values_never_leak(tmp_path):
    canvas = CanvasService(tmp_path)
    try:
        state = DesktopV3State(canvas)
        versions = CanvasVersions(canvas)
        projects = [canvas.project_hub.empty_project({'name': name, 'confirmed': True})['id'] for name in ('One', 'Two')]
        for index, project in enumerate(projects):
            for workspace in ('draft', 'other'):
                db = canvas.db_for(project)
                value = default_state()
                with db:
                    db.execute('INSERT INTO desktop_v3_state VALUES(?,?,?,?,?)', (project, workspace, index + (10 if workspace == 'other' else 1), json.dumps(value), 'now'))
            versions.save({'project': project, 'workspace': 'draft', 'digest': canvas.view(project, 'draft')['digest'], 'author': str(index)})
        for _ in range(2):
            for index, project in enumerate(projects):
                assert state.current(project, 'draft')['revision'] == index + 1
                assert state.current(project, 'other')['revision'] == index + 10
                assert canvas.project_hub.settings(project)['project']['name'] == ('One', 'Two')[index]
                assert versions.list(project, 'draft')['versions'][0]['author'] == str(index)
                # Interní current předpokládá ověřený scope; veřejný read jiný workspace odmítne.
                with pytest.raises(ValueError):
                    state.read(project, 'other')
    finally:
        canvas.close()


def test_external_commit_and_rollback_read_fresh_graph(tmp_path):
    canvas = CanvasService(tmp_path)
    canvas.db_for('draft')  # projektové databáze vznikají lazy
    other = sqlite3.connect(canvas.folder('draft').database)
    try:
        original = canvas.view('draft', 'draft')
        graph = {'nodes': [{'id': 'new', 'name': 'New', 'kind': 'node', 'parentId': None, 'purpose': '', 'x': 0, 'y': 0}], 'edges': []}
        with other:
            other.execute("UPDATE drafts SET graph=? WHERE id='draft'", (json.dumps(graph),))
        assert canvas.view('draft', 'draft')['graph'] == graph
        db = canvas.db_for('draft')
        db.execute("UPDATE drafts SET graph=? WHERE id='draft'", (json.dumps(original['graph']),))
        assert canvas.view('draft', 'draft')['graph'] == original['graph']
        db.rollback()
        assert canvas.view('draft', 'draft')['graph'] == graph
    finally:
        other.close()
        canvas.close()
