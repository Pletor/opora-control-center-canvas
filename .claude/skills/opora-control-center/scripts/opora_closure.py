"""Brána uzavření karet: přehled, co kartám chybí k uzavření, a doplnění důkazů po pushi.

`opora_closure.py --project P --workspace W --repo CESTA [--node SEKTOR] [--apply] [--hook]`.
Bez `--apply` jen vypíše tabulku (nic nezapisuje): pipeline, testy, review, merge, commit a další krok
s tím, kdo ho dělá (agent / auto / člověk).
`--apply`: karta s hotovou pipeline, zelenými `checksRun` a commitem `(OPORA karta N)` na
`<remote>/<branch>` dostane přes agent-output důkaz review a merge = odkaz na commit (review shrne
etapy review a kritiky z pipeline) a `done.proposed`. Uzavření potvrzuje dál jen člověk v UI.
Zaseknutou etapu test / review / kritik (selhala, opakování nenaplánováno) `--apply` znovu zařadí
(`/api/desktop-v3/pipeline` op retry: oprava + opakování); po vyčerpaných smyčkách rozhoduje člověk.
`--hook` (PostToolUse hook na Bash): čte JSON hooku ze stdin a běží jen po `git push`; chyby
nevrací (hook nesmí shodit práci agenta).
Adresa jen loopback (`--base-url` nebo `OPORA_BASE_URL`).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opora_write import BASE_ENV, LEASE_ENV, TIMEOUT, _detail, _read, base_url, post

AGENT = 'closure-auto'
CARD_NUMBER = re.compile(r'^\[task\]\s+((?:[0-9]+|[A-Z]\.?[0-9]+)(?:\.[0-9]+)*)\s')  # 3.1, K.5, B1
REVIEW_KINDS = ('review', 'critic')
RETRIED = ('test', 'review', 'critic')  # shodně s card_pipeline.RETRIED


def get(base, route, params):
    return _read(Request(base + route + '?' + urlencode(params), headers={'Accept': 'application/json'}), TIMEOUT)


# --- pipeline (zrcadlo backend/editor/agent_memory/card_pipeline.py: active / resolved / open_stages)

def _root(item):
    return item.get('retryOf', item['id'])


def open_stages(stages):
    items = [item for item in (stages or {}).get('items', []) if item.get('approved', True)]

    def resolved(position):
        item = items[position]
        if item['status'] in ('passed', 'skipped'):
            return True
        return item['status'] == 'failed' and any(
            _root(later) == _root(item) and later['status'] in ('passed', 'skipped') for later in items[position + 1:])
    return [item for position, item in enumerate(items) if not resolved(position)]


def stuck(stages):
    """Selhané etapy bez naplánovaného opakování (zrcadlo card_pipeline.stuck)."""
    items = [item for item in (stages or {}).get('items', []) if item.get('approved', True)]
    waiting = {id(item) for item in open_stages(stages)}
    return [item for position, item in enumerate(items)
            if item['status'] == 'failed' and id(item) in waiting
            and not any(_root(later) == _root(item) and later['status'] in ('todo', 'doing')
                        for later in items[position + 1:])]


def reviewers(stages):
    """Prošlé etapy review a kritiků jako doklad review: „Code review (review-x), Kritik: hacker (…)“."""
    items = [item for item in (stages or {}).get('items', []) if item.get('approved', True)]
    return ', '.join(f"{item['title']} ({item.get('doneBy') or '?'})" for item in items
                     if item['kind'] in REVIEW_KINDS and item['status'] == 'passed')


# --- git

def git(repo, *args):
    done = subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True, encoding='utf-8', check=False)
    return done.stdout.strip() if done.returncode == 0 else ''


def web_url(remote_url):
    """https://github.com/o/r.git i git@github.com:o/r.git → https://github.com/o/r; jinak ''."""
    match = re.fullmatch(r'(?:https://|git@)([\w.-]+)[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?', remote_url.strip())
    return f'https://{match[1]}/{match[2]}/{match[3]}' if match else ''


def find_commit(repo, number, ref):
    """Nejnovější commit `(OPORA karta N)` dosažitelný z `ref`; '' když není."""
    return git(repo, 'log', ref, '-F', '--grep', f'OPORA karta {number})', '--format=%H', '-n', '1')


# --- přehled

