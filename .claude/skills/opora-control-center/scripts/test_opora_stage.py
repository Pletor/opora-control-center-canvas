"""Odevzdání etapy nad falešnou sítí: `_open` se podvrhne, nic neodchází (vzor test_opora_write.py)."""

import copy
import io
import json
import sys
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import opora_stage
import opora_write

BASE = 'http://127.0.0.1:8741'
TOKEN = 'a' * 64
VERSION = 'b' * 64


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def stage(sid, kind, status='todo', lens=''):
    return {'id': sid, 'kind': kind, 'lens': lens, 'title': 'Etapa ' + sid, 'brief': '', 'status': status,
            'note': '', 'doneBy': '', 'retryOf': ''}


def brief(stages):
    return {'outputContract': {'request': {'nodeId': 'n1', 'expectedRevision': 7, 'contextVersion': VERSION}},
            'evidence': {'tests': {'status': 'passed', 'url': '', 'note': 'z práce'},
                         'review': {'status': 'pending', 'url': '', 'note': ''},
                         'merge': {'status': 'pending', 'url': '', 'note': ''},
                         'checksRun': [{'checkId': 'lint', 'command': 'ruff', 'exitCode': 0, 'logUrl': '', 'at': 'T'}]},
            'pipeline': {'stages': stages, 'current': None, 'parallel': [], 'stuck': []},
            'ideas': {'open': [], 'done': 0}}


@pytest.fixture
def net(monkeypatch, tmp_path):
    server = {'brief': brief([stage('work', 'work', 'passed'), stage('user', 'critic', lens='user'),
                              stage('sly', 'critic', lens='sly'), stage('test', 'test')]),
              'claim_busy': 0, 'output_status': 200, 'apply': True, 'calls': []}

    def fail(req, code, text):
        raise HTTPError(req.full_url, code, 'x', Message(), io.BytesIO(json.dumps({'error': text}).encode('utf-8')))

    def fake_open(req, timeout):
        parts = urlsplit(req.full_url)
        body = json.loads(req.data) if req.data else None
        headers = {k.lower(): v for k, v in req.header_items()}
        server['calls'].append({'method': req.get_method(), 'route': parts.path, 'body': body, 'headers': headers,
                                'query': parse_qs(parts.query)})
        if parts.path == '/api/desktop-v3/node-brief':
            return Response(json.dumps(server['brief']).encode('utf-8'))
        if parts.path == '/api/desktop-v3/lease':
            if body['op'] == 'claim' and server['claim_busy'] > 0:
                server['claim_busy'] -= 1
                fail(req, 409, 'Kartu drží jiný agent.')
            return Response(json.dumps({'token': TOKEN} if body['op'] == 'claim' else {}).encode('utf-8'))
        if parts.path == '/api/desktop-v3/agent-output':
            if server['output_status'] != 200:
                fail(req, server['output_status'], 'Etapu nelze uzavřít před předchozími.')
            if server['apply']:
                report = body['output']['stages'][0]
                for item in server['brief']['pipeline']['stages']:
                    if item['id'] == report['id']:
                        item['status'] = report['status']
                server['brief']['ideas']['open'] += body['output'].get('ideas', [])
            return Response(json.dumps({'revision': 8}).encode('utf-8'))
        raise AssertionError('neočekávaná cesta ' + parts.path)

    monkeypatch.setattr(opora_write, '_open', fake_open)
    monkeypatch.setenv(opora_write.BASE_ENV, BASE)
    note = tmp_path / 'note.txt'
    note.write_text('Projito jako vyčuraný; bez blokátoru.', encoding='utf-8')
    server['note'] = str(note)
    return server


def run(server, *extra, sleeps=None):
    argv = ['--project', 'p1', '--workspace', 'draft', '--node', 'n1', '--agent', 'kritik-sly-2',
            '--note-file', server['note'], '--interval', '1', *extra]
    return opora_stage.main(argv, sleep=(sleeps.append if sleeps is not None else lambda _s: None))


def posted(server, route):
    return [call for call in server['calls'] if call['method'] == 'POST' and call['route'] == route]


def test_passed_critic_with_checks_and_ideas_is_written_released_and_verified(net, capsys):
    code = run(net, '--stage', 'sly', '--passed', '--idea', 'Dlouhý název zalomit.',
               '--check', 'unit=uv run pytest -k "a=b"=0')
    assert code == 0, capsys.readouterr().err
    [claim, release] = posted(net, '/api/desktop-v3/lease')
    assert claim['body']['op'] == 'claim' and claim['body']['owner'] == 'kritik-sly-2'
    assert release['body'] == {'project': 'p1', 'workspace': 'draft', 'nodeId': 'n1', 'op': 'release', 'token': TOKEN}
    [sent] = posted(net, '/api/desktop-v3/agent-output')
    assert sent['headers']['x-opora-lease'] == TOKEN and sent['headers']['x-opora-actor'] == 'agent; name=kritik-sly-2'
    body = sent['body']
    assert body['expectedRevision'] == 7 and body['contextVersion'] == VERSION and body['agent'] == 'kritik-sly-2'
    output = body['output']
    assert output['stages'] == [{'id': 'sly', 'status': 'passed', 'note': 'Projito jako vyčuraný; bez blokátoru.'}]
    assert output['ideas'] == [{'text': 'Dlouhý název zalomit.', 'source': 'critic:sly'}]
    evidence = output['evidence']
    assert evidence['tests']['status'] == 'passed' and evidence['review']['status'] == 'pending'
    assert {run['checkId']: run['command'] for run in evidence['checksRun']} == {'lint': 'ruff', 'unit': 'uv run pytest -k "a=b"'}
    result = json.loads(capsys.readouterr().out)
    assert result['ok'] is True and result['status'] == 'passed' and result['ideasOpen'] == 1


