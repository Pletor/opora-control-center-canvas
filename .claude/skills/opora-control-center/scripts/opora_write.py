"""Zapisovací klient OPORA pro asistenta: jeden POST na plátno, jen na pevný seznam cest.

`opora_write.py <cesta> --project P --workspace W (--json '<json>' | --json-file soubor)`.
Adresa je jen loopback (`--base-url http://127.0.0.1:PORT`, jinak `OPORA_BASE_URL`), bez proxy
a bez přesměrování. Každé volání asistenta schvaluje člověk v UI (docs/asistent.md §5.1).
`project` a `workspace` se doplní do payloadu; jiná hodnota v payloadu je chyba.
Při 409 vypíše `conflict` a skončí kódem 3: asistent znovu načte stav a použije jen svou změnu.
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
TIMEOUT = 30
MAX_BYTES = 8 * 1024 * 1024
MAX_PAYLOAD = 2 * 1024 * 1024
# Jediné cesty, na které skript pošle POST (docs/asistent.md §5.1). Jinam nic neodejde.
WRITE_ROUTES = frozenset({
    '/api/graph', '/api/node-spec', '/api/node-text', '/api/desktop-v3/state', '/api/desktop-v3/block',
    '/api/desktop-v3/agent-workspace', '/api/desktop-v3/agent-output',
})
EXIT_CONFLICT = 3


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
        raise ValueError('Payload musí být JSON objekt.')
    return payload


def scoped(payload, project, workspace):
    """Payload s `project` a `workspace` z argumentů; rozpor s payloadem se nepřepíše potichu."""
    for key, value in (('project', project), ('workspace', workspace)):
        if key in payload and payload[key] != value:
            raise ValueError('Payload má jiné pole ' + key + ' než --' + key + '.')
    return {**payload, 'project': project, 'workspace': workspace}


def post(base, route, payload):
    """POST na plátno; cesta mimo `WRITE_ROUTES` skončí chybou dřív, než cokoli odejde."""
    if route not in WRITE_ROUTES:
        raise ValueError('Cesta ' + route + ' není povolený zápis na plátno.')
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Origin': base}
    return _read(Request(base + route, data=data, headers=headers, method='POST'), TIMEOUT)


MSYS_PATH = re.compile(r'^[A-Za-z]:[/\\].*?(?P<route>[/\\]api[/\\][a-z0-9/\\-]+)$')


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
    parser.add_argument('route', help='jedna z: ' + ', '.join(sorted(WRITE_ROUTES)))
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--json', dest='json_text')
    parser.add_argument('--json-file')
    parser.add_argument('--base-url', help='domácí adresa http://127.0.0.1:PORT; výchozí ' + BASE_ENV)
    args = parser.parse_args(argv)
    args.route = route_of(args.route)
    try:
        if args.route not in WRITE_ROUTES:
            raise ValueError('Cesta ' + args.route + ' není povolený zápis na plátno.')
        base = base_url(args.base_url or os.environ.get(BASE_ENV, '').strip())
        payload = scoped(load_payload(args.json_text, args.json_file), args.project, args.workspace)
        result = post(base, args.route, payload)
        print(json.dumps({'ok': True, 'route': args.route, 'result': result}, ensure_ascii=True, indent=2))
        return 0
    except HTTPError as error:
        detail = _detail(error)
        if error.code == 409:
            out = {'ok': False, 'conflict': True, 'error': 'conflict',
                   'note': 'Stav se mezitím změnil. Znovu načti stav a použij jen svou změnu.'}
            if detail:
                out['detail'] = detail
            print('conflict')
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
