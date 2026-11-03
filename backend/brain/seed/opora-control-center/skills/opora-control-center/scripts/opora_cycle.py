"""Booleovské ovládání cyklu Schránky pro agenty (docs/schranka-neurony.md §3, §9 body 8 a 9).

`opora_cycle.py <příkaz> --project P --workspace W …`, výstup vždy jeden krátký JSON na stdout:

- `next [--discipline D]` – další brána z fronty `/api/brief-vault/next` (nezávazná, bez rezervace).
- `propose FRAGMENT GATE (--json-file F | --json J) --note "…"` – návrh payloadu brány.
- `yes FRAGMENT GATE --note "…"` / `no FRAGMENT GATE --note "…"` – `op: gate` `value: true/false` bez payloadu.
- `reject FRAGMENT GATE --note "…"` – `op: reject-proposal`: zamítne poslední čekající návrh brány.
- `check FRAGMENT GATE [--json-file F]` – poradní `gate-check` (může vrátit `probability: null`).
- `lessons [--discipline D]` – živá poučení.
- `run-checks FRAGMENT --root DIR --tests DIR --executor A [--plan-score N] [--critic-rounds N] [--unexpected] [--note T]` –
  ověřovatel (docs/schranka-bunka.md §3 bod 5): spustí `synthesized.checks` bez shellu v DIR a podá `propose verified`
  s `actual.run`; vlastní aktér nesmí být `--executor`. Výstup kontrol na server nejde, do konzole jen posledních 2 000 znaků.

- `duel open|show|turn|score|decide|align …` – duel změny směru (docs/schranka-duel.md §5), vlastní parser (`duel -h`).

`expectedRevision` si skript načte sám (hlava `/next`, jinak detail fragmentu); `--revision N` ji připne na
revizi, kterou agent četl. Změní-li se mezitím, server vrátí 409 a nic se nezapíše.
Zápisy jdou přes `opora_write.post` (stejný allowlist, loopback, hlavička aktéra a lease, bez opakování).
`yes … placed` zapíše uložený plán na plátno rovnou; pojistkou je verze plátna, kterou backend uloží před
každým `placed` (§11). Aktér: `--actor`, jinak `OPORA_ACTOR`, jinak `OPORA_AGENT_NAME`.
`yes` odmítne potvrdit návrh téhož aktéra (kód 2).
Kódy: 0 ok, 1 chyba, 2 odmítnuto skriptem, 3 konflikt (HTTP 409).
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import tempfile
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parent))

import opora_read
import opora_write

ACTOR_ENV = 'OPORA_ACTOR'
GATES = ('scoped', 'weighed', 'synthesized', 'decided', 'planned', 'placed', 'verified', 'learned')
NO_PAYLOAD = ('scoped', 'planned', 'placed')
VAULT = '/api/brief-vault'
CHECK_ROUTE = '/api/brief-vault/gate-check'
EXIT_ERROR, EXIT_REFUSED, EXIT_CONFLICT = 1, 2, 3
CHECK_PROGRAMS = ('python', 'py', 'uv', 'pytest', 'npm', 'npx', 'node')
CHECK_FORBIDDEN = ('|', '&', ';', '>', '<', '`', '$(', '\\')
STRIPPED_FILES = ('conftest.py', 'pytest.ini', 'tox.ini', 'setup.cfg', 'sitecustomize.py', 'usercustomize.py')
CHECK_TIMEOUT, TAIL_CHARS = 600, 2000


class Refused(Exception):
    """Skript zápis odmítl dřív, než cokoli odešlo (vlastní návrh, návrh není vidět)."""


def actor_of(value):
    """Jméno aktéra: argument, `OPORA_ACTOR`, `OPORA_AGENT_NAME`; stejná očista jako hlavička zápisu."""
    return opora_write.actor_name(value if value is not None else (os.environ.get(ACTOR_ENV) or None))


class Cycle:
    def __init__(self, base, project, workspace, actor):
        self.base, self.actor = base, actor
        self.scope = {'project': project, 'workspace': workspace}

    def get(self, route, **params):
        return opora_read.request(self.base, route, {**self.scope, **{k: v for k, v in params.items() if v is not None}})

    def next(self, discipline=None):
        return self.get(VAULT + '/next', discipline=discipline)

    def head(self, fragment_id, gate, discipline=None):
        """Hlava fronty, pokud je to právě tato brána tohoto fragmentu; jinak None."""
        found = self.next(discipline)
        if (found.get('fragment') or {}).get('id') == fragment_id and found.get('gate') == gate:
            return found
        if discipline is None:
            # Bez --discipline může hlavu globální fronty držet jiná disciplína: zkus frontu disciplíny fragmentu.
            own = self.get(VAULT + '/fragment', id=fragment_id).get('effectiveDiscipline')
            if own:
                return self.head(fragment_id, gate, own)
        return None

    def revision(self, fragment_id, head=None, pinned=None):
        if pinned is not None:
            return pinned
        if head is not None:
            return head['fragment']['revision']
        return self.get(VAULT + '/fragment', id=fragment_id)['latestRevision']

    def write(self, payload):
        return opora_write.post(self.base, VAULT, {**payload, **self.scope}, actor=self.actor)

    def check(self, payload):
        """Poradní kontrola brány: POST, který nic nezapisuje (jen loopback, bez proxy a přesměrování)."""
        data = json.dumps({**payload, **self.scope}, ensure_ascii=False).encode('utf-8')
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Origin': self.base,
                   'X-Opora-Actor': opora_write.actor_header(self.actor)}
        return opora_read._read(Request(self.base + CHECK_ROUTE, data=data, headers=headers, method='POST'),
                                opora_read.POST_TIMEOUT)


def load_payload(args):
    if args.json_text is None and args.json_file is None:
        return None
    payload = json.loads(args.json_text) if args.json_text is not None else opora_write.load_payload(path=args.json_file)
    if not isinstance(payload, dict):
        raise TypeError('Payload musí být JSON objekt.')
    return payload


def cmd_next(cycle, args):
    return {'ok': True, **cycle.next(args.discipline)}


def cmd_lessons(cycle, args):
    found = cycle.get(VAULT + '/lessons', discipline=args.discipline)
    items = [{key: item.get(key) for key in ('id', 'discipline', 'kind', 'text', 'effectiveWeight', 'fragmentId')}
             for item in found.get('lessons', [])]
    return {'ok': True, 'lessons': items, 'count': len(items)}


def cmd_propose(cycle, args):
    if args.gate in NO_PAYLOAD:
        raise ValueError('Brána ' + args.gate + ' payload nemá a návrh nepotřebuje; použij yes.')
    payload = load_payload(args)
    if payload is None:
        raise ValueError('propose vyžaduje --json-file nebo --json s payloadem brány.')
    head = None if args.revision is not None else cycle.head(args.fragment, args.gate, args.discipline)
    revision = cycle.revision(args.fragment, head, args.revision)
    result = cycle.write({'op': 'propose', 'fragmentId': args.fragment, 'expectedRevision': revision,
                          'gate': args.gate, 'payload': payload, 'note': args.note})
    proposal = result.get('proposal') or {}
    return {'ok': True, 'op': 'propose', 'fragmentId': args.fragment, 'gate': args.gate, 'expectedRevision': revision,
            'proposal': {key: proposal.get(key) for key in ('id', 'by', 'revision')}}


def cmd_reject(cycle, args):
    """Zamítnutí čekajícího návrhu brány; `/next` pak vrátí `needs: proposal` (§9 bod 9, §11)."""
    head = None if args.revision is not None else cycle.head(args.fragment, args.gate, args.discipline)
    revision = cycle.revision(args.fragment, head, args.revision)
    result = cycle.write({'op': 'reject-proposal', 'fragmentId': args.fragment, 'expectedRevision': revision,
                          'gate': args.gate, 'note': args.note})
    out = {'ok': True, 'op': 'reject-proposal', 'fragmentId': args.fragment, 'gate': args.gate,
           'expectedRevision': revision}
    for key in ('proposal', 'rejected'):
        if key in result:
            out[key] = result[key]
    return out


def cmd_gate(cycle, args, value):
    head, proposal = None, None
    if value and args.gate not in NO_PAYLOAD:
        # Potvrzení bere poslední návrh; autor návrhu musí být vidět, jinak se nepotvrzuje (fail-closed).
        head = cycle.head(args.fragment, args.gate, args.discipline)
        if head is None:
            raise Refused('Brána ' + args.gate + ' fragmentu ' + args.fragment + ' není v hlavě /next, návrh nejde '
                          'ověřit; spusť next (případně s --discipline) a potvrzuj, co fronta vrátí.')
        proposal = head.get('proposal')
        if head.get('needs') != 'confirm' or not proposal:
            raise Refused('Brána ' + args.gate + ' nemá návrh (needs: proposal); nejdřív propose.')
        if proposal.get('by') == cycle.actor:
            raise Refused('Návrh podal stejný aktér (' + cycle.actor + '); vlastní návrh nepotvrzuj.')
    revision = cycle.revision(args.fragment, head, args.revision)
    body = {'op': 'gate', 'fragmentId': args.fragment, 'expectedRevision': revision, 'gate': args.gate,
            'value': value, 'note': args.note}
    result = cycle.write(body)
    out = {'ok': True, 'op': 'gate', 'fragmentId': args.fragment, 'gate': args.gate, 'value': value,
           'revision': (result.get('fragment') or {}).get('revision'), 'gates': result.get('gates'),
           'gateStep': result.get('gateStep'), 'deadEnd': result.get('deadEnd')}
    if proposal:
        out['proposal'] = {'id': proposal.get('id'), 'by': proposal.get('by')}
    for key in ('returnedTo', 'lesson', 'placement'):
        if key in result:
            out[key] = result[key]
    return 0, out


def cmd_check(cycle, args):
    payload = load_payload(args)
    head = None
    if payload is None and args.gate not in NO_PAYLOAD:
        head = cycle.head(args.fragment, args.gate, args.discipline)
        payload = (head or {}).get('proposal', {}).get('payload')
        if payload is None:
            raise Refused('Pro kontrolu chybí payload: dej --json-file, nebo brána musí mít návrh v hlavě /next.')
    revision = cycle.revision(args.fragment, head, args.revision)
    result = cycle.check({'fragmentId': args.fragment, 'expectedRevision': revision, 'gate': args.gate,
                          'payload': payload})
    return {'ok': True, 'fragmentId': args.fragment, 'gate': args.gate, 'expectedRevision': revision, **result}


def check_argv(command):
    """Příkaz kontroly -> argv. Stejná pravidla jako backend (program z allowlistu, žádné shellové znaky,
    žádná absolutní cesta ani `..`); co by server odmítl, se nespustí."""
    if not isinstance(command, str) or not command.strip() or len(command) > 300:
        raise Refused('Příkaz kontroly je prázdný nebo delší než 300 znaků.')
    if any(mark in command for mark in CHECK_FORBIDDEN):
        raise Refused('Příkaz kontroly obsahuje zakázaný znak (| & ; > < ` $(): ' + command)
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        raise Refused('Příkaz kontroly nejde rozdělit (neuzavřená uvozovka): ' + command) from None
    if not argv or argv[0].lower() not in CHECK_PROGRAMS:
        raise Refused('Příkaz kontroly musí začínat jedním z ' + ', '.join(CHECK_PROGRAMS) + ': ' + command)
    for token in argv[1:]:
        for part in [token] + re.split(r'[=,]', token):
            if part.startswith('/') or re.match(r'^[A-Za-z]:', part) or '..' in part:
                raise Refused('Příkaz kontroly nesmí mít absolutní cestu ani "..": ' + command)
    return argv


def tests_digest(tests):
    """Otisk obsahu složky s kontrolami: seřazené relativní cesty + obsah."""
    digest = hashlib.sha256()
    for path in sorted(item for item in tests.rglob('*') if item.is_file()):
        digest.update(path.relative_to(tests).as_posix().encode('utf-8') + b'\x00' + path.read_bytes() + b'\x00')
    return digest.hexdigest()


def prepare_copy(root, tests, target):
    """Kopie složky vykonavatele bez souborů, které mění chování pytestu, a přes ni zdroje kontrol z `--tests`."""
    shutil.copytree(root, target)
    for path in list(target.rglob('*')):
        if path.is_dir() and path.name == '.pytest_cache':
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file() and path.name in STRIPPED_FILES:
            path.unlink()
    shutil.copytree(tests, target, dirs_exist_ok=True)


def run_check(argv, root):
    """Jedna kontrola bez shellu: (exitCode, durationMs, výstup v bajtech). Timeout = 124, chybějící program = 127."""
    program = shutil.which(argv[0])
    started = time.monotonic()
    if program is None:
        return 127, 0, ('program nenalezen: ' + argv[0]).encode('utf-8')
    try:
        done = subprocess.run([program] + argv[1:], cwd=root, shell=False, capture_output=True, timeout=CHECK_TIMEOUT)
        code, output = done.returncode, (done.stdout or b'') + (done.stderr or b'')
    except subprocess.TimeoutExpired as error:
        code = 124
        output = (error.stdout or b'') + (error.stderr or b'') + b'\n[timeout]'
    return code, int((time.monotonic() - started) * 1000), output


def cmd_run_checks(cycle, args):
    """Ověřovatel (docs/schranka-bunka.md §3 bod 5): spustí kontroly a podá `propose verified` s `actual.run`."""
    if not args.fragment:
        raise ValueError('run-checks vyžaduje FRAGMENT.')
    if not args.root or not args.executor or not args.tests:
        raise ValueError('run-checks vyžaduje --root, --tests a --executor.')
    executor = opora_write.actor_name(args.executor)
    if executor == cycle.actor:
        raise Refused('Vykonavatel a ověřovatel nesmí být stejný aktér (' + executor + ').')
    root = Path(args.root)
    if not root.is_dir():
        raise ValueError('--root musí být existující složka: ' + args.root)
    tests_dir = Path(args.tests)
    if not tests_dir.is_dir():
        raise ValueError('--tests musí být existující složka: ' + args.tests)
    real_root, real_tests = root.resolve(), tests_dir.resolve()
    if real_root == real_tests or real_root in real_tests.parents or real_tests in real_root.parents:
        raise Refused('--tests a --root se nesmí překrývat (kontroly nesmí ležet ve složce vykonavatele).')
    found = cycle.get(VAULT + '/fragment', id=args.fragment)
    synthesized = (found.get('gateDetail') or {}).get('synthesized') or {}
    checks = (synthesized.get('payload') or {}).get('checks')
    if not isinstance(checks, list) or not checks:
        raise ValueError('Brána synthesized fragmentu nemá checks; není co spouštět.')
    plan = [(item.get('id'), item.get('command'), check_argv(item.get('command'))) for item in checks]
    revision = args.revision if args.revision is not None else found['latestRevision']
    results, report = [], []
    scratch = tempfile.TemporaryDirectory(prefix='opora-run-')
    try:
        work = Path(scratch.name) / 'work'
        prepare_copy(root, tests_dir, work)
        for check_id, command, argv in plan:
            code, duration, output = run_check(argv, str(work))
            results.append({'checkId': check_id, 'command': command, 'exitCode': code, 'durationMs': duration,
                            'outputSha256': hashlib.sha256(output).hexdigest()})
            report.append({'checkId': check_id, 'exitCode': code, 'durationMs': duration,
                           'tail': output.decode('utf-8', 'replace')[-TAIL_CHARS:]})
    finally:
        scratch.cleanup()
    tests = 'pass' if all(item['exitCode'] == 0 for item in results) else 'fail'
    actual = {'tests': tests, 'criticRounds': args.critic_rounds, 'unexpected': bool(args.unexpected),
              'run': {'executor': executor, 'verifier': cycle.actor, 'checks': results,
                      'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}}
    if args.plan_score is not None:
        actual['planScore'], actual['planApproved'] = args.plan_score, args.plan_score >= 8
    note = (args.note or '').strip() or 'run-checks: ' + tests + ' (' + str(len(results)) + ' kontrol)'
    cycle.write({'op': 'propose', 'fragmentId': args.fragment, 'expectedRevision': revision, 'gate': 'verified',
                 'payload': {'actual': actual}, 'note': note})
    return {'action': 'proposed', 'ok': True, 'fragmentId': args.fragment, 'expectedRevision': revision,
            'tests': tests, 'testsSha256': tests_digest(tests_dir), 'checks': report}


DUEL_KINDS = ('claim', 'grill', 'answer', 'concede', 'synthesis', 'note')
DUEL_SIDES = ('A', 'B', 'judge', 'human')
DUEL_SUBJECTS = ('fragment', 'node', 'project')
DUEL_ROUTE = VAULT + '/duel'


def text_of(inline, path, label):
    """Text z `--x` nebo `--x-file` (právě jedno z nich)."""
    if (inline is None) == (path is None):
        raise ValueError(label + ': zadej právě jedno z --' + label + ' a --' + label + '-file.')
    return inline if inline is not None else Path(path).read_text(encoding='utf-8')


def duel_state(found):
    """Duel z odpovědi GET; toleruje obal `fields.duel`."""
    duel = found.get('duel') or {}
    return (duel.get('fields') or {}).get('duel') or duel


def duel_authors(found):
    """Aktéři, kteří jsou autory některé výměny nebo challengeru duelu."""
    duel = duel_state(found)
    people = [duel.get('challenger') or {}] + [t for t in (duel.get('turns') or []) if isinstance(t, dict)]
    return {item.get('by') for item in people} - {None, ''}


def short_turn(turn):
    text = ' '.join(str(turn.get('text') or '').split())
    return {'id': turn.get('id'), 'side': turn.get('side'), 'kind': turn.get('kind'),
            'by': turn.get('by'), 'text': text[:117] + '...' if len(text) > 120 else text}


def duel_result(result, *keys):
    return {key: result[key] for key in keys if key in result}


def derived(result):
    """Krátký stav po tahu: p, n, onTurn, rounds, canDecide."""
    probability = result.get('probability') or {}
    return {'p': probability.get('p'), 'n': probability.get('n'), 'onTurn': result.get('onTurn'),
            'rounds': result.get('rounds'), 'canDecide': result.get('canDecide')}


def duel_revision(cycle, args):
    return cycle.revision(args.id, None, args.revision)


def cmd_duel_open(cycle, args):
    incumbent = {'text': text_of(args.incumbent, args.incumbent_file, 'incumbent')}
    if args.incumbent_ref:
        fragment, _, revision = args.incumbent_ref.rpartition(':')
        if not fragment or not revision.isdigit():
            raise ValueError('--incumbent-ref musí mít tvar FRAGMENT:REVIZE.')
        incumbent['ref'] = {'fragmentId': fragment, 'revision': int(revision)}
    body = {'op': 'duel-open', 'subject': {'kind': args.subject_kind, 'id': args.subject}, 'incumbent': incumbent,
            'challenger': {'text': text_of(args.challenger, args.challenger_file, 'challenger')},
            'scopeNodeId': args.scope}
    if args.discipline:
        body['discipline'] = args.discipline
    if args.note:
        body['note'] = args.note
    result = cycle.write(body)
    fragment = result.get('fragment') or {}
    return {'ok': True, 'op': 'duel-open', 'id': fragment.get('id'), 'revision': fragment.get('revision'),
            'status': (result.get('duel') or {}).get('status')}


def cmd_duel_show(cycle, args):
    found = cycle.get(DUEL_ROUTE, id=args.id)
    duel = duel_state(found)
    probability = found.get('probability') or {}
    trajectory = found.get('trajectory') or {}
    return {'ok': True, 'id': args.id, 'status': duel.get('status'), 'revision': (duel.get('fragment') or {}).get('revision'), 'p': probability.get('p'),
            'n': probability.get('n'), 'onTurn': found.get('onTurn'), 'rounds': found.get('rounds'),
            'canDecide': found.get('canDecide'), 'trajectory': trajectory.get('state'),
            'turns': [short_turn(t) for t in (duel.get('turns') or [])[-6:]]}


def cmd_duel_turn(cycle, args):
    body = {'op': 'duel-turn', 'fragmentId': args.id, 'expectedRevision': duel_revision(cycle, args),
            'side': args.side, 'kind': args.kind, 'text': text_of(args.text, args.text_file, 'text')}
    if args.ref:
        body['refs'] = list(args.ref)
    if args.evidence:
        evidence = []
        for item in args.evidence:
            source, sep, quote = item.partition('|')
            if not sep or not source.strip() or not quote.strip():
                raise ValueError('--evidence musí mít tvar "zdroj|citát": ' + item)
            evidence.append({'source': source.strip(), 'quote': quote.strip()})
        body['evidence'] = evidence
    result = cycle.write(body)
    return {'ok': True, 'op': 'duel-turn', 'fragmentId': args.id, 'expectedRevision': body['expectedRevision'],
            'turnId': (result.get('turn') or {}).get('id'), 'revision': (result.get('fragment') or {}).get('revision'),
            **derived(result)}


def cmd_duel_score(cycle, args):
    authors = duel_authors(cycle.get(DUEL_ROUTE, id=args.id))
    if cycle.actor in authors:
        raise Refused('Soudce (' + cycle.actor + ') je autorem výměny nebo challengeru duelu; hodnotí jiný aktér.')
    body = {'op': 'duel-score', 'fragmentId': args.id, 'expectedRevision': duel_revision(cycle, args),
            'turnId': args.turn, 'strength': args.strength, 'supports': args.supports}
    if args.rebutted_by:
        body['rebuttedBy'] = args.rebutted_by
    if args.evidence_ok:
        body['evidenceOk'] = True
    result = cycle.write(body)
    return {'ok': True, 'op': 'duel-score', 'fragmentId': args.id, 'expectedRevision': body['expectedRevision'],
            'scoreId': (result.get('score') or {}).get('id'), 'revision': (result.get('fragment') or {}).get('revision'),
            **derived(result)}


def cmd_duel_decide(cycle, args):
    body = {'op': 'duel-decide', 'fragmentId': args.id, 'expectedRevision': duel_revision(cycle, args)}
    if args.synthesis_turn:
        body['synthesisTurnId'] = args.synthesis_turn
    result = cycle.write(body)
    decision = result.get('decision') or {}
    applied = {'applied': bool(result.get('applied')), 'appliedRevision': decision.get('appliedRevision')}
    if decision.get('reason'):
        applied['appliedReason'] = decision['reason']  # proč se vítězný směr neuplatnil (karta, změna mezitím, keep)
    return {'ok': True, 'op': 'duel-decide', 'fragmentId': args.id, 'expectedRevision': body['expectedRevision'],
            'revision': (result.get('fragment') or {}).get('revision'), 'outcome': decision.get('outcome'),
            'p': (result.get('probability') or {}).get('p'), **applied,
            **duel_result(result, 'decision', 'lesson', 'lessonSkipped')}


def cmd_duel_align(cycle, args):
    body = {'op': 'vision-align', 'score': args.score, 'note': args.note, 'scopeNodeId': args.scope,
            'duelId': args.duel}
    result = cycle.write(body)
    return {'ok': True, 'op': 'vision-align', **duel_result(result, 'point', 'trajectory')}


def duel_parser():
    parser = argparse.ArgumentParser(prog='opora_cycle.py duel', description='Duel změny směru (docs/schranka-duel.md).')
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--project', required=True)
    common.add_argument('--workspace', required=True)
    common.add_argument('--actor', help='jméno aktéra; výchozí ' + ACTOR_ENV + ', pak ' + opora_write.AGENT_ENV)
    common.add_argument('--base-url', help='http://127.0.0.1:PORT; výchozí ' + opora_write.BASE_ENV)
    common.add_argument('--revision', type=int, help='připne expectedRevision na revizi, kterou agent četl')
    sub = parser.add_subparsers(dest='action', required=True)
    opened = sub.add_parser('open', parents=[common])
    opened.add_argument('--subject-kind', required=True, choices=DUEL_SUBJECTS)
    opened.add_argument('--subject', required=True)
    opened.add_argument('--incumbent')
    opened.add_argument('--incumbent-file')
    opened.add_argument('--incumbent-ref', help='FRAGMENT:REVIZE platného směru')
    opened.add_argument('--challenger')
    opened.add_argument('--challenger-file')
    opened.add_argument('--scope', required=True, help='scopeNodeId')
    opened.add_argument('--discipline')
    opened.add_argument('--note')
    sub.add_parser('show', parents=[common]).add_argument('id')
    turn = sub.add_parser('turn', parents=[common])
    turn.add_argument('id')
    turn.add_argument('--side', required=True, choices=DUEL_SIDES)
    turn.add_argument('--kind', required=True, choices=DUEL_KINDS)
    turn.add_argument('--text')
    turn.add_argument('--text-file')
    turn.add_argument('--ref', action='append', help='id výměny, na kterou navazuje (opakovatelné)')
    turn.add_argument('--evidence', action='append', help='"zdroj|citát" (opakovatelné)')
    score = sub.add_parser('score', parents=[common])
    score.add_argument('id')
    score.add_argument('--turn', required=True)
    score.add_argument('--strength', required=True, type=int, choices=range(0, 11), metavar='0-10')
    score.add_argument('--supports', required=True, choices=('A', 'B'))
    score.add_argument('--rebutted-by')
    score.add_argument('--evidence-ok', action='store_true', help='soudce ověřil doložení výměny (bonus ×1.5)')
    decide = sub.add_parser('decide', parents=[common])
    decide.add_argument('id')
    decide.add_argument('--synthesis-turn', help='id výměny synthesis ohodnocené soudcem (nutné při výsledku synthesis)')
    align = sub.add_parser('align', parents=[common])
    align.add_argument('--score', required=True, type=int, choices=range(0, 11), metavar='0-10')
    align.add_argument('--note', required=True)
    align.add_argument('--scope', required=True, help='scopeNodeId')
    align.add_argument('--duel', required=True, help='id rozhodnutého duelu (jeden bod na duel)')
    return parser


def run_duel(args):
    base = opora_write.base_url(args.base_url or os.environ.get(opora_write.BASE_ENV, '').strip())
    cycle = Cycle(base, args.project, args.workspace, actor_of(args.actor))
    handler = {'open': cmd_duel_open, 'show': cmd_duel_show, 'turn': cmd_duel_turn, 'score': cmd_duel_score,
               'decide': cmd_duel_decide, 'align': cmd_duel_align}[args.action]
    return 0, handler(cycle, args)


def parser_of():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['next', 'propose', 'yes', 'no', 'reject', 'check', 'lessons', 'run-checks'])
    parser.add_argument('fragment', nargs='?')
    parser.add_argument('gate', nargs='?', choices=GATES)
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--discipline')
    parser.add_argument('--note')
    parser.add_argument('--json', dest='json_text')
    parser.add_argument('--json-file')
    parser.add_argument('--revision', type=int, help='připne expectedRevision na revizi, kterou agent četl')
    parser.add_argument('--root', help='run-checks: pracovní složka vykonavatele')
    parser.add_argument('--tests', help='run-checks: složka se zdroji kontrol (pevně daná před výkonem, mimo --root)')
    parser.add_argument('--executor', help='run-checks: aktér, který artefakt vytvořil (nesmí být ověřovatel)')
    parser.add_argument('--plan-score', type=int, choices=range(0, 11), metavar='0-10')
    parser.add_argument('--critic-rounds', type=int, default=0, choices=range(0, 4), metavar='0-3')
    parser.add_argument('--unexpected', action='store_true')
    parser.add_argument('--actor', help='jméno aktéra; výchozí ' + ACTOR_ENV + ', pak ' + opora_write.AGENT_ENV)
    parser.add_argument('--base-url', help='http://127.0.0.1:PORT; výchozí ' + opora_write.BASE_ENV)
    return parser


def run(args):
    if args.command == 'run-checks' and args.gate:
        raise ValueError('run-checks nebere GATE.')
    if args.command in ('propose', 'yes', 'no', 'reject', 'check') and not (args.fragment and args.gate):
        raise ValueError(args.command + ' vyžaduje FRAGMENT a GATE.')
    if args.command in ('next', 'lessons') and args.fragment:
        raise ValueError(args.command + ' nebere FRAGMENT ani GATE.')
    if args.command in ('propose', 'yes', 'no', 'reject') and not (args.note or '').strip():
        raise ValueError(args.command + ' vyžaduje --note (proč).')
    if args.command in ('yes', 'no', 'reject') and (args.json_text is not None or args.json_file is not None):
        raise ValueError(args.command + ' je jen ano/ne bez payloadu; payload patří do propose.')
    base = opora_write.base_url(args.base_url or os.environ.get(opora_write.BASE_ENV, '').strip())
    cycle = Cycle(base, args.project, args.workspace, actor_of(args.actor))
    if args.command in ('yes', 'no'):
        return cmd_gate(cycle, args, args.command == 'yes')
    handler = {'next': cmd_next, 'lessons': cmd_lessons, 'propose': cmd_propose, 'reject': cmd_reject,
               'check': cmd_check, 'run-checks': cmd_run_checks}[args.command]
    return 0, handler(cycle, args)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    is_duel = bool(argv) and argv[0] == 'duel'
    args = duel_parser().parse_args(argv[1:]) if is_duel else parser_of().parse_args(argv)
    try:
        code, out = run_duel(args) if is_duel else run(args)
    except Refused as error:
        code, out = EXIT_REFUSED, {'ok': False, 'refused': True, 'error': str(error)}
    except HTTPError as error:
        detail = opora_write._detail(error)
        if error.code == 409:
            code, out = EXIT_CONFLICT, {'ok': False, 'conflict': True, 'error': 'conflict',
                                        'note': 'Nic se nezapsalo; načti znovu (next) a rozhodni znovu.'}
        else:
            code, out = EXIT_ERROR, {'ok': False, 'error': 'HTTP ' + str(error.code)}
        if detail:
            out['detail'] = detail
    except (URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, UnicodeError) as error:
        code, out = EXIT_ERROR, {'ok': False, 'error': str(error)}
    if not is_duel and args.command == 'run-checks' and code:
        out = {'action': 'error', **out}
    print(json.dumps(out, ensure_ascii=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
