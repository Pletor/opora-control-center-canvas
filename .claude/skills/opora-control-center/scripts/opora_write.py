"""Zapisovací klient OPORA pro agenta: jeden POST na plátno, jen na pevný seznam cest.

`opora_write.py <cesta> --project P --workspace W (--json '<json>' | --json - | --json-file soubor) [--dry-run]`.
`--json -` čte tělo ze stdin (heredoc), takže payload nemusí do souboru.
OporaHub (`/api/oporahub/*`): jen cesty, které smí agent (`HUB_AGENT_ROUTES`); lidské (`HUB_HUMAN_ROUTES`)
skript odmítne dřív, než cokoli odejde, a cesty s tokenem běhu či slotu patří `opora_hub.py`.
`--dry-run` (bez hodnoty) u `/api/canvas-plan` a `/api/canvas-layout`: nastaví `dryRun: true` (přepíše hodnotu
z konceptu), dávka se jen ověří a nic se nezapíše; koncept se kvůli tomu nepřepisuje.
Adresa je jen loopback (`--base-url http://127.0.0.1:PORT`, jinak `OPORA_BASE_URL`), bez proxy
a bez přesměrování.
`project` a `workspace` se doplní do payloadu; jiná hodnota v payloadu je chyba.
Při 409 vypíše `conflict: <detail>` a skončí kódem 3 (změněný stav nebo krok, na který je brzy; `hint` říká další
krok). Neplatný payload je 422 s `field`, `expected` a `example` a končí kódem 6. Chybový JSON (stderr) má vždy
`ok`, `status`, `error` a `hint`.
"""
import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

BASE_ENV = 'OPORA_BASE_URL'
# Pomalý server (dlouhé dotazy pod globálním zámkem) odpovídá i za desítky sekund; zápis se
# po vypršení NEopakuje: server ho mohl provést, druhý pokus by zapsal 2× (karta P1).
TIMEOUT = 90
MAX_BYTES = 8 * 1024 * 1024
MAX_PAYLOAD = 2 * 1024 * 1024  # strop konceptu dávky plánu
# Jediné cesty, na které skript pošle POST. Jinam nic neodejde.
WRITE_ROUTES = frozenset({
    '/api/desktop-v3/lease',
    '/api/desktop-v3/realize-source',
    '/api/canvas-layout',
    '/api/desktop-v3/assignment-snapshot',
    '/api/canvas-versions',
    '/api/desktop-v3/rule', '/api/desktop-v3/decision',
    '/api/graph', '/api/node-spec', '/api/node-text', '/api/desktop-v3/state', '/api/desktop-v3/block',
    '/api/desktop-v3/agent-workspace', '/api/desktop-v3/agent-output', '/api/canvas-plan',
    '/api/desktop-v3/pipeline',
    # Schránka zadání: doslovné verzované fragmenty, split, výzkum, propose-mvp (references/workflow.md).
    '/api/brief-vault',
    # Storyboard karty (docs/storyboard-karty.md): momenty, komentáře a šipky člověka.
    '/api/storyboard',
    # Skica momentu storyboardu: kresba ve vrstvě sb/<nodeId>/<momentId> (docs/storyboard-karty.md).
    '/api/drawing',
})
# OporaHub: šablony cest (`{id}` = jeden segment ID). Agent smí jen tyto POST (references/hub-api.md).
HUB_AGENT_ROUTES = (
    '/api/oporahub/changesets', '/api/oporahub/changesets/{id}/rebase',
    '/api/oporahub/graph-proposals', '/api/oporahub/graph-proposals/{id}/rebase',
    '/api/oporahub/content-changes', '/api/oporahub/content-changes/{id}/rebase',
    '/api/oporahub/proposals', '/api/oporahub/proposal-reviews/events',
    '/api/oporahub/auto-rebase/run', '/api/oporahub/auto-rebase/conflicts/{id}/resolve',
    '/api/oporahub/executions/context',
    '/api/oporahub/review-jobs/sync', '/api/oporahub/review-jobs/self-checks',
    '/api/oporahub/review-jobs/findings/{id}/resolve',
    '/api/oporahub/review-incidents', '/api/oporahub/review-evals/sync', '/api/oporahub/review-recurring/promote',
    '/api/oporahub/verifications/{id}/fix-proposal', '/api/oporahub/github-evidence',
    '/api/oporahub/sparse-context/backfill',
)
# Jen člověk v UI (server vrátí 403/428); skript je odmítne předem a nic neodešle.
HUB_HUMAN_ROUTES = (
    '/api/oporahub/baselines', '/api/oporahub/changesets/{id}/accept',
    '/api/oporahub/graph-proposals/{id}/accept', '/api/oporahub/content-changes/{id}/accept',
    '/api/oporahub/review-identities/claim', '/api/oporahub/review-identities/{id}/verify',
    '/api/oporahub/review-identities/{id}/revoke', '/api/oporahub/review-jobs/decisions',
    '/api/oporahub/history/rebuild', '/api/oporahub/execution-budgets', '/api/oporahub/execution-budgets/{id}/cancel',
    '/api/oporahub/review-policy', '/api/oporahub/review-policy/disable',
    '/api/oporahub/proposal-reviews/policy', '/api/oporahub/proposal-reviews/policy/disable',
    '/api/oporahub/reconciliation/bindings', '/api/oporahub/reconciliation/{id}/control',
)
# Nesou token běhu nebo slotu: jen přes `opora_hub.py`, token nesmí do příkazu ani do konceptu.
HUB_TOKEN_ROUTES = (
    '/api/oporahub/executions/claim', '/api/oporahub/executions/{id}/heartbeat',
    '/api/oporahub/executions/{id}/release', '/api/oporahub/executions/{id}/results',
    '/api/oporahub/executions/{id}/steps',
    '/api/oporahub/executions/{id}/pull-request', '/api/oporahub/review-jobs/claim',
    '/api/oporahub/review-jobs/{id}/tasks/{id}/heartbeat', '/api/oporahub/review-jobs/{id}/tasks/{id}/release',
    '/api/oporahub/review-jobs/{id}/tasks/{id}/submit', '/api/oporahub/verifications/requests',
    '/api/oporahub/verifications/{id}/report',
)
# Složené akce karty (docs/navrhy/2026-10-28-zefektivneni-opory.md §3): vrací nebo berou token běhu, proto
# jen `opora_hub.py start` / `deliver`; token nesmí na výstup ani do příkazu.
HUB_COMPOSED_ROUTES = ('/api/oporahub/executions/start', '/api/oporahub/executions/{id}/deliver')
# Tyto cesty berou jen `project` (bez `workspace`); server neznámé pole odmítne.
HUB_PROJECT_ONLY = frozenset({'/api/oporahub/review-evals/sync', '/api/oporahub/review-recurring/promote'})
ID_SEGMENT = re.compile(r'[A-Za-z0-9_.:-]{1,160}')


