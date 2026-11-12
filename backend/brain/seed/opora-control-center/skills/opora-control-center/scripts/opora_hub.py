"""Klient OporaHubu pro agenta: stav pro agenty (ETag), výběr akce, běh karty a slot review.

`opora_hub.py <příkaz> --project P --workspace W [--base-url http://127.0.0.1:PORT]`

Karta:  `start --node N` (kontext, claim a zadání jedním voláním) → práce + commit s `Opora-Node: N` →
        `deliver --execution E --summary T [--step s1:"pozn."]... [--check "npm test=green"]... [--commit SHA]
        [--no-close] [--json -]` (kroky, výsledek, lokální sloučení, kontroly a uzavření jedním voláním).
Čtení:  `state` (GET agent-state s `If-None-Match`; 304 vrátí uloženou kopii), `actions`, `pick`,
        `events` (feed událostí).
Běh:    `claim --action-id ID` (čerstvý agent-state → akce `claim` ve stavu `ready` → kontext v2 → claim),
        `assignment`, `heartbeat`, `step --step-id S --status done|failed|skipped --notes T`
        (průběžný krok hned po jeho commitu), `results --result-file F`, `release`.
Review: `review-claim`, `review-heartbeat`, `review-submit --submission-file F`, `review-release`.
Akce:   `act --action-id ID` provede akci z agent-state přesně podle `method/path/preconditions` (propose_graph,
        accept_baseline, accept, rebase, claim, review, close_card, verification.fix, review.claim); lidské akce jen
        když je agent-state při `autonomy.full` nabízí jako `ready`. Výstup nese `next` = další ready akce.
        Dávka: `act --action-id A --action-id B …` nebo `act --all-ready --verb V [--verb V2] [--target N]…`
        (opora_act_batch.py: klíč (verb, targetId), `{done, skipped, next}`, cizí změna = kód 3 s `changed`).
        `local-merge --execution E --commit SHA` (projekt bez GitHubu), `close-card --card ID [--note T]`.

Token běhu i slotu review se nikdy nevypisuje: leží v soukromém souboru (0600) ve složce `hub` pod
`$OPORA_HOME`, jinak `<cwd>/.opora/` (první zápis doplní `.opora/` do `.gitignore` Git repa), jinak `~/.opora`
(`OPORA_HUB_STATE_DIR` = přímá cesta, má přednost), a skript ho čte sám. Blokovanou akci skript
nepošle (kód 5) a stejné ID akce se po odmítnutí neopakuje. Kód 3 = 409: znovu načti `state`; kód 6 = 422
(neplatné tělo, `field`/`expected`/`example`). Chybový JSON má vždy `ok`, `status`, `error` a `hint` (další krok).
Adresa je jen loopback, bez proxy a bez přesměrování (jako `opora_write.py`).
"""
import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request

import opora_write

HUB = '/api/oporahub'
STATE_DIR_ENV = 'OPORA_HUB_STATE_DIR'  # přímá cesta ke složce stavu; má přednost
HOME_ENV = 'OPORA_HOME'
EXIT_CONFLICT, EXIT_NONE, EXIT_REFUSED, EXIT_INVALID = 3, 4, 5, 6
# Akce, jejichž `preconditions` jsou celé tělo (doplní se jen project a workspace), docs/oporahub-agent-state.md.
BODY_VERBS = frozenset({'propose_graph', 'accept_baseline', 'accept', 'rebase', 'verification.fix'})
STEP_STATUSES = ('done', 'failed', 'skipped')
SLIM = {'assignment': 'omit'}


class BatchConflictError(Exception):
    """Cizí změna stavu během dávky `act`; `payload` = `{error, code, changed, hint, done, skipped}`."""

    def __init__(self, payload):
        super().__init__(payload.get('error'))
        self.payload = payload


class Refused(Exception):
    """Krok, který agent nesmí udělat (blokovaná akce, lidská akce, chybějící feed); `hint` = co místo toho."""

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.hint = hint or 'Načti state --fresh a vyber ready akci podle nového id (pick).'


