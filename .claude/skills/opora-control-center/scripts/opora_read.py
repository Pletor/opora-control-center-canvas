"""Čtecí klient OPORA: pouze GET na loopback server, nebo na vlastní tunel s tokenem.

`--base-url http://127.0.0.1:PORT` je domácí režim beze změny.
`--api-base https://HOST` je vzdálený režim: jde jen s tokenem v proměnné prostředí
`OPORA_ACCESS_TOKEN` (nikdy v příkazu ani v logu) a posílá `Authorization: Bearer` a `Origin`.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_BYTES = 8 * 1024 * 1024
TOKEN_ENV = 'OPORA_ACCESS_TOKEN'


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


def remote_base(value, token):
    """Vzdálená adresa: jen https bez cesty a bez přihlašovacích údajů, a jen s tokenem z prostředí."""
    parts = urlsplit(value)
    if (parts.scheme != 'https' or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.path not in ('', '/') or parts.query or parts.fragment):
        raise ValueError('Použijte --api-base https://HOST bez cesty a přihlašovacích údajů.')
    if not token:
        raise ValueError('Vzdálený přístup vyžaduje token v proměnné prostředí ' + TOKEN_ENV + ' (nikdy v příkazu).')
    base = value.rstrip('/')
    return base, {'Authorization': 'Bearer ' + token, 'Origin': base}


def request(base, route, params=None, binary=False, headers=None):
    suffix = '?' + urlencode(params) if params else ''
    sent = {'Accept': '*/*' if binary else 'application/json', **(headers or {})}
    req = Request(base + route + suffix, headers=sent, method='GET')
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
    if command == 'sessions':
        rows = data if isinstance(data, list) else data.get('sessions', data.get('bindings', []))
        out = pick(data, ['truncated']) if isinstance(data, dict) else {}
        out['sessions'] = [pick(r, ['id', 'nodeId', 'source', 'sessionId', 'runId', 'role', 'title', 'running', 'recent_activity', 'closedAt']) for r in rows]
        out['note'] = 'Telemetrie pouze pro čtení (limit 100). running = ověřený proces; recent_activity = uložená událost.'
        return out
    if command == 'snapshot':
        packet = data.get('packet', {})
        return {**pick(data, ['id', 'digest', 'createdAt']), 'scope': packet.get('scope'), 'warnings': packet.get('warnings'), 'sourceManifest': packet.get('sourceManifest')}
    if command == 'node-brief':
        node = data.get('node', {})
        return {'schema': data.get('schema'), 'readOnly': data.get('readOnly'), 'node': pick(node, ['id', 'name', 'kind', 'path', 'sourceRef']),
                'goal': data.get('goal'), 'phase': data.get('harness', {}).get('phase'),
                'stopConditions': data.get('harness', {}).get('stopConditions'), 'loop': data.get('loop'),
                'note': 'Souhrn; celý balíček pro model vypíše --raw.'}
    if command in ('node-text', 'node-spec'):
        out = pick(data, ['revision', 'readOnly', 'available'])
        out['contentLengths'] = ({'text': len(data.get('text', ''))} if command == 'node-text'
                                 else {k: len(v) for k, v in data.get('fields', {}).items() if isinstance(v, str)})
        out['note'] = 'Obsah vynechán; --raw jej vypíše.'
        return out
    return data


CLAIM_PREFIX = 'Převzato:'
TICKET_TYPES = ('research', 'prototype', 'grilling', 'task')


def ticket_type(name):
    match = re.match(r'\[(\w+)\]', name or '')
    return match.group(1) if match and match.group(1) in TICKET_TYPES else ''


def claim_of(frame):
    for line in (frame or '').splitlines():
        if line.strip().startswith(CLAIM_PREFIX):
            return line.strip()[len(CLAIM_PREFIX):].strip()
    return ''


def frontier(graph, state, sector_id, frames):
    """Mapa wayfinderu nad sektorem: karty sektoru rozdělené na uzavřené, převzaté, blokované a frontier.

    Blokace je vazba `next` (nebo bez portu) z neuzavřené karty. Převzetí je řádek `Převzato:`
    v `agent-workspace.frame`. Pořadí karet je pořadí v grafu.
    """
    nodes = graph.get('nodes', [])
    sector = next((n for n in nodes if n.get('id') == sector_id), None)
    if sector is None or sector.get('kind') != 'sector':
        raise ValueError('--node musí být ID sektoru (mapy) v tomto workspace.')
    names = {n['id']: n.get('name', '') for n in nodes}
    cards = [n for n in nodes if n.get('parentId') == sector_id and n.get('kind') == 'node']
    done = {cid: bool(state.get('nodes', {}).get(cid, {}).get('done', {}).get('confirmed')) for cid in names}
    out = {'map': {'id': sector_id, 'name': sector.get('name', '')}, 'frontier': [], 'claimed': [], 'blocked': [], 'closed': []}
    for card in cards:
        cid = card['id']
        row = {'id': cid, 'name': card.get('name', ''), 'type': ticket_type(card.get('name'))}
        blockers = [e['source'] for e in graph.get('edges', [])
                    if e.get('target') == cid and e.get('port', 'next') == 'next' and not done.get(e.get('source'), False)]
        claim = claim_of(frames.get(cid, ''))
        if done[cid]:
            out['closed'].append(row)
        elif claim:
            out['claimed'].append({**row, 'claim': claim})
        elif blockers:
            out['blocked'].append({**row, 'blockedBy': [{'id': b, 'name': names.get(b, '')} for b in blockers]})
        else:
            out['frontier'].append(row)
    ids = {sector_id, *(c['id'] for c in cards)}
    out['decisions'] = [pick(d, ['id', 'text', 'nodeId', 'pinned', 'by', 'createdAt']) for d in state.get('decisions', []) if d.get('nodeId') in ids]
    out['fog'] = [{'id': n['id'], 'name': n.get('name', '')} for n in nodes if n.get('parentId') == sector_id and n.get('kind') == 'comment']
    return out


def required(args, *names):
    for name in names:
        if not getattr(args, name):
            raise ValueError('--' + name.replace('_', '-') + ' je pro tento příkaz povinné.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', help='domácí adresa http://127.0.0.1:PORT')
    parser.add_argument('--api-base', help='vzdálená adresa tunelu https://HOST; vyžaduje ' + TOKEN_ENV)
    parser.add_argument('command', choices=['status', 'projects', 'workspaces', 'view', 'state', 'sessions', 'snapshot', 'node-text', 'node-spec', 'node-brief', 'frontier'])
    parser.add_argument('--project')
    parser.add_argument('--workspace')
    parser.add_argument('--node')
    parser.add_argument('--id')
    parser.add_argument('--raw', action='store_true', help='Vypíše plný obsah zvoleného scope; může být soukromý.')
    args = parser.parse_args()
    try:
        if bool(args.base_url) == bool(args.api_base):
            raise ValueError('Zadejte právě jedno: --base-url pro loopback, nebo --api-base pro tunel.')
        if args.api_base:
            base, headers = remote_base(args.api_base, os.environ.get(TOKEN_ENV, '').strip())
        else:
            base, headers = base_url(args.base_url), {}

        def fetch(route, params=None, binary=False):
            return request(base, route, params, binary, headers)

        health = fetch('/api/health')
        if health.get('status') != 'ok' or health.get('product') != 'Opora Canvas':
            raise ValueError('Adresa nevrací očekávanou identitu zdravého Opora Canvas.')
        command = args.command
        if command == 'status':
            data = {'health': health, 'baseUrl': base, 'writesPerformed': 0}
            try:
                data['backendIdentityAtStartup'] = fetch('/api/build-identity')
            except HTTPError as error:
                if error.code != 404:
                    raise
                data['backendIdentityAtStartup'] = {'available': False, 'reason': 'endpoint404'}
            data['servedIndexSha256'] = hashlib.sha256(fetch('/', binary=True)).hexdigest()
            bootstrap = fetch('/api/bootstrap')
            data['projectCount'] = len(bootstrap.get('projects', []))
            data['note'] = 'Backend identity vzniká při startu; není důkazem verze později nasazeného frontendu.'
        elif command == 'projects':
            data = fetch('/api/bootstrap')
        elif command in ('node-brief', 'frontier'):
            required(args, 'project', 'workspace', 'node')
            params = {'project': args.project, 'workspace': args.workspace}
            if command == 'node-brief':
                data = fetch('/api/desktop-v3/node-brief', {**params, 'nodeId': args.node})
            else:
                graph = fetch('/api/view', params).get('graph', {})
                state = fetch('/api/desktop-v3/state', params).get('state', {})
                open_cards = [n['id'] for n in graph.get('nodes', []) if n.get('parentId') == args.node and n.get('kind') == 'node'
                              and not state.get('nodes', {}).get(n['id'], {}).get('done', {}).get('confirmed')]
                frames = {cid: fetch('/api/desktop-v3/agent-workspace', {**params, 'nodeId': cid}).get('workspace', {}).get('frame', '') for cid in open_cards}
                data = frontier(graph, state, args.node, frames)
        elif command in ('view', 'state', 'node-text', 'node-spec', 'snapshot', 'sessions'):
            required(args, 'project', 'workspace')
            params = {'project': args.project, 'workspace': args.workspace}
            routes = {'view': '/api/view', 'state': '/api/desktop-v3/state', 'node-text': '/api/node-text', 'node-spec': '/api/node-spec', 'sessions': '/api/node-sessions'}
            if command in ('node-text', 'node-spec'):
                required(args, 'node')
                params['node'] = args.node
            if command == 'sessions' and args.node:
                params['nodeId'] = args.node
            if command == 'snapshot':
                required(args, 'id')
                route = '/api/desktop-v3/packet/snapshots/' + quote(args.id, safe='')
            else:
                route = routes[command]
            data = fetch(route, params)
        else:
            required(args, 'project')
            data = fetch('/api/project-workspaces', {'project': args.project})
        out = data if args.raw else summary(command, data, args, base)
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0
    except HTTPError as error:
        print(json.dumps({'ok': False, 'error': 'HTTP ' + str(error.code), 'writesPerformed': 0}), file=sys.stderr)
    except (URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError) as error:
        print(json.dumps({'ok': False, 'error': str(error), 'writesPerformed': 0}, ensure_ascii=True), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
