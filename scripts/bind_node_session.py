"""Explicitně připojí skutečnou session k uzlu; nespouští model ani placený běh."""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8780')
    for field in ('project', 'workspace', 'node-id', 'session-id', 'title'):
        parser.add_argument('--' + field, required=True)
    parser.add_argument('--source', choices=['hermes', 'claude'], required=True)
    parser.add_argument('--role', choices=['orchestrator', 'worker'], required=True)
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--parent-session-id', default=None)
    parser.add_argument('--confirm', action='store_true', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    parsed = urllib.parse.urlsplit(base)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        parser.error('API musí být lokální HTTP origin bez dalších částí URL.')
    try:
        port = parsed.port
    except ValueError:
        parser.error('Neplatný port.')
    if port is None:
        parser.error('Uveďte explicitní port lokálního API.')
    payload = {'project': args.project, 'workspace': args.workspace, 'nodeId': args.node_id,
               'source': args.source, 'sessionId': args.session_id, 'runId': args.run_id,
               'role': args.role, 'title': args.title, 'parentSessionId': args.parent_session_id,
               'confirmed': args.confirm}
    if (args.source == 'hermes' and args.run_id is not None) or (args.source == 'claude' and not args.run_id):
        parser.error('Claude vyžaduje --run-id; Hermes používá pouze skutečné --session-id.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    def request(path, data=None):
        body = json.dumps(data).encode('utf-8') if data is not None else None
        req = urllib.request.Request(base + path, data=body,
                                     headers={'Origin': base, 'Content-Type': 'application/json'})
        with opener.open(req, timeout=20) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Odpověď API je příliš velká.')
            return json.loads(raw)
    try:
        bound = request('/api/node-sessions/bind', payload)
        query = urllib.parse.urlencode({k: payload[k] for k in ('project', 'workspace', 'nodeId')})
        page = request('/api/node-sessions?' + query)
        found = [s for s in page['sessions'] if s['id'] == bound['id'] and
                 all(s[k] == payload[k] for k in ('project', 'workspace', 'nodeId', 'source', 'sessionId'))]
        if len(found) != 1:
            raise ValueError('Zápis nebyl potvrzen následným čtením přesného uzlu.')
        row = found[0]
        print(json.dumps({'verified': True, **{k: row[k] for k in
                         ('id', 'source', 'sessionId', 'nodeId', 'status', 'sourceAvailable')}}, ensure_ascii=True))
        return 0
    except urllib.error.HTTPError as exc:
        print('Vazba nepotvrzena: HTTP ' + str(exc.code), file=sys.stderr)
    except (OSError, ValueError, KeyError) as exc:
        print('Vazba nepotvrzena: ' + type(exc).__name__, file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
