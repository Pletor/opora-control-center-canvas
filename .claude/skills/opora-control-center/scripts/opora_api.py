"""Obecné volání libovolné cesty OPORY s identitou agenta: `opora_api.py METHOD PATH [volby]`.

Pro agenta mimo aplikaci (terminál, headless běh), když na cestu nemá vlastní příkaz `opora_hub.py`
(např. `POST /api/check-run`, `GET /api/oporahub/graph-proposals/{id}`, lidské akce při `autonomy.full`).
Vlastní HTTP klient v repu ani sondování `/openapi.json` nejsou potřeba.

    opora_api.py GET  /api/oporahub/graph-proposals/context --project P --workspace W
    opora_api.py POST /api/check-run --project P --workspace W --json '{"scope": "<nodeId>", "status": "green", "sha": "<sha>"}'

`--project`/`--workspace` jdou u GET do dotazu, u POST/PUT/PATCH/DELETE do těla (rozpor s tělem = chyba).
Výstup je vždy jeden JSON na stdout: `{ok, status, result}` nebo `{ok: false, status, error, hint, …}`
(u 422 i `field`, `expected`, `example`). Kódy: 0 ok, 1 chyba, 3 HTTP 409, 5 odmítnuto, 6 HTTP 422.

Hranice (stejné jako `opora_write.py` / `opora_hub.py`): jen loopback bez proxy a přesměrování; výjimky plné
autonomie (docs/plna-autonomie-agenta.md §4) i cesty s tokenem běhu nebo slotu skript odmítne dřív, než cokoli
odejde. O všem ostatním rozhoduje server podle identity a `autonomy.full`.
"""
import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

import opora_write

METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')
EXIT_CONFLICT, EXIT_REFUSED, EXIT_INVALID = 3, 5, 6
# Výjimky plné autonomie (docs/plna-autonomie-agenta.md §4) a atribuce člověka: jen člověk v UI, vždy.
HUMAN_ONLY = (re.compile(r'/api/project-settings/agent-autonomy'), re.compile(r'/api/access(/.*)?'),
              re.compile(r'/api/oporahub/repository(/.*)?'), re.compile(r'/api/assistant/jev-key'),
              re.compile(r'/api/memory/provision'), re.compile(r'/api/oporahub/review-identities(/.*)?'),
              re.compile(r'/api/(local-project|empty-project|connect)'))
SAFE_PATH = re.compile(r'/api(/[A-Za-z0-9_.:~-]+)*/?')


class Refused(Exception):
    """Požadavek, který skript nepošle (výjimka §4, token běhu, neplatná cesta)."""

    def __init__(self, message, hint):
        super().__init__(message)
        self.hint = hint


def check(method, path, body):
    if method not in METHODS:
        raise Refused('Metoda ' + method + ' není podporovaná.', 'Použij ' + ', '.join(METHODS) + '.')
    if not SAFE_PATH.fullmatch(path) or any(part in ('.', '..') for part in path.split('/')):
        raise Refused('Cesta ' + path + ' není cesta API OPORY.', 'Cesta začíná /api/ a nemá dotaz; dotaz dej do --query.')
    if any(pattern.fullmatch(path.rstrip('/')) for pattern in HUMAN_ONLY):
        raise Refused('Cesta ' + path + ' patří vždy jen člověku (i při plné autonomii).',
                      'Napiš to člověku; přepínač autonomie, přístupy, repozitář, klíče a identitu reviewera agent nemění.')
    if path.rstrip('/') == '/api/remove' and isinstance(body, dict) and body.get('kind') == 'project':
        raise Refused('Odpojení celého projektu patří jen člověku.', 'Napiš to člověku.')
    if method != 'GET' and opora_write.hub_template(path) in opora_write.HUB_TOKEN_ROUTES:
        raise Refused('Cesta ' + path + ' nese token běhu nebo slotu.',
                      'Použij opora_hub.py (claim, step, results, heartbeat, release, review-*); token nepatří do příkazu.')


def request(base, method, path, body=None, query=None):
    """Jedno volání; vrací (status, tělo). HTTPError propadne volajícímu."""
    url = base + path + ('?' + urlencode(query) if query else '')
    headers = {'Accept': 'application/json', 'Origin': base, 'X-Opora-Actor': opora_write.actor_header()}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = Request(url, data=data, headers=headers, method=method)
    with opora_write._open(req, opora_write.TIMEOUT) as response:
        raw = response.read(opora_write.MAX_BYTES + 1)
        if len(raw) > opora_write.MAX_BYTES:
            raise ValueError('Odpověď překročila limit 8 MiB.')
        return response.status, (json.loads(raw) if raw else None)


def call(base, method, path, project=None, workspace=None, body=None, query=None):
    """Volání s doplněným projektem a prostorem; vrací výsledek ve tvaru výstupu skriptu."""
    method = method.upper()
    query = dict(query or {})
    if method == 'GET':
        if body is not None:
            raise Refused('GET nenese tělo.', 'Parametry dej do --query klic=hodnota.')
        query |= {key: value for key, value in (('project', project), ('workspace', workspace)) if value}
    elif project:
        body = opora_write.scoped(body or {}, project, workspace)
    check(method, path, body)
    try:
        status, result = request(base, method, path, body, query)
    except HTTPError as error:
        return opora_write.explain(error)
    return {'ok': True, 'status': status, 'result': result}


def exit_code(out):
    if out.get('ok'):
        return 0
    return {409: EXIT_CONFLICT, 422: EXIT_INVALID, 403: EXIT_REFUSED, 428: EXIT_REFUSED}.get(out.get('status'), 1)


def main(argv=None):
    opora_write.safe_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('method', type=str.upper, choices=METHODS)
    parser.add_argument('path', help='cesta API bez dotazu, např. /api/check-run')
    parser.add_argument('--project')
    parser.add_argument('--workspace')
    parser.add_argument('--json', dest='json_text', help='tělo jako JSON objekt')
    parser.add_argument('--json-file', help='tělo ze souboru (delší payload); soubor drž mimo repozitář projektu')
    parser.add_argument('--query', action='append', default=[], help='klic=hodnota do dotazu (opakovatelné)')
    parser.add_argument('--base-url', help='http://127.0.0.1:PORT; výchozí ' + opora_write.BASE_ENV)
    args = parser.parse_args(argv)
    path = opora_write.route_of(args.path)
    try:
        if urlsplit(path).query:
            raise Refused('Cesta nese dotaz.', 'Dotaz dej do --query klic=hodnota.')
        query = dict(item.split('=', 1) for item in args.query if '=' in item)
        if len(query) != len(args.query):
            raise ValueError('--query má tvar klic=hodnota.')
        body = None
        if args.json_text is not None or args.json_file is not None:
            body = opora_write.load_payload(args.json_text, args.json_file)
        base = opora_write.base_url(args.base_url or os.environ.get(opora_write.BASE_ENV, '').strip())
        out = call(base, args.method, path, args.project, args.workspace, body, query)
    except Refused as error:
        out = {'ok': False, 'status': None, 'refused': True, 'error': str(error), 'hint': error.hint}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return EXIT_REFUSED
    except (URLError, TimeoutError, OSError, ValueError, TypeError, UnicodeError) as error:
        out = {'ok': False, 'status': None, 'error': str(error),
               'hint': 'Nic neodešlo nebo spojení selhalo: ověř --base-url / OPORA_BASE_URL a argumenty.'}
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return exit_code(out)


if __name__ == '__main__':
    sys.exit(main())
