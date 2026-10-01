"""Čtecí skript nad falešnou sítí: `_open` se podvrhne, nic neodchází (docs/asistent.md §13.1, §13.3)."""

import io
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import opora_read

BASE = 'http://127.0.0.1:8741'
SCOPE = ['--project', 'p1', '--workspace', 'draft']

GRAPH = {'nodes': [
    {'id': 'sec', 'parentId': None, 'kind': 'sector', 'name': 'Plán', 'purpose': ''},
    {'id': 'a', 'parentId': 'sec', 'kind': 'node', 'name': 'Přihlášení', 'purpose': 'Účet uživatele'},
    {'id': 'b', 'parentId': 'sec', 'kind': 'node', 'name': 'Platby', 'purpose': ''},
    {'id': 'c', 'parentId': None, 'kind': 'node', 'name': 'Ostatní', 'purpose': 'nic'},
], 'edges': []}
STATE = {'nodes': {
    'a': {'criteria': [{'id': 'k1', 'text': 'Heslo se ověří'}], 'steps': [{'id': 's1', 'text': 'Formulář'}],
          'blocks': [{'id': 'b1', 'title': 'Šifrování', 'text': 'bcrypt', 'todos': [{'id': 't1', 'text': 'Žádné ČÍSLO'}]}]},
    'b': {'criteria': [], 'steps': [], 'blocks': []},
}}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def net(monkeypatch):
    """Falešná síť: zaznamená každý požadavek a odpoví podle cesty."""
    calls = []
    answers = {
        '/api/health': {'status': 'ok', 'product': 'Opora Canvas'},
        '/api/view': {'graph': GRAPH},
        '/api/desktop-v3/state': {'state': STATE, 'revision': 3},
        '/api/rlm/rank': {'status': 'ok', 'ranked': [{'id': 'b', 'p': 0.7}, {'id': 'a', 'p': 0.2}]},
    }

    def fake_open(req, timeout):
        route = urlsplit(req.full_url).path
        body = json.loads(req.data) if req.data else None
        calls.append({'method': req.get_method(), 'route': route, 'body': body,
                      'headers': {k.lower(): v for k, v in req.header_items()}, 'timeout': timeout})
        return Response(json.dumps(answers.get(route, {'ok': True})).encode('utf-8'))

    monkeypatch.setattr(opora_read, '_open', fake_open)
    monkeypatch.delenv(opora_read.BASE_ENV, raising=False)
    monkeypatch.delenv(opora_read.TOKEN_ENV, raising=False)
    return calls, answers


def run(monkeypatch, capsys, *argv, base=True):
    monkeypatch.setattr(sys, 'argv', ['opora_read.py', *(['--base-url', BASE] if base else []), *argv])
    code = opora_read.main()
    captured = capsys.readouterr()
    return code, (json.loads(captured.out) if captured.out else None), captured.err


def posts(calls):
    return [call for call in calls if call['method'] == 'POST']


def test_post_outside_allowlist_is_refused_before_network(net):
    calls, _ = net
    for route in ('/api/graph', '/api/desktop-v3/state', '/api/rlm/rank/x'):
        with pytest.raises(ValueError):
            opora_read.post_query(BASE, route, {'graph': {}})
    assert calls == []


def test_post_headers_are_json_and_same_origin(net):
    calls, _ = net
    opora_read.post_query(BASE, '/api/memory/recall', {'q': 1}, {'Authorization': 'Bearer x', 'Origin': 'evil'})
    headers = calls[0]['headers']
    assert headers['content-type'] == 'application/json'
    assert headers['origin'] == BASE
    assert headers['authorization'] == 'Bearer x'


