"""Klient OporaHubu pro agenta: stav pro agenty (ETag), výběr akce, běh karty a slot review.

`opora_hub.py <příkaz> --project P --workspace W [--base-url http://127.0.0.1:PORT]`

Čtení:  `state` (GET agent-state s `If-None-Match`; 304 vrátí uloženou kopii), `actions`, `pick`,
        `events` (feed událostí).
Běh:    `claim --action-id ID` (čerstvý agent-state → akce `claim` ve stavu `ready` → kontext v2 → claim),
        `assignment`, `heartbeat`, `results --result-file F`, `release`.
Review: `review-claim`, `review-heartbeat`, `review-submit --submission-file F`, `review-release`.

Token běhu i slotu review se nikdy nevypisuje: leží v soukromém souboru (0600) ve složce
`OPORA_HUB_STATE_DIR` (výchozí `~/.opora/hub`) a skript ho čte sám. Blokovanou akci skript
nepošle (kód 5) a stejné ID akce se po odmítnutí neopakuje. Kód 3 = 409: znovu načti `state`.
Adresa je jen loopback, bez proxy a bez přesměrování (jako `opora_write.py`).
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request

import opora_write

HUB = '/api/oporahub'
STATE_DIR_ENV = 'OPORA_HUB_STATE_DIR'
EXIT_CONFLICT, EXIT_NONE, EXIT_REFUSED = 3, 4, 5
STEP_STATUSES = ('done', 'failed', 'skipped')
SLIM = {'assignment': 'omit'}


class Refused(Exception):
    """Krok, který agent nesmí udělat (blokovaná akce, lidská akce, chybějící feed)."""


def state_dir():
    path = Path(os.environ.get(STATE_DIR_ENV) or Path.home() / '.opora' / 'hub')
    path.mkdir(parents=True, exist_ok=True)
    return path


def _private_write(path, value):
    """Soubor s tokenem: jen vlastník; existující se přepíše bez změny práv na čitelná."""
    data = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)


def _bundle_path(kind, identifier):
    safe = ''.join(ch for ch in identifier if ch.isalnum() or ch in '_-')[:120]
    if not safe:
        raise ValueError('Neplatné ID ' + kind + '.')
    return state_dir() / f'{kind}-{safe}.json'


def load_bundle(kind, identifier):
    path = _bundle_path(kind, identifier)
    if not path.is_file():
        raise ValueError(f'Chybí soukromý záznam {kind} {identifier}; převzal ho tento agent?')
    return json.loads(path.read_text('utf-8'))


def _headers(base, extra=None):
    return {'Accept': 'application/json', 'X-Opora-Actor': opora_write.actor_header(), 'Origin': base, **(extra or {})}


def _call(base, method, route, payload=None, params=None, headers=None):
    """Jediné síťové volání skriptu; vrací (status, tělo, hlavičky)."""
    url = base + route + ('?' + urlencode(params) if params else '')
    data = None
    sent = _headers(base, headers)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        sent['Content-Type'] = 'application/json'
    req = Request(url, data=data, headers=sent, method=method)
    try:
        with opora_write._open(req, opora_write.TIMEOUT) as response:
            body = response.read(opora_write.MAX_BYTES + 1)
            if len(body) > opora_write.MAX_BYTES:
                raise ValueError('Odpověď překročila limit 8 MiB.')
            return response.status, (json.loads(body) if body else None), dict(response.headers.items())
    except HTTPError as error:
        if error.code == 304:
            return 304, None, dict(error.headers.items()) if error.headers else {}
        raise


# --- stav pro agenty -------------------------------------------------------------------------

def _cache_path(project, workspace):
    return state_dir() / f'agent-state-{quote(project, safe="")}-{quote(workspace, safe="")}.json'


def agent_state(base, project, workspace, fresh=False):
    """GET agent-state; s uloženým ETagem pošle `If-None-Match` a 304 vrátí uloženou kopii."""
    cache = _cache_path(project, workspace)
    cached = json.loads(cache.read_text('utf-8')) if cache.is_file() and not fresh else None
    extra = {'If-None-Match': cached['etag']} if cached and cached.get('etag') else None
    status, body, headers = _call(base, 'GET', HUB + '/agent-state',
                                  params={'project': project, 'workspace': workspace}, headers=extra)
    if status == 304 and cached:
        return cached['body'], True
    etag = {k.lower(): v for k, v in headers.items()}.get('etag')
    if etag:
        cache.write_text(json.dumps({'etag': etag, 'body': body}, ensure_ascii=False), 'utf-8')
    return body, False


def ready_actions(state, verb=None, target=None, include_blocked=False):
    """Akce v pořadí serveru (`VERB_ORDER`, pak `targetId`); bez `include_blocked` jen `ready`."""
    return [action for action in state.get('actions', [])
            if (include_blocked or action.get('status') == 'ready')
            and (verb is None or action.get('verb') == verb)
            and (target is None or action.get('targetId') == target)]


def find_action(state, action_id):
    action = next((item for item in state.get('actions', []) if item.get('id') == action_id), None)
    if action is None:
        raise Refused(f'Akce {action_id} v aktuálním agent-state není (hlava se posunula); vyber znovu přes pick.')
    if action.get('status') != 'ready':
        raise Refused(f'Akce {action_id} je {action.get("status")}/{action.get("blockReason")}; blokovanou akci neopakuj.')
    return action


def summary(state, card=None):
    cards = [item for item in state.get('cards', []) if card is None or item.get('nodeId') == card]
    return {'heads': state.get('heads'),
            'stages': [item for item in state.get('stages', []) if item.get('health') != 'ok'],
            'decisions': state.get('decisions', []),
            'ready': [{k: a.get(k) for k in ('id', 'verb', 'targetId', 'path')} for a in ready_actions(state)],
            'blocked': len(state.get('actions', [])) - len(ready_actions(state)),
            'cards': cards, 'truncated': state.get('truncated', False)}


# --- běh karty --------------------------------------------------------------------------------

def claim(base, project, workspace, action_id, ttl, context_version=2):
    """Čerstvý agent-state → akce `claim` ready → kontext → claim; token jde jen do soukromého souboru."""
    state, _ = agent_state(base, project, workspace, fresh=True)
    action = find_action(state, action_id)
    if action.get('verb') != 'claim':
        raise Refused(f'Akce {action_id} je {action.get("verb")}, ne claim.')
    node = action['targetId']
    scope = {'project': project, 'workspace': workspace}
    if context_version == 2:
        _, ctx, _ = _call(base, 'POST', HUB + '/executions/context',
                          {**scope, 'nodeId': node, 'contextProtocolVersion': 2})
    else:
        _, ctx, _ = _call(base, 'GET', HUB + '/executions/context', params={**scope, 'nodeId': node})
    if not ctx.get('available'):
        raise Refused('Karta není k převzetí: ' + str(ctx.get('unavailableReason')))
    payload = {**scope, 'nodeId': node, 'expectedAcceptedHead': ctx['acceptedHead'],
               'expectedContextVersion': ctx['contextVersion'], 'requestId': uuid.uuid4().hex, 'ttlSeconds': ttl}
    if ctx.get('executionProtocolVersion') == 2:
        budget = ctx.get('budget') or {}
        payload |= {'expectedBudgetPolicyHead': budget.get('policyHead'),
                    'previousExecutionId': budget.get('latestExecutionId')}
    if context_version == 2:
        payload['contextProtocolVersion'] = 2
    # `assignment=omit`: zadání se čte jednou přes `assignment`, claim a heartbeat ho nevracejí.
    _, lease, _ = _call(base, 'POST', HUB + '/executions/claim', payload, params=SLIM)
    bundle = {'executionId': lease['executionId'], 'project': project, 'workspace': workspace, 'nodeId': node,
              'actionId': action_id, 'token': lease['token'], 'epoch': lease['epoch'],
              'expiresAt': lease['expiresAt'], 'acceptedRevision': lease['acceptedRevision'],
              'contextProtocolVersion': lease.get('contextProtocolVersion', 1),
              'resultRequestId': uuid.uuid4().hex}
    _private_write(_bundle_path('execution', lease['executionId']), bundle)
    return {k: v for k, v in bundle.items() if k not in ('token', 'resultRequestId')} | {'budget': lease.get('budget')}


def assignment(base, execution, out=None):
    bundle = load_bundle('execution', execution)
    _, value, _ = _call(base, 'GET', f'{HUB}/executions/{execution}/assignment',
                        params={'project': bundle['project'], 'workspace': bundle['workspace']},
                        headers={'X-Opora-Execution-Token': bundle['token']})
    target = Path(out) if out else _bundle_path('assignment', execution)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')
    return {'executionId': execution, 'file': str(target), 'steps': steps_of(value)}


def steps_of(value):
    """`spec.steps` přijatého zadání ze snímku; jinak prázdný seznam."""
    found = []

    def walk(item):
        if isinstance(item, dict):
            steps = item.get('steps')
            if isinstance(steps, list) and steps and all(isinstance(s, dict) and 'acceptance' in s for s in steps):
                found.extend(steps)
                return
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return [{k: s.get(k) for k in ('id', 'order', 'title', 'dependsOn', 'acceptance', 'files')} for s in found]


def _token_body(bundle, **extra):
    return {'project': bundle['project'], 'workspace': bundle['workspace'],
            'token': bundle['token'], 'epoch': bundle['epoch'], **extra}


def heartbeat(base, execution, ttl):
    bundle = load_bundle('execution', execution)
    _, value, _ = _call(base, 'POST', f'{HUB}/executions/{execution}/heartbeat', _token_body(bundle, ttlSeconds=ttl),
                        params=SLIM)
    return {k: v for k, v in (value or {}).items() if k != 'token'}


def release(base, execution):
    bundle = load_bundle('execution', execution)
    _, value, _ = _call(base, 'POST', f'{HUB}/executions/{execution}/release', _token_body(bundle))
    return {k: v for k, v in (value or {}).items() if k != 'token'}


def check_result(result):
    """Tvar výsledku podle execution-prompt agent-office; `stepResults` volitelně."""
    if not isinstance(result, dict) or not isinstance(result.get('summary'), str) or not result['summary'].strip():
        raise ValueError('Výsledek potřebuje neprázdné summary.')
    steps = result.get('stepResults', [])
    if not isinstance(steps, list):
        raise TypeError('stepResults musí být seznam.')
    seen = set()
    for item in steps:
        if not isinstance(item, dict) or not isinstance(item.get('stepId'), str) or item.get('status') not in STEP_STATUSES:
            raise ValueError('Každý stepResults potřebuje stepId a status done|failed|skipped.')
        if item['stepId'] in seen:
            raise ValueError('Krok ' + item['stepId'] + ' je ve stepResults dvakrát.')
        seen.add(item['stepId'])
        if not isinstance(item.get('evidence', {}), dict):
            raise TypeError('evidence kroku je objekt {checks?, commits?, notes}.')
    checks = (result.get('selfChecks') or {}).get('checks', [])
    for check in checks:
        if check.get('status') == 'passed' and check.get('exitCode') != 0:
            raise ValueError('Kontrola ' + str(check.get('name')) + ': passed jen s exitCode 0.')
    return result


def results(base, execution, result_file):
    bundle = load_bundle('execution', execution)
    result = check_result(json.loads(Path(result_file).read_text('utf-8')))
    # Stejné requestId z privátního záznamu: opakování stejného souboru je idempotentní.
    _, value, _ = _call(base, 'POST', f'{HUB}/executions/{execution}/results',
                        _token_body(bundle, requestId=bundle['resultRequestId'], result=result))
    return value


# --- slot review ------------------------------------------------------------------------------

def review_claim(base, project, workspace, ttl, role=None):
    payload = {'project': project, 'workspace': workspace, 'requestId': uuid.uuid4().hex, 'ttlSeconds': ttl}
    if role:
        payload['role'] = role
    _, value, _ = _call(base, 'POST', HUB + '/review-jobs/claim', payload)
    task = value.get('task')
    if not task:
        return {'task': None, 'serverNow': value.get('serverNow')}
    slot = f"{task['reviewJobId']}.{task['taskId']}"
    _private_write(_bundle_path('review', slot.replace('.', '__')),
                   {'project': project, 'workspace': workspace, 'reviewJobId': task['reviewJobId'],
                    'taskId': task['taskId'], 'token': task['token'], 'epoch': task['epoch'],
                    'submitRequestId': uuid.uuid4().hex})
    public = {k: v for k, v in task.items() if k != 'token'}
    target = _bundle_path('review-task', slot.replace('.', '__'))
    target.write_text(json.dumps(public, ensure_ascii=False, indent=2), 'utf-8')
    return {'slot': slot, 'role': task['role'], 'kind': task['job'].get('kind'), 'headSha': task['job'].get('headSha'),
            'sinceSha': task['job'].get('sinceSha'), 'expiresAt': task['expiresAt'], 'file': str(target)}


def _review(slot):
    bundle = load_bundle('review', slot.replace('.', '__'))
    return bundle, f"{HUB}/review-jobs/{bundle['reviewJobId']}/tasks/{bundle['taskId']}"


def review_heartbeat(base, slot, ttl):
    bundle, route = _review(slot)
    return _call(base, 'POST', route + '/heartbeat', _token_body(bundle, ttlSeconds=ttl))[1]


def review_release(base, slot):
    bundle, route = _review(slot)
    return _call(base, 'POST', route + '/release', _token_body(bundle))[1]


def review_submit(base, slot, submission_file):
    bundle, route = _review(slot)
    submission = json.loads(Path(submission_file).read_text('utf-8'))
    if not isinstance(submission, dict) or not ({'findings', 'fixed'} & set(submission) or 'votes' in submission):
        raise ValueError('Odevzdání hledače je {findings, fixed}, ověřovatele {votes}.')
    return _call(base, 'POST', route + '/submit',
                 _token_body(bundle, requestId=bundle['submitRequestId'], submission=submission))[1]


# --- události ---------------------------------------------------------------------------------

def events(base, project, workspace, since=None, limit=100):
    params = {'project': project, 'workspace': workspace, 'limit': limit}
    if since:
        params['since'] = since
    try:
        return _call(base, 'GET', HUB + '/events', params=params)[1]
    except HTTPError as error:
        if error.code in (404, 405):
            raise Refused('Feed událostí na tomto (starším) serveru není; čti agent-state.')
        raise


# --- CLI --------------------------------------------------------------------------------------

def run(args, base):
    scope = (args.project, args.workspace)
    if args.command == 'state':
        state, cached = agent_state(base, *scope, fresh=args.fresh)
        return state if args.raw else {'unchanged': cached, **summary(state, args.card)}
    if args.command == 'actions':
        state, _ = agent_state(base, *scope)
        return ready_actions(state, args.verb, args.target, args.all)
    if args.command == 'pick':
        state, _ = agent_state(base, *scope, fresh=True)
        found = ready_actions(state, args.verb, args.target)
        if not found:
            raise LookupError('Žádná ready akce ' + (args.verb or '') + '.')
        return found[0]
    if args.command == 'claim':
        return claim(base, *scope, args.action_id, args.ttl, args.context_version)
    if args.command == 'assignment':
        return assignment(base, args.execution, args.out)
    if args.command == 'heartbeat':
        return heartbeat(base, args.execution, args.ttl)
    if args.command == 'release':
        return release(base, args.execution)
    if args.command == 'results':
        return results(base, args.execution, args.result_file)
    if args.command == 'review-claim':
        return review_claim(base, *scope, args.ttl, args.role)
    if args.command == 'review-heartbeat':
        return review_heartbeat(base, args.slot, args.ttl)
    if args.command == 'review-release':
        return review_release(base, args.slot)
    if args.command == 'review-submit':
        return review_submit(base, args.slot, args.submission_file)
    return events(base, *scope, args.since, args.limit)


COMMANDS = ['state', 'actions', 'pick', 'claim', 'assignment', 'heartbeat', 'results', 'release',
            'review-claim', 'review-heartbeat', 'review-submit', 'review-release', 'events']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=COMMANDS)
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--base-url', help='http://127.0.0.1:PORT; výchozí ' + opora_write.BASE_ENV)
    parser.add_argument('--raw', action='store_true', help='state: celý dokument')
    parser.add_argument('--fresh', action='store_true', help='state: bez If-None-Match')
    parser.add_argument('--card', help='state: jen etapa této karty')
    parser.add_argument('--verb', help='actions/pick: sloveso akce (claim, review.claim, …)')
    parser.add_argument('--target', help='actions/pick: targetId akce')
    parser.add_argument('--all', action='store_true', help='actions: i blokované')
    parser.add_argument('--action-id', help='claim: stabilní ID akce z pick')
    parser.add_argument('--context-version', type=int, choices=[1, 2], default=2,
                        help='claim: 2 (výchozí); 1 jen na výslovný pokyn člověka, nikdy jako tichý fallback')
    parser.add_argument('--ttl', type=int, default=900, help='claim/heartbeat: 30–3600 s')
    parser.add_argument('--execution', help='ID běhu z claim')
    parser.add_argument('--out', help='assignment: kam uložit neměnné zadání')
    parser.add_argument('--result-file', help='results: JSON výsledku')
    parser.add_argument('--role', choices=['finder', 'voter'])
    parser.add_argument('--slot', help='review-*: slot z review-claim (reviewJobId.taskId)')
    parser.add_argument('--submission-file', help='review-submit: JSON odevzdání')
    parser.add_argument('--since', help='events: kurzor')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args(argv)
    try:
        base = opora_write.base_url(args.base_url or os.environ.get(opora_write.BASE_ENV, '').strip())
        print(json.dumps(run(args, base), ensure_ascii=True, indent=2))
        return 0
    except LookupError as error:
        print(json.dumps({'ok': False, 'none': True, 'error': str(error)}, ensure_ascii=True), file=sys.stderr)
        return EXIT_NONE
    except Refused as error:
        print(json.dumps({'ok': False, 'refused': True, 'error': str(error)}, ensure_ascii=True), file=sys.stderr)
        return EXIT_REFUSED
    except HTTPError as error:
        detail = opora_write._detail(error)
        out = {'ok': False, 'error': 'HTTP ' + str(error.code), 'detail': detail}
        if error.code == 409:
            out['note'] = 'Konflikt: znovu načti state (--fresh) a vyber akci podle nového ID; stejný požadavek neopakuj.'
        if error.code in (403, 428):
            out['note'] = 'Patří člověku nebo chybí identita (OPORA_AGENT_NAME); neobcházej.'
        print(json.dumps(out, ensure_ascii=True), file=sys.stderr)
        return EXIT_CONFLICT if error.code == 409 else EXIT_REFUSED if error.code in (403, 428) else 1
    except (URLError, TimeoutError, OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