def card_row(node, entry, pushed, local, web):
    """Stav jedné karty a další krok; čisté rozhodnutí bez I/O."""
    stages = entry.get('stages') or {}
    evidence = entry.get('evidence') or {}
    runs = evidence.get('checksRun') or []
    status = lambda key: (evidence.get(key) or {}).get('status', '-')
    failed = stuck(stages)
    waiting = [item for item in open_stages(stages) if item['status'] != 'failed']
    if not stages.get('items'):
        pipeline = 'bez pipeline'
    elif failed:
        pipeline = 'zaseknutá: ' + failed[0]['title']
    elif waiting:
        pipeline = 'běží: ' + waiting[0]['title']
    else:
        pipeline = 'hotová'
    checks_ok = bool(runs) and all(run['exitCode'] == 0 for run in runs)
    row = {'id': node['id'], 'card': node['name'], 'pipeline': pipeline,
           'tests': ('ok ' + str(len(runs))) if checks_ok else ('chyba' if runs else '-'),
           'review': status('review'), 'merge': status('merge'),
           'commit': (pushed[:7] + ' push') if pushed else ((local[:7] + ' jen lokálně') if local else '-'),
           'proposed': bool((entry.get('done') or {}).get('proposed')), 'apply': False, 'retry': ''}
    if pipeline == 'bez pipeline':
        row['next'] = 'router: určit pipeline'
    elif failed and failed[0]['kind'] in RETRIED:
        row['next'] = 'auto: znovu zařadit „' + failed[0]['title'] + '“ – oprava + opakování (--apply)'
        row['retry'] = failed[0]['id']
    elif failed:
        row['next'] = 'člověk: rozhodnout zaseknutou etapu „' + failed[0]['title'] + '“'
    elif waiting:
        row['next'] = 'agent: etapa „' + waiting[0]['title'] + '“'
    elif not checks_ok:
        row['next'] = 'agent: spustit kontroly a zapsat checksRun'
    elif not pushed:
        row['next'] = 'člověk: pokyn ke commitu a pushi' if not local else 'člověk: pokyn k pushi'
    elif row['review'] != 'passed' or row['merge'] != 'passed':
        row['next'] = 'auto: doplnit review + merge z commitu (--apply)' if web else 'agent: chybí web URL remote'
        row['apply'] = bool(web)
    else:
        row['next'] = 'člověk: potvrdit uzavření v UI'
    return row


def collect(base, project, workspace, repo, sector, remote, branch):
    scope = {'project': project, 'workspace': workspace}
    graph = get(base, '/api/view', scope)['graph']
    stored = get(base, '/api/desktop-v3/state', scope)
    state = stored['state']['nodes']
    parents = {node['id']: node.get('parentId') for node in graph['nodes']}

    def under(node_id):
        while node_id:
            if node_id == sector:
                return True
            node_id = parents.get(node_id)
        return False
    web = web_url(git(repo, 'remote', 'get-url', remote))
    rows = []
    for node in graph['nodes']:
        match = CARD_NUMBER.match(node.get('name', ''))
        entry = state.get(node['id'], {})
        if not match or (entry.get('done') or {}).get('confirmed') or (sector and not under(node['id'])):
            continue
        pushed = find_commit(repo, match[1], f'{remote}/{branch}')
        local = '' if pushed else find_commit(repo, match[1], 'HEAD')
        row = card_row(node, entry, pushed, local, web)
        row.update(number=match[1], sha=pushed, web=web, stages=entry.get('stages'), evidence=entry.get('evidence'),
                   revision=stored['revision'])
        rows.append(row)
    rows.sort(key=lambda row: [(0, int(p)) if p.isdigit() else (1, p) for p in re.split(r'\.|(?<=[A-Z])(?=[0-9])', row['number'])])
    return rows


def table(rows):
    head = ('Karta', 'Pipeline', 'Testy', 'Review', 'Merge', 'Commit', 'Další krok')
    body = [(row['card'][:46], row['pipeline'][:34], row['tests'], row['review'], row['merge'], row['commit'], row['next'])
            for row in rows]
    widths = [max(len(str(line[i])) for line in [head, *body]) for i in range(len(head) - 1)]
    fmt = lambda line: '  '.join(str(cell).ljust(width) for cell, width in zip(line, widths)) + '  ' + line[-1]
    return '\n'.join([fmt(head), fmt(tuple('-' * w for w in widths) + ('-' * 10,)), *map(fmt, body)])


# --- doplnění důkazů

def evidence_payload(row, request):
    url = row['web'] + '/commit/' + row['sha']
    evidence = dict(row['evidence'])
    evidence['review'] = {'status': 'passed', 'url': url,
                          'note': ('Etapy pipeline prošly: ' + reviewers(row['stages']))[:4000] + '; obsah v commitu.'}
    evidence['merge'] = {'status': 'passed', 'url': url, 'note': f'Push na main {row["sha"][:7]}.'}
    return {'nodeId': row['id'], 'expectedRevision': request['expectedRevision'],
            'contextVersion': request['contextVersion'], 'agent': AGENT,
            'output': {'schema': 'opora.agent-output/1', 'blocks': [], 'reports': [], 'decisions': [], 'stages': [],
                       'done': {'proposed': True, 'note': f'Pipeline hotová, kontroly zelené, commit {row["sha"][:7]} '
                                                          'na main. Čeká na potvrzení uzavření člověkem.'},
                       'evidence': evidence}}