def test_code_payload_is_exact(net, monkeypatch, capsys):
    calls, _ = net
    code, _, _ = run(monkeypatch, capsys, 'code', *SCOPE, '--path', 'frontend/app.tsx',
                     '--operation', 'references', '--line', '4', '--character', '2')
    assert code == 0
    [call] = posts(calls)
    assert call['route'] == '/api/code-intelligence/query'
    assert call['body'] == {'project': 'p1', 'workspace': 'draft', 'language': 'typescript', 'path': 'frontend/app.tsx',
                            'operation': 'references', 'line': 4, 'character': 2}
    assert call['headers']['content-type'] == 'application/json' and call['headers']['origin'] == BASE


def test_code_python_language_and_unknown_suffix(net, monkeypatch, capsys):
    calls, _ = net
    run(monkeypatch, capsys, 'code', *SCOPE, '--path', 'backend/x.py', '--operation', 'documentSymbols')
    assert posts(calls)[0]['body']['language'] == 'python'
    assert posts(calls)[0]['body']['line'] == 0 and posts(calls)[0]['body']['character'] == 0
    code, _, err = run(monkeypatch, capsys, 'code', *SCOPE, '--path', 'README.md', '--operation', 'hover')
    assert code == 1 and 'typescript' in err and len(posts(calls)) == 1


def test_find_payload_is_exact(net, monkeypatch, capsys):
    calls, _ = net
    assert run(monkeypatch, capsys, 'find', *SCOPE, '--query', 'kde se ukládá stav')[0] == 0
    [call] = posts(calls)
    assert call['route'] == '/api/semantic-search/query'
    assert call['body'] == {'project': 'p1', 'workspace': 'draft', 'path': '.', 'query': 'kde se ukládá stav', 'limit': 10}
    assert run(monkeypatch, capsys, 'find', *SCOPE, '--query', 'x', '--limit', '21')[0] == 1
    assert len(posts(calls)) == 1


def test_recall_payload_is_exact(net, monkeypatch, capsys):
    calls, _ = net
    assert run(monkeypatch, capsys, 'recall', *SCOPE, '--query', 'rozhodnutí', '--node', 'a')[0] == 0
    assert posts(calls)[0]['route'] == '/api/memory/recall'
    assert posts(calls)[0]['body'] == {'role': None, 'project': 'p1', 'workspace': 'draft', 'nodeId': 'a',
                                       'query': 'rozhodnutí', 'maxTokens': None}
    run(monkeypatch, capsys, 'recall', *SCOPE, '--query', 'q', '--role', 'architect', '--max-tokens', '500')
    assert posts(calls)[1]['body'] == {'role': 'architect', 'project': 'p1', 'workspace': 'draft', 'nodeId': None,
                                       'query': 'q', 'maxTokens': 500}
    assert run(monkeypatch, capsys, 'recall', *SCOPE, '--query', 'q')[0] == 1
    assert len(posts(calls)) == 2


def test_search_ignores_case_and_diacritics(net, monkeypatch, capsys):
    calls, _ = net
    code, out, _ = run(monkeypatch, capsys, 'search', *SCOPE, '--query', 'SIFROVANI cislo')
    assert code == 0 and posts(calls) == []
    assert [call['route'] for call in calls] == ['/api/health', '/api/view', '/api/desktop-v3/state']
    assert out['matches'] == [{'id': 'a', 'name': 'Přihlášení', 'parentId': 'sec', 'kde': ['blocks']}]
    assert 'node-spec' in out['note']
    _, out, _ = run(monkeypatch, capsys, 'search', *SCOPE, '--query', 'heslo formular')
    assert out['matches'][0]['kde'] == ['criteria', 'steps']
    _, out, _ = run(monkeypatch, capsys, 'search', *SCOPE, '--query', 'nic', '--layer', 'sec')
    assert out['matches'] == []


def test_search_returns_at_most_twenty(net, monkeypatch, capsys):
    _, answers = net
    answers['/api/view'] = {'graph': {'nodes': [{'id': f'n{i}', 'parentId': None, 'kind': 'node', 'name': f'Karta {i}'}
                                                for i in range(30)]}}
    _, out, _ = run(monkeypatch, capsys, 'search', *SCOPE, '--query', 'karta')
    assert len(out['matches']) == 20 and out['total'] == 30 and out['truncated'] is True