def _ignore_in_git(folder):
    """Při prvním zápisu do `<cwd>/.opora/` doplní `.opora/` do `.gitignore` pracovní kopie (je-li to Git repo)."""
    top = next((item for item in (folder, *folder.parents) if (item / '.git').exists()), None)
    if top is None:
        return
    ignore = top / '.gitignore'
    text = ignore.read_text('utf-8') if ignore.is_file() else ''
    if '.opora/' in [line.strip() for line in text.splitlines()]:
        return
    with ignore.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(('' if not text or text.endswith('\n') else '\n') + '.opora/\n')


def opora_home():
    """Kořen stavu klienta: `$OPORA_HOME`, jinak `<cwd>/.opora/` (pracovní složka agenta), jinak `~/.opora`."""
    if os.environ.get(HOME_ENV):
        return Path(os.environ[HOME_ENV])
    local = Path.cwd() / '.opora'
    try:
        fresh = not local.exists()
        local.mkdir(parents=True, exist_ok=True)
        if fresh:
            _ignore_in_git(Path.cwd())
        return local
    except OSError:
        return Path.home() / '.opora'


def state_dir():
    path = Path(os.environ.get(STATE_DIR_ENV) or opora_home() / 'hub')
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
        reason = action.get('blockReason')
        raise Refused(f'Akce {action_id} je {action.get("status")}/{reason}; blokovanou akci neopakuj.',
                      'Patří člověku (bez autonomy.full); napiš mu ID akce.' if reason == 'human_only'
                      else 'Brána projektu agenta nepustí: člověk ve Velínu (Nastavení projektu) zapne '
                           '„Autonomie projde bránou“, nebo akci provede sám.' if reason == 'gate_required'
                      else 'Počkej na změnu stavu (blockedBy, rozpočet) a vyber jinou ready akci (pick).')
    return action


def summary(state, card=None):
    cards = [item for item in state.get('cards', []) if card is None or item.get('nodeId') == card]
    # `autonomy` musí projít: bez něj agent podle skillu bere přijetí/merge/close_card za akci jen pro člověka.
    return {'heads': state.get('heads'), 'autonomy': state.get('autonomy') or {'full': False},
            'stages': [item for item in state.get('stages', []) if item.get('health') != 'ok'],
            'decisions': state.get('decisions', []),
            'ready': [{k: a.get(k) for k in ('id', 'verb', 'targetId', 'path', 'command')} | ({'autonomy': a['autonomy']} if 'autonomy' in a else {}) for a in ready_actions(state)],
            'blocked': len(state.get('actions', [])) - len(ready_actions(state)),
            'cards': cards, 'truncated': state.get('truncated', False)}


# --- běh karty --------------------------------------------------------------------------------

def claim(base, project, workspace, action_id, ttl, context_version=2, request_id=None):
    """Čerstvý agent-state → akce `claim` ready → kontext → claim; token jde jen do soukromého souboru."""
    state, _ = agent_state(base, project, workspace, fresh=True)
    action = find_action(state, action_id)
    if action.get('verb') != 'claim':
        raise Refused(f'Akce {action_id} je {action.get("verb")}, ne claim.', 'Pro jiné akce použij act --action-id.')
    first = next((item for item in ready_actions(state) if item.get('verb') == 'propose_graph'), None)
    if context_version == 2 and first:
        # Běh v2 potřebuje přijatý graf plánu; jinak server vrátí 409 graph_acceptance_required.
        raise Refused('Převzetí potřebuje přijatý graf plánu; přijatá revize ho nemá.',
                      f'Nejdřív act --action-id {first["id"]} (propose_graph), pak act na novou akci accept, potom claim.')
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
               'expectedContextVersion': ctx['contextVersion'], 'requestId': request_id or uuid.uuid4().hex,
               'ttlSeconds': ttl}
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


