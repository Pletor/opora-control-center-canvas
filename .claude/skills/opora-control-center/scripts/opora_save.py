"""Uložit vše z příkazové řádky: vytvoří verzi plátna (Historie uložení), stejně jako tlačítko v UI.

`opora_save.py --project P --workspace W [--author JMÉNO] [--if-dirty] [--quiet-fail]`.
Postup: GET /api/canvas-versions (token, dirty) → GET /api/view (digest) → POST /api/canvas-versions.
`--if-dirty` uloží jen při neuložených změnách. `--quiet-fail` vrací kód 0 i při chybě (pro hook:
nedostupná aplikace nesmí shodit práci agenta). Adresa jen loopback (`--base-url` nebo `OPORA_BASE_URL`).
Verzi lze obnovit v UI (Historie uložení) nebo POST /api/canvas-versions/restore.
"""
import argparse
import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opora_write import BASE_ENV, TIMEOUT, _read, actor_header, base_url  # noqa: E402


def get(base, route, params):
    req = Request(base + route + '?' + urlencode(params), headers={'Accept': 'application/json'})
    return _read(req, TIMEOUT)


def save(base, project, workspace, author, if_dirty):
    scope = {'project': project, 'workspace': workspace}
    versions = get(base, '/api/canvas-versions', scope)
    if if_dirty and not versions.get('dirty'):
        return {'ok': True, 'saved': False, 'reason': 'beze změn'}
    digest = get(base, '/api/view', scope)['digest']
    payload = {**scope, 'digest': digest, 'author': author, 'expectedToken': versions.get('currentToken', '')}
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Origin': base,
               'X-Opora-Actor': actor_header()}
    result = _read(Request(base + '/api/canvas-versions', data=data, headers=headers, method='POST'), TIMEOUT)
    return {'ok': True, 'saved': True, 'version': result.get('version')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--author', default='Claude Code')
    parser.add_argument('--base-url', default=os.environ.get(BASE_ENV))
    parser.add_argument('--if-dirty', action='store_true')
    parser.add_argument('--quiet-fail', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not args.base_url:
            raise ValueError('Chybí --base-url nebo ' + BASE_ENV + '.')
        result = save(base_url(args.base_url), args.project, args.workspace, args.author, args.if_dirty)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as cause:  # hook nesmí spadnout na nedostupné aplikaci
        print(json.dumps({'ok': False, 'error': str(cause)}, ensure_ascii=False), file=sys.stderr)
        return 0 if args.quiet_fail else 1


if __name__ == '__main__':
    sys.exit(main())
