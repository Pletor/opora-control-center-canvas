"""Čtecí klient OPORA: pouze GET na zvolený loopback server, bez proxy a redirectů."""
import argparse
import hashlib
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_BYTES = 8 * 1024 * 1024


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


def request(base, route, params=None, binary=False):
    suffix = '?' + urlencode(params) if params else ''
    req = Request(base + route + suffix, headers={'Accept': '*/*' if binary else 'application/json'}, method='GET')
    with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=10) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('Odpověď překročila limit 8 MiB; zúžte scope.')
        return body if binary else json.loads(body)


def pick(value, keys):
    return {key: value[key] for key in keys if key in value}


def summary(command, data, args, base):
    if command == 'projects':
        return {'draft': data.get('draft'), 'projects': [pick(p, ['id', 'name', 'sourceKind']) for p in data.get('projects', [])], 'jobsCount': len(data.get('jobs', []))}
    if command == 'view':
        nodes = data.get('graph', {}).get('nodes', [])
        edges = data.get('graph', {}).get('edges', [])
        return {**pick(data, ['readOnly', 'digest', 'branch', 'sha', 'dirty']),
                'project': args.project, 'workspace': args.workspace,
                'nodeCount': len(nodes), 'edgeCount': len(edges),
                'nodes': [pick(n, ['id', 'parentId', 'kind', 'name', 'sourceRef']) for n in nodes],
                'workspaces': [pick(w, ['id', 'actor', 'node_id', 'branch']) for w in data.get('workspaces', [])],
                'links': {env: base + '/?' + urlencode({'screen': 'canvas', 'project': args.project, 'workspace': args.workspace, 'environment': env, 'mode': 'structure'}) for env in ['project', 'editor', 'live']}}
    if command == 'state':
        state = data.get('state', {})
        return {**pick(data, ['revision', 'readOnly']), 'counts': {k: len(state.get(k, [])) for k in ['settings', 'rules', 'decisions', 'nodes', 'tickets']}, 'note': 'Obsah vynechán; --raw jej vypíše v daném scope.'}
    if command == 'runs':
        return {**{k: v for k, v in data.items() if k not in ['handoffs', 'planning']},
                'handoffs': [pick(r, ['id', 'scope', 'status', 'digest', 'provider', 'model', 'verification']) for r in data.get('handoffs', [])],
                'planning': [pick(r, ['id', 'project_id', 'workspace', 'layer', 'status', 'digest']) for r in data.get('planning', [])],
                'note': 'API vrací omezené seznamy (typicky max 20 na zdroj), nikoli celý archiv.'}
    if command in ('run', 'export'):
        return {**pick(data, ['id', 'scope', 'status', 'digest', 'provider', 'model', 'budgetSeconds', 'verification', 'allowedFiles']), 'hasResult': bool(data.get('result')), 'hasContext': 'context' in data, 'eventCount': len(data.get('events', []))}
    if command == 'snapshot':
        packet = data.get('packet', {})
        return {**pick(data, ['id', 'digest', 'createdAt']), 'scope': packet.get('scope'), 'warnings': packet.get('warnings'), 'sourceManifest': packet.get('sourceManifest')}
    if command in ('node-text', 'node-spec'):
        out = pick(data, ['revision', 'readOnly', 'available'])
        out['contentLengths'] = ({'text': len(data.get('text', ''))} if command == 'node-text'
                                 else {k: len(v) for k, v in data.get('fields', {}).items() if isinstance(v, str)})
        out['note'] = 'Obsah vynechán; --raw jej vypíše.'
        return out
    return data


