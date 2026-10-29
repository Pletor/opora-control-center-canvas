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
        self.gate_detail = {}
        self.reject_supported = False  # backend op reject-proposal přijde v dalším kusu  # po čtení /next změní revizi (souběžný zápis jiného agenta)
        self.duel = {'duel': {'status': 'grill', 'challenger': {'text': 'B', 'by': 'vyzyvatel-1', 'actor': 'agent'},
                              'turns': [{'id': 't%d' % i, 'side': 'A', 'kind': 'claim', 'text': 'x' * 200,
                                         'by': 'obhajce-1', 'actor': 'agent'} for i in range(1, 9)]},
                     'probability': {'p': 0.42, 'logit': -0.3, 'n': 3, 'contributions': []}, 'onTurn': 'B',
                     'rounds': {'A': 1, 'B': 0}, 'canDecide': False, 'trajectory': {'state': 'unclear'}}
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
                return self.reply(200, {'fragment': {'id': params['id']}, 'latestRevision': state.revision,
                                        'gateDetail': state.gate_detail})
            if url.path == '/api/brief-vault/duel':
                return self.reply(200, state.duel)
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
            if body['op'] in ('duel-open', 'vision-align'):
                return self.reply(200, {'ok': True, 'fragment': {'id': 'd1', 'revision': 1}})
            if body['expectedRevision'] != state.revision:
                return self.reply(409, {'error': f'fragment má revizi {state.revision}; načtěte nový stav.'})
            if body['op'] == 'reject-proposal' and not state.reject_supported:
                return self.reply(400, {'error': 'neznámá operace reject-proposal.'})
            if body['op'].startswith('duel-'):
                return self.reply(200, {'ok': True, 'probability': {'p': 0.5}, 'canDecide': False, 'status': 'grill'})
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


def test_only_loopback_base(server, capsys, monkeypatch):
    monkeypatch.setenv('OPORA_BASE_URL', 'http://example.com:80')
    code, out = run(capsys, 'next')
    assert code == 1 and server.calls == []


OK_CMD = 'python -c "import sys"'
FAIL_CMD = 'python -c "raise SystemExit(3)"'


def with_checks(state, *commands):
    checks = [{'id': f'c{i}', 'command': command} for i, command in enumerate(commands, 1)]
    state.gate_detail = {'synthesized': {'value': True, 'valid': True, 'payload': {'type': 'FLOW', 'checks': checks}}}


def run_checks(capsys, tmp_path, *extra, executor='vykonavatel-1', root=None, tests=None):
    if root is None:
        root = tmp_path / 'work'
        root.mkdir(exist_ok=True)
    tests = tests or tmp_path / 'checks'
    tests.mkdir(exist_ok=True)
    return run(capsys, 'run-checks', 'f1', '--root', str(root), '--tests', str(tests), '--executor', executor, *extra)