def step(base, execution, step_id, status, notes, commits=(), checks=()):
    """Průběžný krok (`POST /executions/{id}/steps`) hned po jeho commitu; pád běhu ho neztratí.

    `requestId` je odvozené z kroku a stavu: opakování téhož příkazu vrátí totéž potvrzení."""
    if status not in STEP_STATUSES:
        raise ValueError('Stav kroku je done, failed nebo skipped.')
    bundle = load_bundle('execution', execution)
    evidence = {'notes': notes}
    if commits:
        evidence['commits'] = list(commits)
    if checks:
        evidence['checks'] = list(checks)
    request = ('step-' + ''.join(ch for ch in step_id if ch.isalnum() or ch in '_-') + '-' + status)[:80]
    _, value, _ = _call(base, 'POST', f'{HUB}/executions/{execution}/steps',
                        _token_body(bundle, requestId=request, stepId=step_id, status=status, evidence=evidence))
    return value


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
    decisions = result.get('decisions', [])
    if not isinstance(decisions, list) or not all(isinstance(item, str) and item.strip() for item in decisions):
        raise ValueError('decisions je seznam neprázdných textů (rozhodnutí karty).')
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


# --- složené akce karty: start a deliver (zefektivneni-opory.md §3) ------------------------------

def start(base, project, workspace, node, ttl):
    """Jedno volání: kontext, hlavy, claim a zadání; token jde jen do soukromého souboru, zadání do souboru."""
    payload = {'project': project, 'workspace': workspace, 'nodeId': node, 'ttlSeconds': ttl}
    _, value, _ = _call(base, 'POST', HUB + '/executions/start', payload)
    execution = value['executionId']
    _private_write(_bundle_path('execution', execution), {
        'executionId': execution, 'project': project, 'workspace': workspace, 'nodeId': node,
        'token': value['token'], 'epoch': value['epoch'], 'expiresAt': value['expiresAt'],
        'acceptedRevision': value['acceptedRevision'], 'contextProtocolVersion': 2, 'resultRequestId': uuid.uuid4().hex})
    target = _bundle_path('assignment', execution)
    target.write_text(json.dumps(value['assignment'], ensure_ascii=False, indent=2), 'utf-8')
    return {'executionId': execution, 'nodeId': node, 'epoch': value['epoch'], 'expiresAt': value['expiresAt'],
            'resumed': value.get('resumed'), 'steps': value.get('steps'), 'assignmentFile': str(target),
            'next': value.get('next')}


def parse_steps(items):
    """`--step s1` / `--step s1:"poznámka"` → krok `done` (bez poznámky ji server odvodí z commitů karty)."""
    steps = []
    for item in items:
        step, _, notes = item.partition(':')
        if not step.strip():
            raise ValueError('--step má tvar ID[:poznámka], např. --step s1:"Komponenta a test".')
        steps.append({'stepId': step.strip(), 'status': 'done', **({'notes': notes.strip()} if notes.strip() else {})})
    return steps


def parse_checks(items):
    """`--check "npm test=green"` → `{name, status}`; stav je green nebo red."""
    checks = []
    for item in items:
        name, _, status = item.rpartition('=')
        if not name.strip() or status.strip() not in ('green', 'red'):
            raise ValueError('--check má tvar "PŘÍKAZ=green|red", např. --check "npm test=green".')
        checks.append({'name': name.strip(), 'status': status.strip()})
    return checks


def deliver(base, execution, summary, steps=(), checks=(), commit=None, close=True, extra=None):
    """Jedno volání: kroky, výsledek, lokální sloučení, kontroly a uzavření; `extra` = tělo z `--json`."""
    bundle = load_bundle('execution', execution)
    body = {'project': bundle['project'], 'workspace': bundle['workspace'], **(extra or {})}
    if summary:
        body['summary'] = summary
    if steps:
        body['steps'] = parse_steps(steps)
    if checks:
        body['checks'] = parse_checks(checks)
    if commit:
        body['commit'] = commit
    if not close:
        body['close'] = False
    _, value, _ = _call(base, 'POST', f'{HUB}/executions/{execution}/deliver', body,
                        headers={'X-Opora-Execution-Token': bundle['token']})
    keys = ('executionId', 'nodeId', 'merged', 'checks', 'closed', 'missing', 'leaseRenewed', 'next')
    return {key: value.get(key) for key in keys} | {'steps': (value.get('delivered') or {}).get('steps')}