def required(args, *names):
    for name in names:
        if not getattr(args, name):
            raise ValueError('--' + name.replace('_', '-') + ' je pro tento příkaz povinné.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('command', choices=['status', 'projects', 'workspaces', 'view', 'state', 'runs', 'capabilities', 'run', 'snapshot', 'export', 'node-text', 'node-spec'])
    parser.add_argument('--project')
    parser.add_argument('--workspace')
    parser.add_argument('--node')
    parser.add_argument('--id')
    parser.add_argument('--raw', action='store_true', help='Vypíše plný obsah zvoleného scope; může být soukromý.')
    args = parser.parse_args()
    try:
        base = base_url(args.base_url)
        health = request(base, '/api/health')
        if health.get('status') != 'ok' or health.get('product') != 'Opora Canvas':
            raise ValueError('Adresa nevrací očekávanou identitu zdravého Opora Canvas.')
        command = args.command
        if command == 'status':
            data = {'health': health, 'baseUrl': base, 'writesPerformed': 0}
            try:
                data['backendIdentityAtStartup'] = request(base, '/api/build-identity')
            except HTTPError as error:
                if error.code != 404:
                    raise
                data['backendIdentityAtStartup'] = {'available': False, 'reason': 'endpoint404'}
            data['servedIndexSha256'] = hashlib.sha256(request(base, '/', binary=True)).hexdigest()
            bootstrap = request(base, '/api/bootstrap')
            data['projectCount'] = len(bootstrap.get('projects', []))
            data['note'] = 'Backend identity vzniká při startu; není důkazem verze později nasazeného frontendu.'
        elif command == 'projects':
            data = request(base, '/api/bootstrap')
        elif command in ('view', 'state', 'node-text', 'node-spec', 'snapshot'):
            required(args, 'project', 'workspace')
            params = {'project': args.project, 'workspace': args.workspace}
            routes = {'view': '/api/view', 'state': '/api/desktop-v3/state', 'node-text': '/api/node-text', 'node-spec': '/api/node-spec'}
            if command in ('node-text', 'node-spec'):
                required(args, 'node')
                params['node'] = args.node
            if command == 'snapshot':
                required(args, 'id')
                route = '/api/desktop-v3/packet/snapshots/' + quote(args.id, safe='')
            else:
                route = routes[command]
            data = request(base, route, params)
        elif command == 'workspaces':
            required(args, 'project')
            data = request(base, '/api/project-workspaces', {'project': args.project})
        elif command == 'capabilities':
            required(args, 'project')
            data = {'handoff': request(base, '/api/task-handoffs/capabilities', {'project': args.project}),
                    'planning': request(base, '/api/llm/capabilities'), 'coding': request(base, '/api/coding/capabilities')}
        elif command == 'runs':
            required(args, 'project', 'workspace')
            data = {'handoffs': [], 'planning': [], 'sourceErrors': {}}
            sources = [('handoffs', '/api/task-handoffs', {'project': args.project, 'workspace': args.workspace}),
                       ('planning', '/api/llm/runs', {'project': args.project})]
            for key, route, params in sources:
                try:
                    value = request(base, route, params)
                    rows = value if isinstance(value, list) else value.get('runs', [])
                    data[key] = [r for r in rows if (r.get('scope', {}).get('project') == args.project and r.get('scope', {}).get('workspace') == args.workspace)] if key == 'handoffs' else [r for r in rows if r.get('project_id') == args.project and r.get('workspace') == args.workspace]
                except (HTTPError, URLError, ValueError) as error:
                    data['sourceErrors'][key] = type(error).__name__ + (':' + str(error.code) if isinstance(error, HTTPError) else '')
        else:
            required(args, 'id', 'project', 'workspace')
            route = '/api/task-handoffs/' + quote(args.id, safe='') + ('/export' if command == 'export' else '')
            data = request(base, route)
            scope = data.get('scope', {})
            if data.get('id') != args.id or scope.get('project') != args.project or scope.get('workspace') != args.workspace:
                raise ValueError('Odpověď patří jinému běhu nebo scope; obsah nebyl vypsán.')
        out = data if args.raw else summary(command, data, args, base)
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2 if command == 'runs' and data.get('sourceErrors') else 0
    except HTTPError as error:
        print(json.dumps({'ok': False, 'error': 'HTTP ' + str(error.code), 'writesPerformed': 0}), file=sys.stderr)
    except (URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError) as error:
        print(json.dumps({'ok': False, 'error': str(error), 'writesPerformed': 0}, ensure_ascii=True), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
