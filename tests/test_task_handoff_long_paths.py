"""Regrese skutečného Git startu pod dlouhou Windows cestou, bez modelu."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from test_task_handoffs import HEADERS, ORIGIN, _prepare, _seed_packet

from backend.app import create_app


def test_owned_git_workspace_supports_deep_application_paths_without_global_config(tmp_path):
    root = tmp_path / ('d' * max(1, 165 - len(str(tmp_path)) - 1))
    app = create_app(root)
    app.state.task_handoffs.plans._hermes_paths = lambda: (tmp_path / 'hermes', tmp_path, Path(sys.executable))
    app.state.task_handoffs.worker = lambda *_args: None
    with TestClient(app, base_url=ORIGIN) as client:
        record = _prepare(client, _seed_packet(client))
        started = client.post('/api/task-handoffs/' + record['id'] + '/start', headers=HEADERS, json={'digest': record['digest'], 'confirmed': True})
        assert started.status_code == 200, started.text
        assert started.json()['status'] == 'starting'


def test_workspace_initialization_failure_is_terminal_without_starting_model(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    app.state.task_handoffs.plans._hermes_paths = lambda: (tmp_path / 'hermes', tmp_path, Path(sys.executable))
    launched = []
    app.state.task_handoffs.worker = lambda *_args: launched.append(True)

    def unavailable_git(*_args, **_kwargs):
        raise ValueError('Git preparation unavailable')

    monkeypatch.setattr('backend.task_handoffs.git', unavailable_git)
    with TestClient(app, base_url=ORIGIN) as client:
        record = _prepare(client, _seed_packet(client))
        response = client.post('/api/task-handoffs/' + record['id'] + '/start', headers=HEADERS, json={'digest': record['digest'], 'confirmed': True})
        assert response.status_code == 409
        state = client.get('/api/task-handoffs/' + record['id']).json()
        assert state['status'] == 'failed'
        assert state['localTreeInactive'] is True
        assert not launched
