import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opora_closure


def stage(sid, kind, status, title='', retry_of=None, done_by=''):
    item = {'id': sid, 'kind': kind, 'lens': '', 'title': title or kind, 'status': status, 'approved': True,
            'doneBy': done_by}
    if retry_of:
        item['retryOf'] = retry_of
    return item


EVIDENCE = {'tests': {'status': 'passed', 'url': '', 'note': ''},
            'review': {'status': 'pending', 'url': '', 'note': ''},
            'merge': {'status': 'pending', 'url': '', 'note': ''},
            'checksRun': [{'checkId': 'pytest', 'command': 'uv run pytest', 'exitCode': 0, 'logUrl': '',
                           'at': '2026-10-09T10:00:00+00:00'}]}
NODE = {'id': 'n1', 'name': '[task] 2.11 Router'}
WEB = 'https://github.com/o/r'


def test_open_stages_mirrors_server_retry_resolution():
    stages = {'items': [stage('a', 'work', 'passed'), stage('b', 'critic', 'failed'), stage('c', 'fix', 'passed'),
                        stage('d', 'critic', 'passed', retry_of='b')]}
    assert opora_closure.open_stages(stages) == []
    stuck = {'items': [stage('a', 'review', 'failed'), stage('b', 'fix', 'passed')]}
    assert [item['id'] for item in opora_closure.open_stages(stuck)] == ['a']


def test_web_url_from_https_and_ssh_remotes():
    assert opora_closure.web_url('https://github.com/Pletor/ample.git') == 'https://github.com/Pletor/ample'
    assert opora_closure.web_url('git@github.com:Pletor/ample.git') == 'https://github.com/Pletor/ample'
    assert opora_closure.web_url('file:///tmp/repo') == ''


def test_card_row_next_step_and_who():
    done = {'items': [stage('a', 'work', 'passed'), stage('b', 'review', 'passed', 'Code review', done_by='rev-1')]}
    entry = {'stages': done, 'evidence': EVIDENCE}
    assert opora_closure.card_row(NODE, entry, 'abc1234567', '', WEB)['apply'] is True
    assert opora_closure.card_row(NODE, entry, '', 'abc1234567', WEB)['next'] == 'člověk: pokyn k pushi'
    assert opora_closure.card_row(NODE, entry, '', '', WEB)['next'] == 'člověk: pokyn ke commitu a pushi'
    ready = {**EVIDENCE, 'review': {'status': 'passed', 'url': WEB, 'note': ''},
             'merge': {'status': 'passed', 'url': WEB, 'note': ''}}
    assert opora_closure.card_row(NODE, {'stages': done, 'evidence': ready}, 'abc', '', WEB)['next'] == 'člověk: potvrdit uzavření v UI'
    stuck = {'items': [stage('a', 'review', 'failed', 'Shoda s návrhem')]}
    row = opora_closure.card_row(NODE, {'stages': stuck, 'evidence': EVIDENCE}, 'abc', '', WEB)
    assert row['pipeline'] == 'zaseknutá: Shoda s návrhem' and row['apply'] is False and row['retry'] == 'a'
    stuck_work = {'items': [stage('a', 'work', 'failed', 'Implementace')]}
    row = opora_closure.card_row(NODE, {'stages': stuck_work, 'evidence': EVIDENCE}, 'abc', '', WEB)
    assert row['retry'] == '' and row['next'].startswith('člověk:')
    assert opora_closure.card_row(NODE, {}, '', '', WEB)['next'] == 'router: určit pipeline'
    red = {**EVIDENCE, 'checksRun': [{**EVIDENCE['checksRun'][0], 'exitCode': 1}]}
    assert opora_closure.card_row(NODE, {'stages': done, 'evidence': red}, 'abc', '', WEB)['apply'] is False


