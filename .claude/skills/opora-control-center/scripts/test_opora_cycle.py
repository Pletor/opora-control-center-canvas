"""Booleovské ovládání cyklu proti falešnému HTTP serveru na loopbacku (docs/schranka-neurony.md §9 body 8 a 9)."""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import opora_cycle  # noqa: E402

SCOPE = ['--project', 'p1', '--workspace', 'draft']
PROPOSAL = {'id': 'pr1', 'gate': 'weighed', 'payload': {'benefit': 'Rychlejší import.', 'risk': 'Stará data.'},
            'by': 'navrhovatel-1', 'revision': 4}


class Server:
    """Stav jednoho fragmentu `f1` s revizí; zápis s jinou `expectedRevision` = 409 beze změny."""

    def __init__(self):
        self.revision = 4
        self.calls = []
        self.proposals = []
        self.race = False
        self.reject_supported = False  # backend op reject-proposal přijde v dalším kusu  # po čtení /next změní revizi (souběžný zápis jiného agenta)
        self.next = {'fragment': {'id': 'f1', 'title': 'Import', 'effectiveDiscipline': 'be', 'revision': 4},
                     'gate': 'weighed', 'needs': 'confirm', 'proposal': PROPOSAL, 'hint': 'x', 'lessons': [],
                     'blocked': 1}


def handler_for(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            data = json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlsplit(self.path)
            params = {k: v[0] for k, v in parse_qs(url.query).items()}
            state.calls.append(('GET', url.path, params, None, dict(self.headers)))
            if url.path == '/api/brief-vault/next':
                body = json.loads(json.dumps(state.next))
                if body.get('fragment'):
                    body['fragment']['revision'] = state.revision
                if state.race:
                    state.revision += 1
                return self.reply(200, body)
            if url.path == '/api/brief-vault/fragment':
                return self.reply(200, {'fragment': {'id': params['id']}, 'latestRevision': state.revision})
            if url.path == '/api/brief-vault/lessons':
                return self.reply(200, {'lessons': [{'id': 'l1', 'discipline': 'be', 'kind': 'pattern', 'text': 'T',
                                                     'effectiveWeight': 0.9, 'fragmentId': 'f1', 'by': 'x'}]})
            self.reply(404, {'error': 'nic'})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state.calls.append(('POST', self.path, None, body, dict(self.headers)))
            if self.path == '/api/brief-vault/gate-check':
                return self.reply(200, {'probability': None, 'provider': 'typesafe', 'inputHash': 'h',
                                        'reason': 'not-allowed'})
            if body['expectedRevision'] != state.revision:
                return self.reply(409, {'error': f'fragment má revizi {state.revision}; načtěte nový stav.'})
            if body['op'] == 'reject-proposal' and not state.reject_supported:
                return self.reply(400, {'error': 'neznámá operace reject-proposal.'})
            by = self.headers['X-Opora-Actor'].split('name=', 1)[1]
            if body['op'] == 'reject-proposal':
                return self.reply(200, {'ok': True, 'rejected': {'id': 'pr1', 'by': by}})
            if body['op'] == 'propose':
                state.proposals.append(body)
                return self.reply(200, {'ok': True, 'proposal': {'id': 'pr2', 'by': by, 'revision': state.revision}})
            state.revision += 1
            return self.reply(200, {'ok': True, 'fragment': {'revision': state.revision},
                                    'gates': {body['gate']: body['value']}, 'gateStep': 2, 'deadEnd': False,
                                    **({'placement': {'planId': 'pl1'}} if body['gate'] == 'placed' else {})})

    return Handler


@pytest.fixture
def server(monkeypatch):
    state = Server()
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(state))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('OPORA_BASE_URL', f'http://127.0.0.1:{httpd.server_port}')
    monkeypatch.setenv('OPORA_ACTOR', 'potvrzovatel-1')
    monkeypatch.delenv('OPORA_AGENT_NAME', raising=False)
    monkeypatch.delenv('OPORA_LEASE_TOKEN', raising=False)
    yield state
    httpd.shutdown()
    httpd.server_close()