def test_index_reports_chars_without_content(net, monkeypatch, capsys):
    calls, _ = net
    code, out, _ = run(monkeypatch, capsys, 'index', *SCOPE)
    assert code == 0 and posts(calls) == []
    rows = {row['id']: row for row in out['sections']}
    body = 'Účet uživatele\nŠifrování\nbcrypt\nŽádné ČÍSLO\nHeslo se ověří\nFormulář'
    assert rows['a'] == {'id': 'a', 'name': 'Přihlášení', 'parentId': 'sec', 'kind': 'node', 'chars': len(body)}
    assert rows['b']['chars'] == 0 and out['count'] == 4
    _, out, _ = run(monkeypatch, capsys, 'index', *SCOPE, '--layer', 'sec')
    assert [row['id'] for row in out['sections']] == ['a', 'b']


def test_rank_sends_candidates_and_names_results(net, monkeypatch, capsys):
    calls, _ = net
    code, out, _ = run(monkeypatch, capsys, 'rank', *SCOPE, '--query', 'platby', '--layer', 'sec', '--top', '5')
    assert code == 0
    [call] = posts(calls)
    assert call['route'] == '/api/rlm/rank'
    assert set(call['body']) == {'project', 'workspace', 'query', 'candidates', 'top'}
    assert call['body']['top'] == 5 and call['body']['query'] == 'platby'
    assert [c['id'] for c in call['body']['candidates']] == ['a', 'b']
    assert call['body']['candidates'][1] == {'id': 'b', 'text': 'Platby'}
    assert out['ranked'] == [{'id': 'b', 'p': 0.7, 'name': 'Platby'}, {'id': 'a', 'p': 0.2, 'name': 'Přihlášení'}]


def test_rank_limits_candidates_and_text(net, monkeypatch, capsys):
    calls, answers = net
    answers['/api/view'] = {'graph': {'nodes': [{'id': f'n{i}', 'parentId': None, 'kind': 'node', 'name': 'K',
                                                 'purpose': 'x' * 1000} for i in range(300)]}}
    answers['/api/rlm/rank'] = {'status': 'unavailable'}
    _, out, _ = run(monkeypatch, capsys, 'rank', *SCOPE, '--query', 'q')
    candidates = posts(calls)[0]['body']['candidates']
    assert len(candidates) == 255 and all(len(c['text']) <= 300 for c in candidates)
    assert out['status'] == 'unavailable' and out['candidatesTruncated'] is True and 'ranked' not in out
    assert run(monkeypatch, capsys, 'rank', *SCOPE, '--query', 'q', '--top', '51')[0] == 1


def test_base_url_defaults_to_env(net, monkeypatch, capsys):
    monkeypatch.setenv(opora_read.BASE_ENV, 'http://127.0.0.1:9123')
    seen = []
    original = opora_read._open
    monkeypatch.setattr(opora_read, '_open', lambda req, timeout: seen.append(req.full_url) or original(req, timeout))
    assert run(monkeypatch, capsys, 'index', *SCOPE, base=False)[0] == 0
    assert seen and all(url.startswith('http://127.0.0.1:9123/api/') for url in seen)


def test_env_base_must_be_loopback_and_explicit_flag_wins(net, monkeypatch, capsys):
    calls, _ = net
    monkeypatch.setenv(opora_read.BASE_ENV, 'http://example.com:80')
    code, _, _ = run(monkeypatch, capsys, 'index', *SCOPE, base=False)
    assert code == 1 and calls == []
    assert run(monkeypatch, capsys, 'index', *SCOPE)[0] == 0


def test_without_any_base_it_refuses(net, monkeypatch, capsys):
    calls, _ = net
    code, _, err = run(monkeypatch, capsys, 'index', *SCOPE, base=False)
    assert code == 1 and 'právě jedno' in json.loads(err)['error'] and calls == []