def test_evidence_payload_links_commit_and_lists_reviewers_only_proposes():
    stages = {'items': [stage('a', 'work', 'passed', done_by='w'), stage('b', 'review', 'passed', 'Code review', done_by='rev-1'),
                        stage('c', 'critic', 'passed', 'Kritik: hacker', done_by='crit-2')]}
    row = {'id': 'n1', 'sha': 'abc1234567', 'web': WEB, 'stages': stages, 'evidence': EVIDENCE}
    payload = opora_closure.evidence_payload(row, {'expectedRevision': 7, 'contextVersion': 'cv'})
    evidence = payload['output']['evidence']
    assert evidence['review']['url'] == evidence['merge']['url'] == WEB + '/commit/abc1234567'
    assert 'Code review (rev-1), Kritik: hacker (crit-2)' in evidence['review']['note']
    assert evidence['tests'] == EVIDENCE['tests'] and evidence['checksRun'] == EVIDENCE['checksRun']
    assert payload['output']['done'] == {'proposed': True, 'note': payload['output']['done']['note']}
    assert 'confirmed' not in payload['output']['done']
    assert payload['expectedRevision'] == 7 and payload['contextVersion'] == 'cv'


def test_hook_runs_only_after_git_push():
    push = lambda command: json.dumps({'tool_input': {'command': command}})  # noqa: E731
    assert opora_closure.is_push(push('git push origin main'))
    assert opora_closure.is_push(push('cd repo && git -C . push'))
    assert not opora_closure.is_push(push('git status'))
    assert not opora_closure.is_push(push('echo push'))
    assert not opora_closure.is_push('not json')


def test_failed_stage_with_queued_retry_is_running_not_stuck():
    stages = {'items': [stage('a', 'work', 'passed'), stage('b', 'review', 'failed', 'Code review'),
                        stage('c', 'fix', 'todo', 'Oprava: Code review'), stage('d', 'review', 'todo', 'Code review', retry_of='b')]}
    row = opora_closure.card_row(NODE, {'stages': stages, 'evidence': EVIDENCE}, 'abc', '', WEB)
    assert row['pipeline'] == 'běží: Oprava: Code review' and row['retry'] == ''


def test_card_number_accepts_sector_letters():
    names = ['[task] 3.1 Index', '[task] K.5 Sada', '[task] B1 Schránka', '[task] 2.43 XLSX', '[task] Bez čísla']
    assert [m.group(1) if (m := opora_closure.CARD_NUMBER.match(n)) else None for n in names] == ['3.1', 'K.5', 'B1', '2.43', None]


def test_requeue_carries_revision_from_slim_response_and_refreshes_on_conflict(monkeypatch):
    """Karta P3: znovuzařazení vrací jen {revision, nodeId, stages}; další karta použije tuto revizi
    bez čtení celého stavu, při konfliktu 409 jednou s čerstvou revizí ze stavu."""
    from urllib.error import HTTPError
    reads, sent = [], []
    monkeypatch.setattr(opora_closure, 'get', lambda base, route, params: reads.append(route) or {'revision': 40})

    def post(base, route, payload):
        sent.append(payload['expectedRevision'])
        if payload['expectedRevision'] == 7:
            raise HTTPError(route, 409, 'conflict', {}, None)
        return {'revision': payload['expectedRevision'] + 1, 'nodeId': payload['nodeId'], 'stages': {'items': []}}

    monkeypatch.setattr(opora_closure, 'post', post)
    first = {'id': 'n1', 'retry': 'a'}
    assert opora_closure.requeue_with_revision('http://127.0.0.1:1', 'p', 'w', first, None) == 41
    assert reads == ['/api/desktop-v3/state'] and sent == [40]
    second = {'id': 'n2', 'retry': 'b'}
    assert opora_closure.requeue_with_revision('http://127.0.0.1:1', 'p', 'w', second, 41) == 42
    assert reads == ['/api/desktop-v3/state'] and sent == [40, 41]
    third = {'id': 'n3', 'retry': 'c'}
    assert opora_closure.requeue_with_revision('http://127.0.0.1:1', 'p', 'w', third, 7) == 41
    assert reads == ['/api/desktop-v3/state'] * 2 and sent == [40, 41, 7, 40]
