"""Zapisovací klient OPORA pro asistenta: jeden POST na plátno, jen na pevný seznam cest.

`opora_write.py <cesta> --project P --workspace W (--json '<json>' | --json-file soubor) [--dry-run]`.
OporaHub (`/api/oporahub/*`): jen cesty, které smí agent (`HUB_AGENT_ROUTES`); lidské (`HUB_HUMAN_ROUTES`)
skript odmítne dřív, než cokoli odejde, a cesty s tokenem běhu či slotu patří `opora_hub.py`.
`--dry-run` (bez hodnoty) u `/api/canvas-plan` a `/api/canvas-layout`: nastaví `dryRun: true` (přepíše hodnotu
z konceptu), dávka se jen ověří a nic se nezapíše; koncept se kvůli tomu nepřepisuje.
Adresa je jen loopback (`--base-url http://127.0.0.1:PORT`, jinak `OPORA_BASE_URL`), bez proxy
a bez přesměrování. Každé volání asistenta schvaluje člověk v UI (docs/asistent.md §5.1).
`project` a `workspace` se doplní do payloadu; jiná hodnota v payloadu je chyba.
Při 409 vypíše `conflict: <detail>` a skončí kódem 3. 409 je změněný stav i neplatný payload; rozliší je detail.
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
MAX_PAYLOAD = 2 * 1024 * 1024  # shodně s `DRAFT_LIMIT` v approvals.py (koncept dávky plánu)
# Jediné cesty, na které skript pošle POST (docs/asistent.md §5.1). Jinam nic neodejde.
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
    '/api/oporahub/executions/{id}/pull-request', '/api/oporahub/review-jobs/claim',
    '/api/oporahub/review-jobs/{id}/tasks/{id}/heartbeat', '/api/oporahub/review-jobs/{id}/tasks/{id}/release',
    '/api/oporahub/review-jobs/{id}/tasks/{id}/submit', '/api/oporahub/verifications/requests',
    '/api/oporahub/verifications/{id}/report',
)
# Tyto cesty berou jen `project` (bez `workspace`); server neznámé pole odmítne.
HUB_PROJECT_ONLY = frozenset({'/api/oporahub/review-evals/sync', '/api/oporahub/review-recurring/promote'})
ID_SEGMENT = re.compile(r'[A-Za-z0-9_.:-]{1,160}')


def hub_template(route):
    """Šablona OporaHub cesty pro `route`, nebo None; ID segment nesmí být `.` ani `..`."""
    parts = route.split('/')
    for template in HUB_AGENT_ROUTES + HUB_HUMAN_ROUTES + HUB_TOKEN_ROUTES:
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
        raise ValueError('Cesta ' + route + ' patří člověku v UI (403); napiš to člověku, neobcházej.')
    if template in HUB_TOKEN_ROUTES:
        raise ValueError('Cesta ' + route + ' nese token běhu nebo slotu; použij opora_hub.py.')
    if template is None:
        raise ValueError('Cesta ' + route + ' není povolený zápis na plátno.')
    if template == '/api/oporahub/sparse-context/backfill' and (payload or {}).get('dryRun') is not True:
        raise ValueError('Backfill sparse kontextu smí agent jen s dryRun: true; zápis spouští člověk.')
    return template


EXIT_CONFLICT = 3
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
    if (text is None) == (path is None):
        raise ValueError('Zadejte právě jedno: --json nebo --json-file.')
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


def _detail(error):
    try:
        detail = json.loads(error.read(64 * 1024)).get('error')
    except (OSError, ValueError, AttributeError):
        return None
    return detail if isinstance(detail, str) else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('route', help='jedna z: ' + ', '.join(sorted(WRITE_ROUTES)) + '; OporaHub viz HUB_AGENT_ROUTES')
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', help='povinné kromě ' + ', '.join(sorted(HUB_PROJECT_ONLY)))
    parser.add_argument('--json', dest='json_text')
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
        detail = _detail(error)
        if error.code == 409:
            # Backend vrací 409 i pro neplatný payload (každá ValueError, factory.py); `detail` rozliší,
            # zda opakovat s čerstvou revizí, nebo opravit payload. Stejný zápis znovu nepomůže.
            out = {'ok': False, 'conflict': True, 'error': 'conflict',
                   'note': 'Zápis odmítnut (409): buď se stav mezitím změnil, nebo payload neprošel validací. '
                           'Podle detail buď znovu načti stav a použij jen svou změnu, nebo oprav payload.'}
            if detail:
                out['detail'] = detail
            print('conflict' + (': ' + detail if detail else ''))
            print(json.dumps(out, ensure_ascii=True), file=sys.stderr)
            return EXIT_CONFLICT
        out = {'ok': False, 'error': 'HTTP ' + str(error.code)}
        if detail:
            out['detail'] = detail
        print(json.dumps(out, ensure_ascii=True), file=sys.stderr)
    except (URLError, TimeoutError, OSError, ValueError, TypeError, UnicodeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=True), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