# --- akce z agent-state, lokální sloučení, uzavření karty ----------------------------------------

def next_ready(base, project, workspace):
    """První ready akce po kroku (pořadí serveru), aby agent nečetl celý stav znovu."""
    state, _ = agent_state(base, project, workspace, fresh=True)
    found = ready_actions(state)
    return first_ready(found)


def first_ready(found):
    """První ready akce jako `{id, verb, targetId, command}` (`command` z agent-state, je-li)."""
    return {k: found[0].get(k) for k in ('id', 'verb', 'targetId', 'command')} if found else None


def close_card(base, project, workspace, card, note=None):
    """Ruční `done.confirmed` karty přes `POST /api/desktop-v3/state` (s plnou autonomií agent, jinak člověk).

    Jen možnost, ne podmínka: splněnou definici hotovo uzavře server sám (`by: "opora"`, opora_card_auto_close).
    Karta bez záznamu ve stavu dostane minimální uzel `{phase, criteria, steps}` jako v UI."""
    scope = {'project': project, 'workspace': workspace}
    _, current, _ = _call(base, 'GET', '/api/desktop-v3/state', params=scope)
    state = current['state']
    node = state.setdefault('nodes', {}).setdefault(card, {'phase': 'discover', 'criteria': [], 'steps': []})
    at = datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')
    node['done'] = {'confirmed': True, 'by': 'agent', 'at': at,
                    'note': note or 'Uzavřeno agentem: definice hotovo splněná (agent-state dod.missing jen human_close).'}
    _, saved, _ = _call(base, 'POST', '/api/desktop-v3/state',
                        {**scope, 'expectedRevision': current['revision'], 'state': state})
    return {'cardId': card, 'revision': (saved or {}).get('revision'), 'done': node['done']}


def local_merge(base, project, workspace, execution, commit):
    """Ohlášení sloučení v projektu bez GitHubu (docs/lokalni-slouceni.md): commit musí být předek HEAD větve."""
    if not commit:
        raise ValueError('local-merge potřebuje --commit SHA sloučeného commitu (git rev-parse HEAD).')
    _, value, _ = _call(base, 'POST', f'{HUB}/executions/{execution}/local-merge',
                        {'project': project, 'workspace': workspace, 'commit': commit})
    return value


def perform(base, project, workspace, action, ttl=900, note=None, request_id=None):
    """Provede jednu ready akci přesně podle `method/path/preconditions`; `request_id` = deterministický klíč dávky."""
    verb, scope = action['verb'], {'project': project, 'workspace': workspace}
    if verb == 'claim':
        return claim(base, project, workspace, action['id'], ttl, request_id=request_id)
    if verb == 'review.claim':
        return review_claim(base, project, workspace, ttl, (action.get('preconditions') or {}).get('role'), request_id)
    if verb == 'close_card':
        return close_card(base, project, workspace, action['targetId'], note)
    if action.get('method') == 'GET':
        return _call(base, 'GET', action['path'])[1]
    if verb in BODY_VERBS and action.get('method') == 'POST':
        return _call(base, 'POST', action['path'], {**scope, **(action.get('preconditions') or {})})[1]
    if verb == 'link_pull_request':
        raise Refused('Vazbu PR zakládá agent-office s tokenem běhu.',
                      'Projekt bez GitHubu (cards[].dod.gate == "local"): opora_hub.py local-merge --execution E --commit SHA.')
    raise Refused(f'Akci {verb} skript obecně neprovádí (tělo není jen preconditions).',
                  'Viz references/hub-api.md pro tvar těla; pošli ho přes opora_api.py.')


def act(base, project, workspace, action_id, ttl=900, note=None):
    """Provede ready akci z čerstvého agent-state přesně podle `method/path/preconditions`."""
    state, _ = agent_state(base, project, workspace, fresh=True)
    action = find_action(state, action_id)
    result = perform(base, project, workspace, action, ttl, note)
    return {'ok': True, 'action': {k: action.get(k) for k in ('id', 'verb', 'targetId', 'path')},
            'result': result, 'next': next_ready(base, project, workspace)}


