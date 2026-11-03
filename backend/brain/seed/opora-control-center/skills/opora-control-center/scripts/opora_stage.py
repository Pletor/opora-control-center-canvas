"""Odevzdání etapy pipeline jedním příkazem: brief → lease → agent-output → release → ověření čtením.

`opora_stage.py --project P --workspace W --node N --stage STAGE_ID --agent JMÉNO (--passed|--failed)
 --note-file F [--idea "text" ...] [--check "id=příkaz=exit" ...] [--wait-prior] [--timeout S]`.

Postup (vše v popředí, nic na pozadí):
1. `--wait-prior`: čeká (time.sleep), až etapy před touto (u kritika před jeho kolem) nejsou todo/doing.
2. `lease claim` na kartu; obsazenou kartu (409) zkusí znovu nejvýš `--claim-tries`× po `--interval` s.
3. Čerstvý `node-brief` (revize, contextVersion, stávající evidence) a `agent-output` se `stages`,
   `evidence` (povinná: tests passed jen když všechny `--check` mají exit 0; review se tu nikdy
   nepovyšuje — chybí-li, je pending) a `ideas` (podněty k dalšímu vývoji, zdroj podle druhu etapy).
4. `lease release` vždy, i po chybě; nakonec `node-brief` ověří, že etapa má hlášený stav.
Kód 0 = zapsáno a ověřeno, 3 = konflikt (409: obsazeno, revize, pořadí, payload), 1 = jiná chyba.
Adresa jen loopback (`--base-url` nebo `OPORA_BASE_URL`), zápis jen přes povolené cesty `opora_write`.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opora_write import (
    AGENT_NAME,
    BASE_ENV,
    TIMEOUT,
    WRITE_ROUTES,
    _detail,
    _read,
    base_url,
)

SCHEMA = 'opora.agent-output/1'
EXIT_CONFLICT = 3
MAX_NOTE = 4000
MAX_IDEA = 1000
OPEN = ('todo', 'doing')
LEASE_TTL = 300


class Conflict(Exception):
    """HTTP 409 se srozumitelným detailem serveru."""


def actor(agent):
    return 'agent; name=' + (AGENT_NAME.sub('', agent).strip()[:80] or 'agent')


def get(base, route, params):
    return _read(Request(base + route + '?' + urlencode(params), headers={'Accept': 'application/json'}), TIMEOUT)


def post(base, route, payload, agent, lease=''):
    if route not in WRITE_ROUTES:
        raise ValueError('Cesta ' + route + ' není povolený zápis na plátno.')
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Origin': base,
               'X-Opora-Actor': actor(agent)}
    if re.fullmatch(r'[0-9a-f]{64}', lease):
        headers['X-Opora-Lease'] = lease
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    try:
        return _read(Request(base + route, data=data, headers=headers, method='POST'), TIMEOUT)
    except HTTPError as error:
        detail = _detail(error) or ('HTTP ' + str(error.code))
        if error.code == 409:
            raise Conflict(detail) from None
        raise ValueError(f'{route}: HTTP {error.code}: {detail}') from None


def parse_check(value):
    """`id=příkaz=exit`: id před prvním `=`, exit za posledním, příkaz smí `=` obsahovat."""
    check_id, sep, rest = value.partition('=')
    command, sep2, code = rest.rpartition('=')
    if not sep or not sep2 or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', check_id) or not command.strip():
        raise ValueError('--check má tvar id=příkaz=exit, např. unit=uv run pytest backend=0.')
    try:
        exit_code = int(code)
    except ValueError:
        raise ValueError('--check: exit musí být celé číslo.') from None
    return {'checkId': check_id, 'command': command.strip(), 'exitCode': exit_code, 'logUrl': '',
            'at': datetime.now(UTC).isoformat(timespec='seconds')}


def critic_start(stages, position):
    """Začátek kola kritiků (souvislé etapy `critic`) jako na serveru: kolo nečeká samo na sebe."""
    start = position
    while start > 0 and stages[start - 1]['kind'] == 'critic':
        start -= 1
    return start


def stage_of(brief, stage_id):
    stages = (brief.get('pipeline') or {}).get('stages') or []
    position = next((index for index, item in enumerate(stages) if item['id'] == stage_id), None)
    if position is None:
        raise ValueError(f'Etapa {stage_id} na kartě není (pipeline.stages v node-briefu).')
    return stages, position


def waiting_before(brief, stage_id):
    stages, position = stage_of(brief, stage_id)
    first = critic_start(stages, position) if stages[position]['kind'] == 'critic' else position
    return [item['title'] for item in stages[:first] if item['status'] in OPEN]


def source_of(stage):
    return 'critic:' + stage['lens'] if stage['kind'] == 'critic' else stage['kind']


def evidence_of(existing, checks):
    """Evidence pro výstup: stávající se nezhorší, testy jen z `--check`, review a merge nikdy nepovýší."""
    pending = {'status': 'pending', 'url': '', 'note': ''}
    base = existing if isinstance(existing, dict) and {'tests', 'review', 'merge', 'checksRun'} <= set(existing) else {}
    runs = {run['checkId']: run for run in base.get('checksRun', [])}
    runs.update({run['checkId']: run for run in checks})
    tests = base.get('tests', pending)
    if checks:
        failed = [run['checkId'] for run in checks if run['exitCode'] != 0]
        tests = {'status': 'failed' if failed else 'passed', 'url': '',
                 'note': ('neprošly: ' + ', '.join(failed)) if failed else
                 'prošly: ' + ', '.join(run['checkId'] for run in checks)}
    return {'tests': tests, 'review': base.get('review', pending), 'merge': base.get('merge', pending),
            'checksRun': list(runs.values())}


def brief_of(base, scope, node):
    return get(base, '/api/desktop-v3/node-brief', {**scope, 'nodeId': node})


def wait_prior(base, scope, node, stage_id, timeout, interval, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout
    while True:
        waiting = waiting_before(brief_of(base, scope, node), stage_id)
        if not waiting:
            return
        if clock() >= deadline:
            raise TimeoutError('Předchozí etapy pořád běží: ' + ', '.join(waiting) + '.')
        sleep(interval)


def claim(base, scope, node, agent, tries, interval, sleep=time.sleep):
    for attempt in range(tries):
        try:
            result = post(base, '/api/desktop-v3/lease',
                          {**scope, 'nodeId': node, 'op': 'claim', 'owner': agent, 'ttlSeconds': LEASE_TTL}, agent)
            return result['token']
        except Conflict:
            if attempt + 1 >= tries:
                raise
            sleep(interval)
    raise Conflict('Kartu se nepodařilo převzít.')


def submit(args, sleep=time.sleep, clock=time.monotonic):
    base = base_url(args.base_url or os.environ.get(BASE_ENV, '').strip())
    scope = {'project': args.project, 'workspace': args.workspace}
    with open(args.note_file, encoding='utf-8') as handle:
        note = handle.read().strip()
    if not note or len(note) > MAX_NOTE:
        raise ValueError(f'Předávka (--note-file) musí být neprázdný text do {MAX_NOTE} znaků.')
    if any(not text.strip() or len(text) > MAX_IDEA for text in args.idea):
        raise ValueError(f'--idea musí být neprázdný text do {MAX_IDEA} znaků.')
    checks = [parse_check(value) for value in args.check]
    if args.wait_prior:
        wait_prior(base, scope, args.node, args.stage, args.timeout, args.interval, sleep, clock)
    token = claim(base, scope, args.node, args.agent, args.claim_tries, args.interval, sleep)
    try:
        brief = brief_of(base, scope, args.node)
        stages, position = stage_of(brief, args.stage)
        request = brief['outputContract']['request']
        output = {'schema': SCHEMA, 'blocks': [], 'reports': [], 'done': {'proposed': False, 'note': ''},
                  'decisions': [],
                  'stages': [{'id': args.stage, 'status': 'passed' if args.passed else 'failed', 'note': note}],
                  'evidence': evidence_of(brief.get('evidence'), checks)}
        if args.idea:
            output['ideas'] = [{'text': text.strip(), 'source': source_of(stages[position])} for text in args.idea]
        saved = post(base, '/api/desktop-v3/agent-output',
                     {**scope, 'nodeId': args.node, 'expectedRevision': request['expectedRevision'],
                      'contextVersion': request['contextVersion'], 'agent': args.agent, 'output': output},
                     args.agent, token)
    finally:
        post(base, '/api/desktop-v3/lease', {**scope, 'nodeId': args.node, 'op': 'release', 'token': token}, args.agent)
    after = brief_of(base, scope, args.node)
    stages, position = stage_of(after, args.stage)
    status = output['stages'][0]['status']
    if stages[position]['status'] != status:
        raise ValueError(f'Ověření čtením selhalo: etapa má stav {stages[position]["status"]}, ne {status}.')
    pipeline = after.get('pipeline') or {}
    return {'ok': True, 'stage': args.stage, 'status': status, 'revision': saved.get('revision'),
            'tests': output['evidence']['tests']['status'], 'ideasOpen': len((after.get('ideas') or {}).get('open', [])),
            'next': (pipeline.get('current') or {}).get('id'), 'parallel': pipeline.get('parallel', []),
            'stuck': [item['id'] for item in pipeline.get('stuck', [])]}


def parser():
    out = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    out.add_argument('--project', required=True)
    out.add_argument('--workspace', required=True)
    out.add_argument('--node', required=True)
    out.add_argument('--stage', required=True, help='id etapy z node-brief pipeline.current nebo pipeline.parallel')
    out.add_argument('--agent', required=True, help='jméno relace <role>-<relace>; jiné než autor práce u review/kritika')
    status = out.add_mutually_exclusive_group(required=True)
    status.add_argument('--passed', action='store_true')
    status.add_argument('--failed', action='store_true', help='jen pro blokátor (pipeline.md, Kritici)')
    out.add_argument('--note-file', required=True, help='předávka další relaci (UTF-8 text)')
    out.add_argument('--idea', action='append', default=[], help='ne-blokující podnět k dalšímu vývoji (opakovatelné)')
    out.add_argument('--check', action='append', default=[], help='id=příkaz=exit (opakovatelné)')
    out.add_argument('--wait-prior', action='store_true', help='počkat, až předchozí etapy nejsou todo/doing')
    out.add_argument('--timeout', type=int, default=600, help='strop čekání --wait-prior v sekundách')
    out.add_argument('--interval', type=int, default=10, help='pauza mezi pokusy v sekundách')
    out.add_argument('--claim-tries', type=int, default=6, help='kolikrát zkusit převzít obsazenou kartu')
    out.add_argument('--base-url', help='http://127.0.0.1:PORT; výchozí ' + BASE_ENV)
    return out


def main(argv=None, sleep=time.sleep, clock=time.monotonic):
    args = parser().parse_args(argv)
    try:
        print(json.dumps(submit(args, sleep, clock), ensure_ascii=False, indent=2))
        return 0
    except Conflict as error:
        print('conflict: ' + str(error))
        print(json.dumps({'ok': False, 'conflict': True, 'detail': str(error)}, ensure_ascii=False), file=sys.stderr)
        return EXIT_CONFLICT
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