def hub_template(route):
    """Šablona OporaHub cesty pro `route`, nebo None; ID segment nesmí být `.` ani `..`."""
    parts = route.split('/')
    for template in HUB_AGENT_ROUTES + HUB_HUMAN_ROUTES + HUB_TOKEN_ROUTES + HUB_COMPOSED_ROUTES:
        expected = template.split('/')
        if len(expected) == len(parts) and all(
                want == got or (want == '{id}' and ID_SEGMENT.fullmatch(got) and got not in ('.', '..'))
                for want, got in zip(expected, parts)):
            return template
    return None


def check_route(route, payload=None):
    """Povolí cestu ze `WRITE_ROUTES` nebo agentní OporaHub cestu; jinak ValueError s důvodem."""
    if route in WRITE_ROUTES:
        return route
    template = hub_template(route)
    if template in HUB_HUMAN_ROUTES:
        raise ValueError('Cesta ' + route + ' patří člověku v UI (403); napiš to člověku, neobcházej. Agent mimo'
                         ' aplikaci s autonomy.full ji provede přes opora_hub.py act --action-id ID.')
    if template in HUB_TOKEN_ROUTES or template in HUB_COMPOSED_ROUTES:
        raise ValueError('Cesta ' + route + ' nese token běhu nebo slotu; použij opora_hub.py.')
    if template is None:
        raise ValueError('Cesta ' + route + ' není povolený zápis na plátno.')
    if template == '/api/oporahub/sparse-context/backfill' and (payload or {}).get('dryRun') is not True:
        raise ValueError('Backfill sparse kontextu smí agent jen s dryRun: true; zápis spouští člověk.')
    return template