def test_run_checks_pass_proposes_verified_with_run(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    with_checks(server, OK_CMD, 'python -c "print(\'hotovo\')"')
    code, out = run_checks(capsys, tmp_path, '--plan-score', '9', '--note', 'běh kontrol')
    assert code == 0 and out['action'] == 'proposed' and out['tests'] == 'pass' and out['expectedRevision'] == 4
    assert [c['exitCode'] for c in out['checks']] == [0, 0] and out['checks'][1]['tail'].strip() == 'hotovo'
    body = server.proposals[0]
    assert body['op'] == 'propose' and body['gate'] == 'verified' and body['note'] == 'běh kontrol'
    actual = body['payload']['actual']
    assert actual['tests'] == 'pass' and actual['criticRounds'] == 0 and actual['unexpected'] is False
    assert actual['planApproved'] is True and actual['planScore'] == 9
    run_ = actual['run']
    assert run_['executor'] == 'vykonavatel-1' and run_['verifier'] == 'overovatel-1'
    assert [c['checkId'] for c in run_['checks']] == ['c1', 'c2'] and run_['checks'][0]['command'] == OK_CMD
    assert len(run_['checks'][0]['outputSha256']) == 64 and run_['checks'][0]['durationMs'] >= 0
    assert run_['at'].endswith('+00:00')
    assert 'tail' not in json.dumps(body)  # výstup kontrol na server nejde


def test_run_checks_fail_when_any_exit_code_is_nonzero(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    with_checks(server, OK_CMD, FAIL_CMD)
    code, out = run_checks(capsys, tmp_path, '--critic-rounds', '2', '--unexpected')
    assert code == 0 and out['tests'] == 'fail' and out['checks'][1]['exitCode'] == 3
    actual = server.proposals[0]['payload']['actual']
    assert actual['tests'] == 'fail' and actual['criticRounds'] == 2 and actual['unexpected'] is True
    assert 'planApproved' not in actual


def test_run_checks_refuses_executor_equal_to_actor(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    with_checks(server, OK_CMD)
    code, out = run_checks(capsys, tmp_path, executor='overovatel-1')
    assert code == 2 and out['action'] == 'error' and server.proposals == []


def test_run_checks_refuses_forbidden_program_and_chars_before_running_anything(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    for bad in ('rm -rf x', 'bash -c ls', 'python -c "pass" | cat', 'python a.py && python b.py', 'python ../x.py',
                'python /etc/x.py', 'python x.py > out.txt', 'python a\\b.py', 'python --file=/etc/x'):
        with_checks(server, OK_CMD, bad)
        code, out = run_checks(capsys, tmp_path)
        assert code == 2 and out['action'] == 'error', bad
    assert server.proposals == []


def test_run_checks_errors_without_checks_or_root(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    code, out = run_checks(capsys, tmp_path)
    assert code == 1 and out['action'] == 'error' and 'checks' in out['error']
    with_checks(server, OK_CMD)
    code, out = run_checks(capsys, tmp_path, root=tmp_path / 'neni')
    assert code == 1 and out['action'] == 'error' and server.proposals == []


def test_run_checks_stale_revision_is_409(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    with_checks(server, OK_CMD)
    code, out = run_checks(capsys, tmp_path, '--revision', '3')
    assert code == 3 and out['action'] == 'error' and out['conflict'] is True and server.proposals == []


CHECK_VECTORS = [
    ('python -m pytest -q test_slug.py', True), ('python tests/test_a.py', True),
    ('npm test -- --run src/a.test.ts', True), ('python tests\\test_a.py', False), ('python "C:probe.py"', False),
    ('python C:/x.py', False), ('python /x.py', False), ('python ../x.py', False), ('python --file=/etc/x', False),
    ('python "unterminated', False), ('bash x.sh', False), ('python a.py | cat', False),
    ('python -c "import sys; sys.exit(0)"', False),
]


@pytest.mark.parametrize(('command', 'allowed'), CHECK_VECTORS)
def test_check_vectors_match_backend_syntax(command, allowed):
    if allowed:
        assert opora_cycle.check_argv(command)
    else:
        with pytest.raises(opora_cycle.Refused):
            opora_cycle.check_argv(command)


def test_run_checks_uses_pinned_tests_not_executor_files(server, capsys, tmp_path, monkeypatch):
    """Vykonavatel podstrčí test_slug.py s `assert True` a conftest; platí test z --tests, conftest se maže."""
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    with_checks(server, 'python -m pytest -q test_slug.py')
    work, checks = tmp_path / 'work', tmp_path / 'checks'
    work.mkdir()
    checks.mkdir()
    (work / 'test_slug.py').write_text('def test_x():\n    assert True\n', encoding='utf-8')
    (work / 'conftest.py').write_text('collect_ignore_glob = ["*"]\n', encoding='utf-8')
    (checks / 'test_slug.py').write_text('def test_x():\n    assert False\n', encoding='utf-8')
    code, out = run_checks(capsys, tmp_path, root=work, tests=checks)
    assert code == 0 and out['tests'] == 'fail' and len(out['testsSha256']) == 64
    assert 'testsSha256' not in json.dumps(server.proposals[0])
    assert (work / 'test_slug.py').read_text(encoding='utf-8').endswith('assert True\n')  # původní složka beze změny


def test_run_checks_refuses_overlapping_tests_and_root(server, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'overovatel-1')
    with_checks(server, OK_CMD)
    inner = tmp_path / 'work' / 'checks'
    inner.mkdir(parents=True)
    code, out = run_checks(capsys, tmp_path, root=tmp_path / 'work', tests=inner)
    assert code == 2 and out['action'] == 'error' and server.proposals == []


def duel_run(capsys, *argv):
    code = opora_cycle.main(['duel', *argv, *SCOPE])
    return code, json.loads(capsys.readouterr().out)


def test_duel_open_sends_body_with_ref_and_files(server, capsys, tmp_path):
    inc = tmp_path / 'inc.txt'
    inc.write_text('Platný směr č.', encoding='utf-8')
    code, out = duel_run(capsys, 'open', '--subject-kind', 'fragment', '--subject', 'f1', '--incumbent-file', str(inc),
                         '--challenger', 'Změna', '--scope', 'n1', '--discipline', 'be', '--incumbent-ref', 'f1:4')
    assert code == 0 and out['op'] == 'duel-open'
    assert posts(server)[0][3] == {'op': 'duel-open', 'subject': {'kind': 'fragment', 'id': 'f1'},
                                   'incumbent': {'text': 'Platný směr č.', 'ref': {'fragmentId': 'f1', 'revision': 4}},
                                   'challenger': {'text': 'Změna'}, 'scopeNodeId': 'n1', 'discipline': 'be',
                                   'project': 'p1', 'workspace': 'draft'}


def test_duel_open_needs_exactly_one_text_source(server, capsys):
    code, out = duel_run(capsys, 'open', '--subject-kind', 'node', '--subject', 'n', '--challenger', 'B', '--scope', 'n1')
    assert code == 1 and posts(server) == []
    code, _ = duel_run(capsys, 'open', '--subject-kind', 'node', '--subject', 'n', '--incumbent', 'A', '--challenger', 'B',
                       '--incumbent-ref', 'bad', '--scope', 'n1')
    assert code == 1 and posts(server) == []


def test_duel_show_is_short(server, capsys):
    code, out = duel_run(capsys, 'show', 'd1')
    assert code == 0 and out['p'] == 0.42 and out['n'] == 3 and out['onTurn'] == 'B' and out['canDecide'] is False
    assert out['rounds'] == {'A': 1, 'B': 0} and out['trajectory'] == 'unclear'
    assert [t['id'] for t in out['turns']] == ['t3', 't4', 't5', 't6', 't7', 't8'] and len(out['turns'][0]['text']) <= 120
    assert server.calls[0][1:3] == ('/api/brief-vault/duel', {'project': 'p1', 'workspace': 'draft', 'id': 'd1'})


def test_duel_turn_body_revision_refs_and_evidence(server, capsys):
    code, out = duel_run(capsys, 'turn', 'd1', '--side', 'B', '--kind', 'answer', '--text', 'Odpověď', '--ref', 't1',
                         '--ref', 't2', '--evidence', 'docs/a.md:3|citát')
    assert code == 0 and out['expectedRevision'] == 4
    assert posts(server)[0][3] == {'op': 'duel-turn', 'fragmentId': 'd1', 'expectedRevision': 4, 'side': 'B',
                                   'kind': 'answer', 'text': 'Odpověď', 'refs': ['t1', 't2'],
                                   'evidence': [{'source': 'docs/a.md:3', 'quote': 'citát'}], 'project': 'p1',
                                   'workspace': 'draft'}
    assert duel_run(capsys, 'turn', 'd1', '--side', 'A', '--kind', 'claim', '--text', 'x', '--evidence', 'bez')[0] == 1


def test_duel_turn_stale_revision_is_409_and_text_file(server, capsys, tmp_path):
    path = tmp_path / 't.txt'
    path.write_text('Z souboru', encoding='utf-8')
    code, out = duel_run(capsys, 'turn', 'd1', '--side', 'A', '--kind', 'claim', '--text-file', str(path), '--revision', '3')
    assert code == 3 and out['conflict'] is True and posts(server)[0][3]['text'] == 'Z souboru'


def test_duel_score_by_judge_sends_body(server, capsys, monkeypatch):
    monkeypatch.setenv('OPORA_ACTOR', 'soudce-1')
    code, out = duel_run(capsys, 'score', 'd1', '--turn', 't2', '--strength', '7', '--supports', 'B', '--rebutted-by', 't5',
                         '--evidence-ok')
    assert code == 0 and out['p'] == 0.5
    assert posts(server)[0][3] == {'op': 'duel-score', 'fragmentId': 'd1', 'expectedRevision': 4, 'turnId': 't2',
                                   'strength': 7, 'supports': 'B', 'rebuttedBy': 't5', 'evidenceOk': True, 'project': 'p1', 'workspace': 'draft'}


@pytest.mark.parametrize('actor', ['obhajce-1', 'vyzyvatel-1'])
def test_duel_score_refused_for_author_of_turn_or_challenger(server, capsys, monkeypatch, actor):
    monkeypatch.setenv('OPORA_ACTOR', actor)
    code, out = duel_run(capsys, 'score', 'd1', '--turn', 't2', '--strength', '7', '--supports', 'A')
    assert code == 2 and out['refused'] is True and posts(server) == []


def test_duel_score_rejects_strength_out_of_range(server, capsys):
    with pytest.raises(SystemExit):
        duel_run(capsys, 'score', 'd1', '--turn', 't2', '--strength', '11', '--supports', 'A')
    assert server.calls == []


def test_duel_decide_has_no_override_and_sends_synthesis_turn(server, capsys):
    code, _ = duel_run(capsys, 'decide', 'd1', '--synthesis-turn', 't9')
    assert code == 0
    body = posts(server)[0][3]
    assert body == {'op': 'duel-decide', 'fragmentId': 'd1', 'expectedRevision': 4, 'synthesisTurnId': 't9',
                    'project': 'p1', 'workspace': 'draft'} and 'override' not in body
    code, _ = duel_run(capsys, 'decide', 'd1')
    assert code == 0 and 'synthesisTurnId' not in posts(server)[1][3]


def test_duel_align_body_without_revision_read(server, capsys):
    with pytest.raises(SystemExit):
        duel_run(capsys, 'align', '--score', '8', '--note', 'x', '--scope', 'n1')
    assert server.calls == []
    code, out = duel_run(capsys, 'align', '--score', '8', '--note', 'blíž', '--scope', 'n1', '--duel', 'd1')
    assert code == 0 and out['op'] == 'vision-align'
    assert posts(server)[0][3] == {'op': 'vision-align', 'score': 8, 'note': 'blíž', 'scopeNodeId': 'n1', 'duelId': 'd1',
                                   'project': 'p1', 'workspace': 'draft'}
    assert [c[1] for c in server.calls] == ['/api/brief-vault']