# --- slot review ------------------------------------------------------------------------------

def review_claim(base, project, workspace, ttl, role=None, request_id=None):
    payload = {'project': project, 'workspace': workspace, 'requestId': request_id or uuid.uuid4().hex,
               'ttlSeconds': ttl}
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

def _last(values):
    """Opakovatelný přepínač u příkazu s jednou hodnotou: platí poslední."""
    return values[-1] if values else None


def run(args, base):
    scope = (args.project, args.workspace)
    if args.command == 'state':
        state, cached = agent_state(base, *scope, fresh=args.fresh)
        return state if args.raw else {'unchanged': cached, **summary(state, args.card)}
    if args.command == 'actions':
        state, _ = agent_state(base, *scope)
        return ready_actions(state, _last(args.verb), _last(args.target), args.all)
    if args.command == 'pick':
        state, _ = agent_state(base, *scope, fresh=True)
        found = ready_actions(state, _last(args.verb), _last(args.target))
        if not found:
            raise LookupError('Žádná ready akce ' + (_last(args.verb) or '') + '.')
        return found[0]
    if args.command == 'start':
        if not args.node:
            raise ValueError('start potřebuje --node ID karty.')
        return start(base, *scope, args.node, args.ttl)
    if args.command == 'deliver':
        extra = opora_write.load_payload(args.json_text) if args.json_text is not None else None
        if not args.execution or not (args.summary or (extra or {}).get('summary')):
            raise ValueError('deliver potřebuje --execution E a --summary T (nebo summary v --json).')
        return deliver(base, args.execution, args.summary, args.step, args.check,
                       args.commit[-1] if args.commit else None, not args.no_close, extra)
    if args.command == 'claim':
        return claim(base, *scope, _last(args.action_id), args.ttl, args.context_version)
    if args.command == 'assignment':
        return assignment(base, args.execution, args.out)
    if args.command == 'heartbeat':
        return heartbeat(base, args.execution, args.ttl)
    if args.command == 'release':
        return release(base, args.execution)
    if args.command == 'step':
        return step(base, args.execution, args.step_id, args.status, args.notes or '', args.commit, args.check)
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
    if args.command == 'act':
        if args.all_ready or len(args.action_id) > 1:
            import opora_act_batch  # hromadné act: stabilní klíč (verb, targetId), skipped místo 409
            return opora_act_batch.run(base, *scope, args.action_id, args.verb, args.target, args.all_ready,
                                       args.ttl, args.note)
        return act(base, *scope, _last(args.action_id), args.ttl, args.note)
    if args.command == 'local-merge':
        return {**local_merge(base, *scope, args.execution, args.commit), 'next': next_ready(base, *scope)}
    if args.command == 'close-card':
        return {**close_card(base, *scope, args.card, args.note), 'next': next_ready(base, *scope)}
    return events(base, *scope, args.since, args.limit)


COMMANDS = ['state', 'actions', 'pick', 'start', 'deliver', 'claim', 'assignment', 'heartbeat', 'step', 'results', 'release',
            'review-claim', 'review-heartbeat', 'review-submit', 'review-release', 'events',
            'act', 'local-merge', 'close-card']