EXIT_CONFLICT = 3
EXIT_INVALID = 6
# Další krok podle HTTP stavu, když ho server neřekl sám (`hint` v těle má přednost).
HINTS = {
    422: 'Neplatné tělo: oprav pole z `field` podle `expected` (vzor v `example`) a pošli znovu; nic se nezapsalo.',
    409: 'Stav se mezitím změnil nebo na krok je brzy: opora_hub.py state --fresh, vyber akci podle nového id; '
         'stejný požadavek znovu nepomůže.',
    403: 'Patří člověku. S autonomy.full v agent-state to agent smí přes opora_hub.py act --action-id ID '
         '(nebo opora_api.py); jinak napiš člověku, neobcházej.',
    428: 'Chybí identita: nastav OPORA_AGENT_NAME="<role>-<relace>" a pošli znovu.',
    404: 'Cesta nebo záznam neexistuje: ověř cestu v references/hub-api.md nebo routy.md a ID ze state.',
}
# Záznam činnosti (docs/zaznam-cinnosti.md): každý zápis skriptu se hlásí jako agent.
AGENT_ENV = 'OPORA_AGENT_NAME'
LEASE_ENV = 'OPORA_LEASE_TOKEN'
AGENT_NAME = re.compile(r'[^\w .:()\-]')


def actor_name(name=None):
    """Jméno aktéra: `name`, jinak `OPORA_AGENT_NAME`; nepovolené znaky pryč, výchozí `agent`."""
    raw = name if name is not None else os.environ.get(AGENT_ENV, '')
    return AGENT_NAME.sub('', raw).strip()[:80] or 'agent'


def actor_header(name=None):
    """Hodnota `X-Opora-Actor` pro jméno z `actor_name`."""
    return 'agent; name=' + actor_name(name)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Přesměrování odmítnuto; ověřte adresu aplikace.')


def base_url(value):
    parts = urlsplit(value)
    if (parts.scheme != 'http' or parts.hostname not in ('127.0.0.1', 'localhost')
            or parts.username is not None or parts.password is not None
            or parts.path not in ('', '/') or parts.query or parts.fragment
            or parts.port is None):
        raise ValueError('Použijte http://127.0.0.1:PORT nebo http://localhost:PORT bez cesty a přihlašovacích údajů.')
    return value.rstrip('/')


def _open(req, timeout):
    """Jediné místo, kde skript sahá na síť: bez proxy a bez přesměrování."""
    return build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout)


def _read(req, timeout):
    with _open(req, timeout) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('Odpověď překročila limit 8 MiB.')
        return json.loads(body) if body else {}


def load_payload(text=None, path=None):
    """Tělo z `--json TEXT`, `--json -` (stdin, bez souboru v repu) nebo `--json-file`."""
    if (text is None) == (path is None):
        raise ValueError('Zadejte právě jedno: --json nebo --json-file.')
    if text == '-':
        raw = sys.stdin.buffer.read(MAX_PAYLOAD + 1)
        if len(raw) > MAX_PAYLOAD:
            raise ValueError('Payload překročil limit 2 MiB.')
        text = raw.decode('utf-8-sig')
    if path is not None:
        with open(path, 'rb') as handle:
            raw = handle.read(MAX_PAYLOAD + 1)
        if len(raw) > MAX_PAYLOAD:
            raise ValueError('Payload překročil limit 2 MiB.')
        text = raw.decode('utf-8')
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise TypeError('Payload musí být JSON objekt.')
    return payload


def scoped(payload, project, workspace):
    """Payload s `project` a `workspace` z argumentů; rozpor s payloadem se nepřepíše potichu.

    `workspace=None` = cesta jen s projektem (`HUB_PROJECT_ONLY`)."""
    pairs = (('project', project),) if workspace is None else (('project', project), ('workspace', workspace))
    for key, value in pairs:
        if key in payload and payload[key] != value:
            raise ValueError('Payload má jiné pole ' + key + ' než --' + key + '.')
    return {**payload, **dict(pairs)}


def post(base, route, payload, actor=None):
    """POST na plátno; cesta mimo `WRITE_ROUTES` skončí chybou dřív, než cokoli odejde.

    `actor` = jméno aktéra (opora_cycle.py); bez něj `OPORA_AGENT_NAME`."""
    check_route(route, payload)
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Origin': base,
               'X-Opora-Actor': actor_header(actor)}
    # Zápis na kartu drženou lease nese token převzetí (upgrade-opora #35).
    lease = os.environ.get(LEASE_ENV, '').strip()
    if re.fullmatch(r'[0-9a-f]{64}', lease):
        headers['X-Opora-Lease'] = lease
    return _read(Request(base + route, data=data, headers=headers, method='POST'), TIMEOUT)


MSYS_PATH = re.compile(r'^[A-Za-z]:[/\\].*?(?P<route>[/\\]api[/\\][A-Za-z0-9_.:/\\-]+)$')


