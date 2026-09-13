"""Deadline musí platit i pro závěrečné ověření už zapsaného souboru."""
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from test_task_handoffs import HEADERS, ORIGIN, _prepare, _ShortChildPlans

from backend.app.factory import create_app


def test_verification_crossing_deadline_never_becomes_completed(tmp_path, monkeypatch):
    clock = [0.0]
    verified_reads = []
    monkeypatch.setattr('backend.agents.runs.task_handoffs.time', SimpleNamespace(monotonic=lambda: clock[0], sleep=time.sleep))
    original = Path.read_text

    def late_read(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path.name == 'result.md':
            verified_reads.append(True)
            clock[0] = 1000.0
        return value

    monkeypatch.setattr(Path, 'read_text', late_read)
    app = create_app(tmp_path)
    app.state.task_handoffs.plans = _ShortChildPlans('success')
    with TestClient(app, base_url=ORIGIN) as client:
        record = _prepare(client)
        response = client.post('/api/task-handoffs/' + record['id'] + '/start', headers=HEADERS, json={'digest': record['digest'], 'confirmed': True})
        assert response.status_code == 200
        until = time.monotonic() + 5
        state = response.json()
        while state['status'] in {'starting', 'running', 'verifying', 'stopping'} and time.monotonic() < until:
            time.sleep(0.05)
            state = client.get('/api/task-handoffs/' + record['id']).json()
        assert verified_reads
        assert state['status'] == 'cancelled', state
        assert state['localTreeInactive'] is True
        assert state['verification']['passed'] is not True