def run(capsys, *argv):
    code = opora_cycle.main(list(argv) + SCOPE)
    return code, json.loads(capsys.readouterr().out)


def posts(state):
    return [call for call in state.calls if call[0] == 'POST']


def test_next_passes_discipline_and_scope(server, capsys):
    code, out = run(capsys, 'next', '--discipline', 'be')
    assert code == 0 and out['gate'] == 'weighed' and out['needs'] == 'confirm' and out['blocked'] == 1
    assert server.calls[0][1:3] == ('/api/brief-vault/next', {'project': 'p1', 'workspace': 'draft', 'discipline': 'be'})


def test_propose_reads_revision_itself_and_sends_payload(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'navrhovatel-1')
    path = tmp_path / 'p.json'
    path.write_text(json.dumps({'benefit': 'Č', 'risk': 'R'}), encoding='utf-8')
    code, out = run(capsys, 'propose', 'f1', 'weighed', '--json-file', str(path), '--note', 'odvozeno z textu')
    assert code == 0 and out['expectedRevision'] == 4 and out['proposal']['by'] == 'navrhovatel-1'
    body = posts(server)[0][3]
    assert body == {'op': 'propose', 'fragmentId': 'f1', 'expectedRevision': 4, 'gate': 'weighed',
                    'payload': {'benefit': 'Č', 'risk': 'R'}, 'note': 'odvozeno z textu', 'project': 'p1',
                    'workspace': 'draft'}
    assert posts(server)[0][4]['X-Opora-Actor'] == 'agent; name=navrhovatel-1'


def test_propose_with_stale_pinned_revision_is_409_without_change(server, capsys):
    code, out = run(capsys, 'propose', 'f1', 'weighed', '--json', '{"benefit": "a", "risk": "b"}', '--note', 'n',
                    '--revision', '3')
    assert code == 3 and out['conflict'] is True and 'revizi 4' in out['detail']
    assert server.proposals == [] and server.revision == 4


def test_yes_confirms_proposal_without_payload(server, capsys):
    code, out = run(capsys, 'yes', 'f1', 'weighed', '--note', 'přínos i riziko sedí')
    assert code == 0 and out['value'] is True and out['revision'] == 5 and out['proposal']['by'] == 'navrhovatel-1'
    body = posts(server)[0][3]
    assert body['op'] == 'gate' and body['value'] is True and body['expectedRevision'] == 4 and 'payload' not in body


def test_yes_refuses_own_proposal_and_sends_nothing(server, capsys, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'navrhovatel-1')
    code, out = run(capsys, 'yes', 'f1', 'weighed', '--note', 'ok')
    assert code == 2 and out['refused'] is True and posts(server) == []
    # Argument má přednost před proměnnou: jiný aktér potvrdit smí.
    code, _ = run(capsys, 'yes', 'f1', 'weighed', '--note', 'ok', '--actor', 'potvrzovatel-2')
    assert code == 0 and posts(server)[0][4]['X-Opora-Actor'] == 'agent; name=potvrzovatel-2'


def test_yes_refuses_when_proposal_is_not_visible(server, capsys):
    code, out = run(capsys, 'yes', 'f1', 'decided', '--note', 'ok')
    assert code == 2 and 'není v hlavě' in out['error']
    server.next['needs'], server.next['proposal'] = 'proposal', None
    code, out = run(capsys, 'yes', 'f1', 'weighed', '--note', 'ok')
    assert code == 2 and 'propose' in out['error'] and posts(server) == []


def test_no_turns_gate_off_with_revision_from_detail(server, capsys):
    code, out = run(capsys, 'no', 'f1', 'synthesized', '--note', 'done nejde ověřit')
    assert code == 0 and out['value'] is False
    assert [c[1] for c in server.calls] == ['/api/brief-vault/fragment', '/api/brief-vault']
    assert posts(server)[0][3]['value'] is False and posts(server)[0][3]['expectedRevision'] == 4


def test_conflict_after_concurrent_write_passes_through(server, capsys):
    server.race = True
    code, out = run(capsys, 'yes', 'f1', 'weighed', '--note', 'ok')
    assert code == 3 and out['conflict'] is True and 'načti znovu' in out['note']
    assert server.revision == 5 and len(posts(server)) == 1


