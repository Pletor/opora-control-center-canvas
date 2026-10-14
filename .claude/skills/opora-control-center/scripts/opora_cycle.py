"""Booleovské ovládání cyklu Schránky pro agenty (docs/schranka-neurony.md §3, §9 body 8 a 9).

`opora_cycle.py <příkaz> --project P --workspace W …`, výstup vždy jeden krátký JSON na stdout:

- `next [--discipline D]` – další brána z fronty `/api/brief-vault/next` (nezávazná, bez rezervace).
- `propose FRAGMENT GATE (--json-file F | --json J) --note "…"` – návrh payloadu brány.
- `yes FRAGMENT GATE --note "…"` / `no FRAGMENT GATE --note "…"` – `op: gate` `value: true/false` bez payloadu.
- `reject FRAGMENT GATE --note "…"` – `op: reject-proposal`: zamítne poslední čekající návrh brány.
- `check FRAGMENT GATE [--json-file F]` – poradní `gate-check` (může vrátit `probability: null`).
- `lessons [--discipline D]` – živá poučení.

`expectedRevision` si skript načte sám (hlava `/next`, jinak detail fragmentu); `--revision N` ji připne na
revizi, kterou agent četl. Změní-li se mezitím, server vrátí 409 a nic se nezapíše.
Zápisy jdou přes `opora_write.post` (stejný allowlist, loopback, hlavička aktéra a lease, bez opakování).
`yes … placed` zapíše uložený plán na plátno rovnou; pojistkou je verze plátna, kterou backend uloží před
každým `placed` (§11). Aktér: `--actor`, jinak `OPORA_ACTOR`, jinak `OPORA_AGENT_NAME`.
`yes` odmítne potvrdit návrh téhož aktéra (kód 2).
Kódy: 0 ok, 1 chyba, 2 odmítnuto skriptem, 3 konflikt (HTTP 409).
"""
import argparse
import json
import os
import sys
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


def parser_of():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['next', 'propose', 'yes', 'no', 'reject', 'check', 'lessons'])
    parser.add_argument('fragment', nargs='?')
    parser.add_argument('gate', nargs='?', choices=GATES)
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--discipline')
    parser.add_argument('--note')
    parser.add_argument('--json', dest='json_text')
    parser.add_argument('--json-file')
    parser.add_argument('--revision', type=int, help='připne expectedRevision na revizi, kterou agent četl')
    parser.add_argument('--actor', help='jméno aktéra; výchozí ' + ACTOR_ENV + ', pak ' + opora_write.AGENT_ENV)
    parser.add_argument('--base-url', help='http://127.0.0.1:PORT; výchozí ' + opora_write.BASE_ENV)
    return parser


def run(args):
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
               'check': cmd_check}[args.command]
    return 0, handler(cycle, args)


def main(argv=None):
    args = parser_of().parse_args(argv)
    try:
        code, out = run(args)
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
    print(json.dumps(out, ensure_ascii=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
