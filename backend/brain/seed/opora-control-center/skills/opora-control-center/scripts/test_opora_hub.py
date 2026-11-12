"""`opora_hub.py` nad skutečným backendem (TestClient místo sítě) a nad falešnou sítí pro okrajové případy.

Hlídá smyčku skillu: agent-state s ETagem → `ready` akce `claim` → kontext → claim → neměnné zadání →
heartbeat → výsledek se `stepResults` (idempotentní) a že token nikdy neodejde na výstup.
"""

import io
import json
import sys
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[7]))

import opora_hub  # noqa: E402
import opora_write  # noqa: E402

ORIGIN = 'http://127.0.0.1:8740'
SCOPE = ['--project', 'draft', '--workspace', 'draft']


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def bridge(client):
    """`_open` skriptu přesměrovaný do TestClientu: stejné metody, hlavičky i tělo."""
    def fake_open(req, timeout):
        parts = urlsplit(req.full_url)
        path = parts.path + ('?' + parts.query if parts.query else '')
        headers = dict(req.header_items())
        response = client.request(req.get_method(), path, content=req.data, headers=headers)
        out = {k: v for k, v in response.headers.items() if k.lower() in ('etag', 'content-type')}
        if response.status_code >= 300:
            msg = Message()
            for key, value in out.items():
                msg[key] = value
            raise HTTPError(req.full_url, response.status_code, 'x', msg, io.BytesIO(response.content))
        return Response(response.content, response.status_code, out)
    return fake_open


@pytest.fixture
def backend(tmp_path, monkeypatch):
    import backend.conftest  # noqa: F401  (lidská UI session pro TestClient, vypnuté smyčky na pozadí)
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app
    from backend.api.editor.test_opora_changeset_routes import baseline_payload
    from backend.canvas.test_canvas_plan import HEADERS, seed

    monkeypatch.setenv(opora_hub.STATE_DIR_ENV, str(tmp_path / 'hub'))
    monkeypatch.setenv(opora_write.AGENT_ENV, 'worker-7f3a')
    monkeypatch.setenv(opora_write.BASE_ENV, ORIGIN)
    with TestClient(create_app(tmp_path / 'data'), base_url=ORIGIN) as client:
        seed(client)
        scope = {'project': 'draft', 'workspace': 'draft'}
        # Readiness = přijaté zadání s ≥ 1 krokem plánu (docs/oporahub-plan-steps.md), ne stará pipeline.
        steps = [{'id': 's1', 'order': 1, 'title': 'Parser DOCX', 'acceptance': ['test projde'], 'dependsOn': []}]
        fields = {'goal': 'Načíst DOCX', 'non_goals': 'PDF', 'acceptance': 'test projde', 'steps': steps}
        spec = client.post('/api/node-spec', headers=HEADERS, json={**scope, 'node': 'n0', 'expected_revision': 0,
                                                                     'fields': fields})
        assert spec.status_code == 200, spec.text
        assert client.post('/api/oporahub/baselines', headers=HEADERS,
                           json=baseline_payload(client)).status_code == 200
        monkeypatch.setattr(opora_write, '_open', bridge(client))
        yield client


def run(capsys, *argv):
    code = opora_hub.main([*argv, *SCOPE])
    captured = capsys.readouterr()
    return code, (json.loads(captured.out) if captured.out.strip() else None), captured.err