def test_yes_and_no_take_no_payload_and_need_note(server, capsys):
    assert run(capsys, 'yes', 'f1', 'weighed', '--note', 'x', '--json', '{}')[0] == 1
    assert run(capsys, 'no', 'f1', 'weighed')[0] == 1
    assert run(capsys, 'propose', 'f1', 'scoped', '--json', '{}', '--note', 'x')[0] == 1
    assert server.calls == []


def test_check_returns_null_probability(server, capsys):
    code, out = run(capsys, 'check', 'f1', 'weighed')
    assert code == 0 and out['probability'] is None and out['reason'] == 'not-allowed'
    body = posts(server)[0][3]
    assert body == {'fragmentId': 'f1', 'expectedRevision': 4, 'gate': 'weighed', 'payload': PROPOSAL['payload'],
                    'project': 'p1', 'workspace': 'draft'}


def test_lessons_are_short(server, capsys):
    code, out = run(capsys, 'lessons', '--discipline', 'be')
    assert code == 0 and out['count'] == 1 and 'by' not in out['lessons'][0]


def test_placed_is_written_directly_by_the_agent(server, capsys):
    """§11: cyklus je čistě pro agenty; `yes … placed` zapíše rovnou (pojistkou je verze plátna z backendu)."""
    code, out = run(capsys, 'yes', 'f1', 'placed', '--note', 'vlož uložený plán')
    assert code == 0 and out['value'] is True and out['placement'] == {'planId': 'pl1'}
    body = posts(server)[0][3]
    assert body == {'op': 'gate', 'fragmentId': 'f1', 'expectedRevision': 4, 'gate': 'placed', 'value': True,
                    'note': 'vlož uložený plán', 'project': 'p1', 'workspace': 'draft'}


def test_assistant_window_still_asks_for_placed():
    """Okno asistenta je jiná cesta: stejný zápis přes opora_write.py tam dál schvaluje člověk."""
    from backend.claude_code.assistant import approvals

    body = json.dumps({'op': 'gate', 'fragmentId': 'f1', 'expectedRevision': 4, 'gate': 'placed', 'value': True,
                       'note': 'x'})
    command = f"python x/opora_write.py /api/brief-vault --project p1 --workspace draft --json '{body}'"
    kind, parsed = approvals.classify({'tool_name': 'Bash', 'input': {'command': command}})
    assert kind == 'ask' and parsed['payloadSummary'].startswith('Zápis na plátno: brána placed')


def test_reject_sends_reject_proposal_and_passes_400_until_backend_has_it(server, capsys):
    code, out = run(capsys, 'reject', 'f1', 'weighed', '--note', 'riziko je obecné')
    assert code == 1 and out['error'] == 'HTTP 400' and 'reject-proposal' in out['detail']
    assert posts(server)[0][3] == {'op': 'reject-proposal', 'fragmentId': 'f1', 'expectedRevision': 4,
                                   'gate': 'weighed', 'note': 'riziko je obecné', 'project': 'p1', 'workspace': 'draft'}
    server.reject_supported = True
    code, out = run(capsys, 'reject', 'f1', 'weighed', '--note', 'riziko je obecné')
    assert code == 0 and out['op'] == 'reject-proposal' and out['rejected']['id'] == 'pr1'
    assert run(capsys, 'reject', 'f1', 'weighed')[0] == 1  # bez --note nic neodejde
    assert len(posts(server)) == 2


def test_cycle_script_itself_is_never_approvable():
    """Asistent nemůže zápis obejít přes opora_cycle.py: backend ho zamítne sám."""
    from backend.claude_code.assistant import approvals

    command = 'python x/opora_cycle.py yes f1 placed --project p --workspace w --note ok'
    assert approvals.classify({'tool_name': 'Bash', 'input': {'command': command}})[0] == 'auto_deny'


def test_only_loopback_base(server, capsys, monkeypatch):
    monkeypatch.setenv('OPORA_BASE_URL', 'http://example.com:80')
    code, out = run(capsys, 'next')
    assert code == 1 and server.calls == []