def apply(base, project, workspace, row):
    scope = {'project': project, 'workspace': workspace}
    brief = get(base, '/api/desktop-v3/node-brief', {**scope, 'nodeId': row['id']})
    claim = post(base, '/api/desktop-v3/lease', {**scope, 'nodeId': row['id'], 'op': 'claim', 'owner': AGENT,
                                                  'ttlSeconds': 120})
    token = (claim.get('result') or claim).get('token', '')
    os.environ[LEASE_ENV] = token
    try:
        post(base, '/api/desktop-v3/agent-output', {**scope, **evidence_payload(row, brief['outputContract']['request'])})
    finally:
        post(base, '/api/desktop-v3/lease', {**scope, 'nodeId': row['id'], 'op': 'release', 'token': token})
        os.environ.pop(LEASE_ENV, None)


def requeue(base, project, workspace, row):
    """Znovu zařadí etapu; vrací štíhlou odpověď serveru {revision, nodeId, stages} (karta P3)."""
    return post(base, '/api/desktop-v3/pipeline', {'project': project, 'workspace': workspace, 'nodeId': row['id'],
                                                   'expectedRevision': row['revision'], 'op': 'retry', 'stageId': row['retry'],
                                                   'reason': 'Zaseknutá etapa bez opakování; automatická oprava + opakování.'})


def requeue_with_revision(base, project, workspace, row, known):
    """Znovu zařadí etapu a vrátí novou revizi stavu. Revize z odpovědi předchozího znovuzařazení
    (`known`) ušetří čtení celého stavu (~700 kB); při konfliktu (mezitím zapsal někdo jiný) se zápis
    jednou zopakuje s čerstvou revizí ze stavu."""
    def fresh():
        return get(base, '/api/desktop-v3/state', {'project': project, 'workspace': workspace})['revision']

    row['revision'] = known if known is not None else fresh()
    try:
        return (requeue(base, project, workspace, row) or {}).get('revision')
    except HTTPError as error:
        if error.code != 409 or known is None:
            raise
    row['revision'] = fresh()
    return (requeue(base, project, workspace, row) or {}).get('revision')


def is_push(stdin_text):
    try:
        command = json.loads(stdin_text or '{}').get('tool_input', {}).get('command', '')
    except (ValueError, AttributeError):
        return False
    return bool(re.search(r'\bgit\b[^|;&]*\bpush\b', command or ''))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--repo', required=True, help='kořen git repa projektu')
    parser.add_argument('--node', default='', help='sektor (rodič karet); výchozí celé plátno')
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--branch', default='main')
    parser.add_argument('--base-url', default=os.environ.get(BASE_ENV))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--hook', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if args.hook and not is_push(sys.stdin.read()):
        return 0
    os.environ.setdefault('OPORA_AGENT_NAME', AGENT)
    try:
        if not args.base_url:
            raise ValueError('Chybí --base-url nebo ' + BASE_ENV + '.')
        base = base_url(args.base_url)
        rows = collect(base, args.project, args.workspace, args.repo, args.node, args.remote, args.branch)
        applied, errors = [], []
        if args.apply or args.hook:
            revision = None  # revize ze štíhlé odpovědi posledního znovuzařazení; jiný zápis ji zahodí
            for row in [row for row in rows if row['apply'] or row['retry']]:
                try:
                    if row['retry']:
                        revision = requeue_with_revision(base, args.project, args.workspace, row, revision)
                    else:
                        revision = None
                        apply(base, args.project, args.workspace, row)
                    applied.append(row['number'])
                except Exception as cause:  # noqa: BLE001 - jedna karta nesmí zastavit ostatní
                    revision = None
                    detail = _detail(cause) if isinstance(cause, HTTPError) else None
                    errors.append(f"{row['number']}: {detail or cause}")
            if applied:
                rows = collect(base, args.project, args.workspace, args.repo, args.node, args.remote, args.branch)
        if args.json:
            print(json.dumps({'rows': [{k: v for k, v in row.items() if k not in ('stages', 'evidence')} for row in rows],
                              'applied': applied, 'errors': errors}, ensure_ascii=False, indent=2))
        else:
            print(table(rows))
            if applied:
                print('\nAutomaticky provedeno (důkazy / znovu zařazená etapa): ' + ', '.join(applied))
            for error in errors:
                print('Chyba ' + error)
        return 1 if errors and not args.hook else 0
    except Exception as cause:  # noqa: BLE001 - hook nesmí spadnout
        print(json.dumps({'ok': False, 'error': str(cause)}, ensure_ascii=False), file=sys.stderr)
        return 0 if args.hook else 1


if __name__ == '__main__':
    sys.exit(main())