def main(argv=None):
    opora_write.safe_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=COMMANDS)
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--base-url', help='http://127.0.0.1:PORT; výchozí ' + opora_write.BASE_ENV)
    parser.add_argument('--raw', action='store_true', help='state: celý dokument')
    parser.add_argument('--fresh', action='store_true', help='state: bez If-None-Match')
    parser.add_argument('--card', help='state: jen etapa této karty; close-card: karta k uzavření')
    parser.add_argument('--verb', action='append', default=[],
                        help='actions/pick: sloveso akce (claim, review.claim, …); act --all-ready: opakovatelné')
    parser.add_argument('--target', action='append', default=[],
                        help='actions/pick: targetId akce; act --all-ready: jen tyto cíle (opakovatelné)')
    parser.add_argument('--all-ready', action='store_true',
                        help='act: všechny ready akce sloves --verb (i ty, které vzniknou po kroku dávky)')
    parser.add_argument('--all', action='store_true', help='actions: i blokované')
    parser.add_argument('--action-id', action='append', default=[],
                        help='claim/act: ID akce z pick nebo state; act: opakovatelné = dávka')
    parser.add_argument('--context-version', type=int, choices=[1, 2], default=2,
                        help='claim: 2 (výchozí); 1 jen na výslovný pokyn člověka, nikdy jako tichý fallback')
    parser.add_argument('--ttl', type=int, default=900, help='start/claim/heartbeat: 30–3600 s')
    parser.add_argument('--execution', help='ID běhu z claim')
    parser.add_argument('--out', help='assignment: kam uložit neměnné zadání')
    parser.add_argument('--step-id', help='step: ID kroku ze zadání')
    parser.add_argument('--status', choices=list(STEP_STATUSES), help='step: stav kroku')
    parser.add_argument('--notes', help='step: co krok udělal (povinné, do 4000 znaků)')
    parser.add_argument('--note', help='act/close-card: poznámka k uzavření karty')
    parser.add_argument('--commit', action='append', default=[],
                        help='step: SHA commitu kroku (opakovatelné); local-merge/deliver: commit karty'
                             ' (poslední platí; deliver bez něj = HEAD)')
    parser.add_argument('--check', action='append', default=[],
                        help='step: spuštěná kontrola; deliver: "PŘÍKAZ=green|red" (opakovatelné)')
    parser.add_argument('--result-file', help='results: JSON výsledku')
    parser.add_argument('--node', help='start: ID karty')
    parser.add_argument('--summary', help='deliver: souhrn práce karty')
    parser.add_argument('--step', action='append', default=[],
                        help='deliver: hotový krok ID[:poznámka] (opakovatelné); bez poznámky ji server odvodí z commitů')
    parser.add_argument('--no-close', action='store_true', help='deliver: kartu neuzavírat')
    parser.add_argument('--json', dest='json_text', help="deliver: tělo jako JSON; '-' = ze stdin")
    parser.add_argument('--role', choices=['finder', 'voter'])
    parser.add_argument('--slot', help='review-*: slot z review-claim (reviewJobId.taskId)')
    parser.add_argument('--submission-file', help='review-submit: JSON odevzdání')
    parser.add_argument('--since', help='events: kurzor')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args(argv)
    if args.command == 'local-merge':
        args.commit = args.commit[-1] if args.commit else None
    try:
        base = opora_write.base_url(args.base_url or os.environ.get(opora_write.BASE_ENV, '').strip())
        print(json.dumps(run(args, base), ensure_ascii=True, indent=2))
        return 0
    except LookupError as error:
        print(json.dumps({'ok': False, 'status': None, 'none': True, 'error': str(error),
                          'hint': 'Nic není ready: state ukáže blokované akce a rozhodnutí; jinak konec.'},
                         ensure_ascii=True), file=sys.stderr)
        return EXIT_NONE
    except BatchConflictError as error:
        print(json.dumps(error.payload, ensure_ascii=True), file=sys.stderr)
        return EXIT_CONFLICT
    except Refused as error:
        print(json.dumps({'ok': False, 'status': None, 'refused': True, 'error': str(error), 'hint': error.hint},
                         ensure_ascii=True), file=sys.stderr)
        return EXIT_REFUSED
    except HTTPError as error:
        out = opora_write.explain(error)
        out['detail'] = out['error']  # zpětná kompatibilita: text serveru býval v `detail`
        if error.code == 409 and 'code' not in out:
            out['note'] = 'Konflikt: znovu načti state (--fresh) a vyber akci podle nového ID; stejný požadavek neopakuj.'
        print(json.dumps(out, ensure_ascii=True), file=sys.stderr)
        return {409: EXIT_CONFLICT, 422: EXIT_INVALID, 403: EXIT_REFUSED, 428: EXIT_REFUSED}.get(error.code, 1)
    except (URLError, TimeoutError, OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'ok': False, 'status': None, 'error': str(error),
                          'hint': 'Skript nic neodeslal nebo spojení selhalo; oprav argumenty podle error.'},
                         ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