def test_full_agent_loop_against_the_real_backend(backend, capsys, tmp_path):
    code, state, _ = run(capsys, 'state')
    assert code == 0 and state['unchanged'] is False
    code, again, _ = run(capsys, 'state')
    assert code == 0 and again['unchanged'] is True  # 304 přes If-None-Match

    code, action, _ = run(capsys, 'pick', '--verb', 'claim', '--target', 'n0')
    assert code == 0 and action['status'] == 'ready' and action['id'].startswith('act_')

    # Kontext v2 potřebuje přijatý graf plánu: skript nespadne potichu na v1 a řekne, která akce je první.
    code, _, err = run(capsys, 'claim', '--action-id', action['id'])
    assert code == 5 and 'propose_graph' in json.loads(err)['hint']

    code, lease, out = run(capsys, 'claim', '--action-id', action['id'], '--context-version', '1', '--ttl', '120')
    assert code == 0, out
    execution = lease['executionId']
    bundle = json.loads((tmp_path / 'hub' / f'execution-{execution}.json').read_text('utf-8'))
    assert 'token' not in lease and bundle['token'] not in json.dumps(lease)

    code, assigned, _ = run(capsys, 'assignment', '--execution', execution)
    assert code == 0 and Path(assigned['file']).is_file() and bundle['token'] not in Path(assigned['file']).read_text('utf-8')
    code, beat, _ = run(capsys, 'heartbeat', '--execution', execution, '--ttl', '120')
    assert code == 0 and beat['epoch'] == bundle['epoch'] and 'assignment' not in beat  # jen oprávnění
    step = ('step', '--execution', execution, '--step-id', 's1', '--status', 'done', '--notes', 'ok', '--check', 'pytest')
    code, checkpoint, out = run(capsys, *step)
    assert code == 0 and checkpoint['stepId'] == 's1' and bundle['token'] not in out
    assert run(capsys, *step)[1] == checkpoint  # stejný krok a stav → stejné potvrzení

    result = tmp_path / 'result.json'
    result.write_text(json.dumps({'summary': 'Hotovo', 'stepResults': [
        {'stepId': 's1', 'status': 'done', 'evidence': {'checks': ['pytest'], 'commits': [], 'notes': 'ok'}}]}), 'utf-8')
    code, receipt, _ = run(capsys, 'results', '--execution', execution, '--result-file', str(result))
    assert code == 0 and receipt['result']['stepResults'][0]['stepId'] == 's1'
    code, repeat, _ = run(capsys, 'results', '--execution', execution, '--result-file', str(result))
    assert code == 0 and repeat == receipt  # stejné requestId → stejné potvrzení

    code, state, _ = run(capsys, 'state', '--card', 'n0')
    assert state['cards'][0]['executionId'] == execution
    code, _, err = run(capsys, 'claim', '--action-id', action['id'], '--context-version', '1')
    assert code == 5 and 'pick' in err  # staré ID akce po změně stavu neplatí


def test_blocked_action_is_never_sent(monkeypatch, tmp_path, capsys):
    calls = []
    state = {'actions': [{'id': 'act_x', 'verb': 'accept', 'status': 'blocked', 'blockReason': 'human_only',
                          'targetId': 'c1'}]}

    def fake_open(req, timeout):
        calls.append((req.get_method(), urlsplit(req.full_url).path))
        return Response(json.dumps(state).encode('utf-8'), 200, {'ETag': '"1"'})

    monkeypatch.setattr(opora_write, '_open', fake_open)
    monkeypatch.setenv(opora_hub.STATE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(opora_write.BASE_ENV, ORIGIN)
    code, _, err = run(capsys, 'claim', '--action-id', 'act_x')
    assert code == 5 and 'neopakuj' in err
    assert calls == [('GET', '/api/oporahub/agent-state')]
    code, _, _ = run(capsys, 'pick', '--verb', 'accept')
    assert code == 4


def test_events_feed_missing_on_an_older_server_is_refused(monkeypatch, tmp_path, capsys):
    def fake_open(req, timeout):
        raise HTTPError(req.full_url, 404, 'x', Message(), io.BytesIO(b'{"error": "Nezn\\u00e1m\\u00e1 cesta API."}'))

    monkeypatch.setattr(opora_write, '_open', fake_open)
    monkeypatch.setenv(opora_hub.STATE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(opora_write.BASE_ENV, ORIGIN)
    code, _, err = run(capsys, 'events')
    assert code == 5 and 'agent-state' in err


@pytest.mark.parametrize('result,message', [
    ({}, 'summary'),
    ({'summary': 'x', 'stepResults': [{'stepId': 's1', 'status': 'ok'}]}, 'done|failed|skipped'),
    ({'summary': 'x', 'stepResults': [{'stepId': 's1', 'status': 'done'}, {'stepId': 's1', 'status': 'done'}]}, 'dvakrát'),
    ({'summary': 'x', 'selfChecks': {'checks': [{'name': 'tests', 'status': 'passed', 'exitCode': 1}]}}, 'exitCode 0'),
])
def test_result_shape_is_checked_before_sending(result, message):
    with pytest.raises(ValueError, match=message):
        opora_hub.check_result(result)


def test_summary_keeps_autonomy():
    """Bez `autonomy` ve výstupu `state` agent nepozná plnou autonomii a přijetí nechá člověku."""
    state = {'autonomy': {'full': True}, 'actions': [{'id': 'a', 'verb': 'accept', 'status': 'ready', 'autonomy': 'full'}]}
    out = opora_hub.summary(state)
    assert out['autonomy'] == {'full': True} and out['ready'][0]['autonomy'] == 'full'
    assert opora_hub.summary({})['autonomy'] == {'full': False}