def test_a_red_check_reports_failed_tests_and_review_is_never_promoted(net):
    net['brief']['evidence'] = None
    assert run(net, '--stage', 'test', '--failed', '--check', 'unit=uv run pytest=1') == 0
    evidence = posted(net, '/api/desktop-v3/agent-output')[0]['body']['output']['evidence']
    assert evidence['tests']['status'] == 'failed' and 'unit' in evidence['tests']['note']
    assert evidence['review'] == {'status': 'pending', 'url': '', 'note': ''}


def test_busy_card_is_claimed_again_in_the_foreground_until_tries_run_out(net, capsys):
    net['claim_busy'] = 2
    sleeps = []
    assert run(net, '--stage', 'sly', '--passed', '--claim-tries', '3', sleeps=sleeps) == 0
    assert len(posted(net, '/api/desktop-v3/lease')) == 4 and sleeps == [1, 1]
    net['claim_busy'] = 5
    net['calls'].clear()
    assert run(net, '--stage', 'sly', '--passed', '--claim-tries', '2') == 3
    assert posted(net, '/api/desktop-v3/agent-output') == []
    assert 'conflict: Kartu drží jiný agent.' in capsys.readouterr().out


def test_conflicting_output_still_releases_the_lease(net):
    net['output_status'] = 409
    assert run(net, '--stage', 'test', '--passed') == 3
    assert [call['body']['op'] for call in posted(net, '/api/desktop-v3/lease')] == ['claim', 'release']


def test_unverified_write_is_an_error(net, capsys):
    net['apply'] = False
    assert run(net, '--stage', 'sly', '--passed') == 1
    assert 'Ověření čtením selhalo' in capsys.readouterr().err


def test_wait_prior_sleeps_until_earlier_stages_close_but_not_for_its_own_critic_round(net):
    net['brief']['pipeline']['stages'][0]['status'] = 'doing'
    sleeps = []
    original = copy.deepcopy(net['brief'])

    def finish_work(seconds):
        sleeps.append(seconds)
        net['brief']['pipeline']['stages'][0]['status'] = 'passed'

    assert opora_stage.wait_prior(BASE, {'project': 'p1', 'workspace': 'draft'}, 'n1', 'sly', 30, 5,
                                  sleep=finish_work) is None
    assert sleeps == [5]
    # Kritik „sly“ nečeká na kritika „user“ téhož kola.
    assert opora_stage.waiting_before(net['brief'], 'sly') == []
    assert opora_stage.waiting_before(original, 'sly') == ['Etapa work']
    assert opora_stage.waiting_before(net['brief'], 'test') == ['Etapa user', 'Etapa sly']


def test_wait_prior_gives_up_after_the_timeout(net, capsys):
    net['brief']['pipeline']['stages'][0]['status'] = 'doing'
    ticks = iter(range(0, 1000, 10))
    code = opora_stage.main(['--project', 'p1', '--workspace', 'draft', '--node', 'n1', '--agent', 'k', '--stage', 'sly',
                             '--passed', '--note-file', net['note'], '--wait-prior', '--timeout', '25', '--interval', '10'],
                            sleep=lambda _s: None, clock=lambda: next(ticks))
    assert code == 1 and 'Etapa work' in capsys.readouterr().err
    assert posted(net, '/api/desktop-v3/lease') == []


@pytest.mark.parametrize('value', ['unit', 'unit=cmd', '=cmd=0', 'unit= =0', 'unit=cmd=x', 'bad id=cmd=0'])
def test_bad_check_sends_nothing(net, value):
    assert run(net, '--stage', 'sly', '--passed', '--check', value) == 1
    assert net['calls'] == []


def test_empty_note_or_unknown_stage_fails(net, tmp_path):
    empty = tmp_path / 'empty.txt'
    empty.write_text('  ', encoding='utf-8')
    net['note'] = str(empty)
    assert run(net, '--stage', 'sly', '--passed') == 1 and net['calls'] == []
    net['note'] = str(tmp_path / 'note2.txt')
    Path(net['note']).write_text('ok', encoding='utf-8')
    assert run(net, '--stage', 'nobody', '--passed') == 1
    assert [call['body']['op'] for call in posted(net, '/api/desktop-v3/lease')] == ['claim', 'release']