def route_of(value):
    """Cesta API z argumentu. Git Bash (MSYS) přepíše `/api/x` na `C:/Program Files/Git/api/x`;
    takovou cestu vrátí zpět. Backend schvaluje příkaz ještě před přepisem, allowlist platí dál."""
    match = MSYS_PATH.match(value or '')
    return match['route'].replace('\\', '/') if match else value


def explain(error):
    """HTTPError → `{ok: False, status, error, hint}` a z těla serveru `code`, `field`, `expected`, `example`."""
    try:
        body = json.loads(error.read(64 * 1024))
    except (OSError, ValueError, AttributeError):
        body = None
    body = body if isinstance(body, dict) else {}
    out = {'ok': False, 'status': error.code,
           'error': body['error'] if isinstance(body.get('error'), str) else 'HTTP ' + str(error.code)}
    for key in ('code', 'field', 'expected', 'example', 'humanRequired'):
        if key in body:
            out[key] = body[key]
    hint = body.get('hint') if isinstance(body.get('hint'), str) else None
    out['hint'] = hint or HINTS.get(error.code) or (
        'Server nebo úložiště nedostupné: opora_read.py status; zápis neopakuj naslepo.' if error.code >= 500
        else 'Přečti error a oprav požadavek.')
    return out


def _detail(error):
    try:
        detail = json.loads(error.read(64 * 1024)).get('error')
    except (OSError, ValueError, AttributeError):
        return None
    return detail if isinstance(detail, str) else None


def safe_console():
    """Nápověda a chyby s diakritikou nespadnou na konzoli cp1250 (Windows): neznámý znak se escapuje."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='backslashreplace')
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    safe_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('route', help='jedna z: ' + ', '.join(sorted(WRITE_ROUTES)) + '; OporaHub viz HUB_AGENT_ROUTES')
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', help='povinné kromě ' + ', '.join(sorted(HUB_PROJECT_ONLY)))
    parser.add_argument('--json', dest='json_text', help="tělo jako JSON; '-' = ze stdin")
    parser.add_argument('--json-file')
    parser.add_argument('--dry-run', action='store_true', help='jen ověření dávky nebo rozmístění; /api/canvas-plan a /api/canvas-layout')
    parser.add_argument('--base-url', help='domácí adresa http://127.0.0.1:PORT; výchozí ' + BASE_ENV)
    args = parser.parse_args(argv)
    args.route = route_of(args.route)
    try:
        template = check_route(args.route, {'dryRun': True})
        project_only = template in HUB_PROJECT_ONLY
        if not project_only and not args.workspace:
            raise ValueError('Chybí --workspace.')
        if args.dry_run and args.route not in ('/api/canvas-plan', '/api/canvas-layout'):
            raise ValueError('--dry-run platí jen pro /api/canvas-plan a /api/canvas-layout.')
        base = base_url(args.base_url or os.environ.get(BASE_ENV, '').strip())
        payload = scoped(load_payload(args.json_text, args.json_file), args.project,
                         None if project_only else args.workspace)
        if args.dry_run:
            payload = {**payload, 'dryRun': True}
        result = post(base, args.route, payload)
        print(json.dumps({'ok': True, 'route': args.route, 'result': result}, ensure_ascii=True, indent=2))
        return 0
    except HTTPError as error:
        out = explain(error)
        detail = out['error'] if out['error'] != 'HTTP ' + str(error.code) else None
        if error.code == 409:
            # 409 = změněný stav nebo krok, na který je brzy; neplatný payload je u nových chyb 422
            # (backend/canvas/payload_errors.py), starší cesty ho vrací jako 409 dál: rozliší `detail`.
            out |= {'conflict': True, 'error': 'conflict', 'note': 'Zápis odmítnut (409): stav se změnil, krok čeká '
                    'na jiný krok, nebo (starší cesta) payload neprošel validací. Řiď se detail a hint.'}
            if detail:
                out['detail'] = detail
            print('conflict' + (': ' + detail if detail else ''))
            print(json.dumps(out, ensure_ascii=True), file=sys.stderr)
            return EXIT_CONFLICT
        if detail:
            out['detail'] = detail
        print(json.dumps(out, ensure_ascii=True), file=sys.stderr)
        return EXIT_INVALID if error.code == 422 else 1
    except (URLError, TimeoutError, OSError, ValueError, TypeError, UnicodeError) as error:
        print(json.dumps({'ok': False, 'status': None, 'error': str(error),
                          'hint': 'Skript nic neodeslal nebo spojení selhalo; oprav argumenty podle error.'},
                         ensure_ascii=True), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
