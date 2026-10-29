"""Čtecí skript nad falešnou sítí: `_open` se podvrhne, nic neodchází (RLM: backend/brain_opora/decision/README.md)."""

import io
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import opora_read


def test_versions_returns_workspace_token_for_approved_save(net, monkeypatch, capsys):
    calls, answers = net
    answers['/api/canvas-versions'] = {'currentToken': 'version-token', 'dirty': True, 'versions': []}
    code, out, _ = run(monkeypatch, capsys, 'versions', *SCOPE)
    assert code == 0 and out['currentToken'] == 'version-token'
    assert calls[-1]['route'] == '/api/canvas-versions'


@pytest.mark.parametrize('kind', ['rule', 'decision'])
def test_read_one_memory_item(net, monkeypatch, capsys, kind):
    calls, answers = net
    answers['/api/desktop-v3/' + kind] = {'item': {'id': 'a', 'text': 'Exact original'}, 'revision': 3}
    code, out, _ = run(monkeypatch, capsys, kind, *SCOPE, '--id', 'a')
    assert code == 0
    assert calls[-1]['route'] == '/api/desktop-v3/' + kind
    assert out['item']['text'] == 'Exact original'


def test_frontier_waiting_takes_precedence_over_claim_and_dependencies():
    graph = {'nodes': [{'id': 's', 'kind': 'sector'},
                       {'id': 'a', 'kind': 'node', 'parentId': 's'},
                       {'id': 'b', 'kind': 'node', 'parentId': 's'}],
             'edges': [{'id': 'e', 'source': 'b', 'target': 'a'}]}
    state = {'nodes': {'a': {'blocks': [{'id': 'ask', 'title': 'Credentials',
                                        'state': {'status': 'blocked', 'note': 'Supply URL'}}]}}}
    result = opora_read.frontier(graph, state, 's', {'a': opora_read.CLAIM_PREFIX + ' agent'})
    assert result['claimed'] == []
    assert result['blocked'] == []
    assert [r['id'] for r in result['frontier']] == ['b']
    assert result['waiting'][0]['waitingOnHuman'] == [{'blockId': 'ask', 'ask': 'Supply URL'}]
    state['nodes']['a']['done'] = {'confirmed': True}
    result = opora_read.frontier(graph, state, 's', {})
    assert result['waiting'] == []
    assert [r['id'] for r in result['closed']] == ['a']

from backend.canvas.canvas_index import build_index
from backend.canvas.canvas_index import search as index_search

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
        parts = urlsplit(req.full_url)
        route = parts.path
        body = json.loads(req.data) if req.data else None
        if route == '/api/canvas-index':
            # Falešný server odpovídá skutečnou logikou indexu nad aktuálním grafem a stavem.
            query = {key: values[0] for key, values in parse_qs(parts.query).items()}
            entries = build_index(answers['/api/view']['graph'], answers['/api/desktop-v3/state']['state'])
            answers[route] = index_search(entries, query.get('q', ''), int(query.get('limit', 200)))
        calls.append({'method': req.get_method(), 'route': route, 'body': body, 'query': parse_qs(parts.query),
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
    # Skript nic neskládá: čte jen jednotný index plátna.
    assert [call['route'] for call in calls] == ['/api/health', '/api/canvas-index']
    assert out['matches'] == [{'id': 'a', 'name': 'Přihlášení', 'parentId': 'sec', 'kind': 'node',
                               'address': 'plan/prihlaseni', 'type': None, 'layer': None, 'status': None, 'kde': ['text']}]
    assert 'node-spec' in out['note']
    _, out, _ = run(monkeypatch, capsys, 'search', *SCOPE, '--query', 'prihlaseni')
    assert out['matches'][0]['kde'] == ['name', 'address', 'text']
    _, out, _ = run(monkeypatch, capsys, 'search', *SCOPE, '--query', 'nic', '--layer', 'sec')
    assert out['matches'] == []


def test_search_returns_at_most_twenty(net, monkeypatch, capsys):
    _, answers = net
    answers['/api/view'] = {'graph': {'nodes': [{'id': f'n{i}', 'parentId': None, 'kind': 'node', 'name': f'Karta {i}',
                                                 'purpose': ''} for i in range(30)], 'edges': []}}
    _, out, _ = run(monkeypatch, capsys, 'search', *SCOPE, '--query', 'karta')
    assert len(out['matches']) == 20 and out['total'] == 30 and out['truncated'] is True


def test_index_reports_chars_without_content(net, monkeypatch, capsys):
    calls, _ = net
    code, out, _ = run(monkeypatch, capsys, 'index', *SCOPE)
    assert code == 0 and posts(calls) == []
    rows = {row['id']: row for row in out['sections']}
    body = 'plan/prihlaseni\nPřihlášení\nÚčet uživatele\nŠifrování\nbcrypt\nŽádné ČÍSLO\nHeslo se ověří\nFormulář'
    assert rows['a'] == {'id': 'a', 'name': 'Přihlášení', 'parentId': 'sec', 'kind': 'node', 'chars': len(body),
                         'address': 'plan/prihlaseni', 'type': None, 'layer': None, 'status': None}
    assert rows['b']['chars'] == len('plan/platby\nPlatby') and out['count'] == 4
    # Pořadí indexu je podle adresy.
    _, out, _ = run(monkeypatch, capsys, 'index', *SCOPE, '--layer', 'sec')
    assert [row['id'] for row in out['sections']] == ['b', 'a']


def test_rank_sends_candidates_and_names_results(net, monkeypatch, capsys):
    calls, _ = net
    code, out, _ = run(monkeypatch, capsys, 'rank', *SCOPE, '--query', 'platby', '--layer', 'sec', '--top', '5')
    assert code == 0
    [call] = posts(calls)
    assert call['route'] == '/api/rlm/rank'
    assert set(call['body']) == {'project', 'workspace', 'query', 'candidates', 'top'}
    assert call['body']['top'] == 5 and call['body']['query'] == 'platby'
    # Pořadí indexu je podle adresy; text = adresa + typ + název + začátek korpusu.
    assert [c['id'] for c in call['body']['candidates']] == ['b', 'a']
    assert call['body']['candidates'][0] == {'id': 'b', 'text': 'plan/platby\nPlatby\nplan/platby\nPlatby'}
    assert out['ranked'] == [{'id': 'b', 'p': 0.7, 'name': 'Platby'}, {'id': 'a', 'p': 0.2, 'name': 'Přihlášení'}]


def test_rank_limits_candidates_and_text(net, monkeypatch, capsys):
    calls, answers = net
    answers['/api/view'] = {'graph': {'nodes': [{'id': f'n{i}', 'parentId': None, 'kind': 'node', 'name': 'K',
                                                 'purpose': 'x' * 1000} for i in range(300)], 'edges': []}}
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


def test_node_brief_summary_shows_start_and_length_of_card_text():
    text = "Zadání Jihlava, kap. Zpracování dat. " * 20
    data = {"schema": "opora.node-brief/1", "node": {"id": "n"}, "content": {"text": text, "revision": 3}}
    out = opora_read.summary("node-brief", data, None, None)
    assert out["content"] == {"start": text[:opora_read.CONTENT_PREVIEW], "length": len(text), "revision": 3}
    assert opora_read.summary("node-brief", {**data, "content": None}, None, None)["content"] is None


@pytest.mark.parametrize('command,route', [
    ('agent-workspace', '/api/desktop-v3/agent-workspace'), ('agent-results', '/api/desktop-v3/agent-results')])
def test_card_scoped_reads_send_node_id(net, monkeypatch, capsys, command, route):
    calls, answers = net
    answers[route] = {'revision': 4}
    code, out, _ = run(monkeypatch, capsys, command, *SCOPE, '--node', 'n1')
    assert code == 0 and out['revision'] == 4 and calls[-1]['route'] == route


def test_process_sync_reads_project_workspace_and_optional_node(net, monkeypatch, capsys):
    calls, answers = net
    answers['/api/oporahub/process'] = {'schema': 'opora.process-sync/1', 'scope': {'project': 'p1', 'workspace': 'draft'}, 'items': []}
    code, out, _ = run(monkeypatch, capsys, 'process-sync', *SCOPE)
    assert code == 0 and out['schema'] == 'opora.process-sync/1'
    assert calls[-1]['method'] == 'GET' and calls[-1]['route'] == '/api/oporahub/process'
    assert calls[-1]['query'] == {'project': ['p1'], 'workspace': ['draft']}
    code, _, _ = run(monkeypatch, capsys, 'process-sync', *SCOPE, '--node', 'node-7')
    assert code == 0 and calls[-1]['query'] == {'project': ['p1'], 'workspace': ['draft'], 'nodeId': ['node-7']}
    assert all(call['method'] == 'GET' for call in calls)


def test_frontier_without_node_reads_the_canvas_root_and_profiles_need_no_scope(net, monkeypatch, capsys):
    calls, answers = net
    answers['/api/desktop-v3/frontier'] = {'needsRouting': [{'id': 'n1'}]}
    code, out, _ = run(monkeypatch, capsys, 'frontier', *SCOPE)
    assert code == 0 and out['needsRouting'] == [{'id': 'n1'}]
    answers['/api/desktop-v3/pipeline-profiles'] = {'profiles': [{'id': 'goal'}]}
    code, out, _ = run(monkeypatch, capsys, 'pipeline-profiles')
    assert code == 0 and out['profiles'][0]['id'] == 'goal'


def test_node_brief_summary_carries_pipeline_and_output_request():
    stages = [{'id': 'a', 'status': 'passed'}, {'id': 'b', 'status': 'todo'}]
    data = {'node': {'id': 'n', 'checks': [{'id': 'unit', 'command': 'pytest'}], 'goal_mode': 'until_checks_pass'},
            'pipeline': {'profile': 'goal', 'routedBy': 'router-1', 'current': {'id': 'b'}, 'stuck': [], 'stages': stages},
            'outputContract': {'request': {'nodeId': 'n', 'expectedRevision': 2, 'contextVersion': 'f' * 64}}}
    out = opora_read.summary('node-brief', data, None, None)
    assert out['pipeline'] == {'profile': 'goal', 'routedBy': 'router-1', 'current': {'id': 'b'}, 'stuck': [], 'done': 1, 'total': 2}
    assert out['request']['expectedRevision'] == 2 and out['goalMode'] == 'until_checks_pass'
    assert opora_read.summary('node-brief', {'node': {}}, None, None)['pipeline'] is None


def test_vault_reads_tree_fragment_and_research_brief_by_get(net, monkeypatch, capsys):
    """Schránka zadání: tři GET čtení se správnými parametry; souhrn bez textů, --raw celé."""
    calls, answers = net
    coverage = {'leaves': 62, 'inserted': 20, 'saved': 42}
    answers['/api/brief-vault'] = {'readOnly': False, 'feedback': [], 'roots': [
        {'id': 'r1', 'title': '3. VRSTVA', 'scopeNodeId': 's3', 'revision': 1, 'chars': 17796, 'status': 'saved',
         'coverage': coverage, 'children': [{'id': 'c1', 'children': []}, {'id': 'c2', 'children': []}]}]}
    code, out, _ = run(monkeypatch, capsys, 'vault', *SCOPE, '--node', 's3')
    assert code == 0 and calls[-1]['route'] == '/api/brief-vault' and calls[-1]['query']['scope'] == ['s3']
    assert out['roots'] == [{'id': 'r1', 'title': '3. VRSTVA', 'scopeNodeId': 's3', 'revision': 1, 'chars': 17796,
                             'status': 'saved', 'children': 2, 'coverage': coverage}]
    code, out, _ = run(monkeypatch, capsys, 'vault', *SCOPE)
    assert 'scope' not in calls[-1]['query']
    answers['/api/brief-vault/fragment'] = {'fragment': {'id': 'c1', 'revision': 2, 'title': '3.37', 'text': 'Doslovně.', 'chars': 9},
                                           'latestRevision': 2, 'history': [{}, {}], 'children': [], 'cards': [], 'path': []}
    code, out, _ = run(monkeypatch, capsys, 'vault-fragment', *SCOPE, '--id', 'c1')
    assert code == 0 and calls[-1]['query']['id'] == ['c1'] and 'text' not in out['fragment'] and out['history'] == 2
    code, out, _ = run(monkeypatch, capsys, 'vault-fragment', *SCOPE, '--id', 'c1', '--raw')
    assert out['fragment']['text'] == 'Doslovně.'
    answers['/api/brief-vault/research-brief'] = {'schema': 'opora.brief-vault.research-brief/1', 'trust': {'data': ['goal']},
                                                 'target': {'id': 'c1'}, 'fragment': {'id': 'c1', 'text': 'x'}, 'research': [{}]}
    code, out, _ = run(monkeypatch, capsys, 'research-brief', *SCOPE, '--id', 'c1')
    assert code == 0 and calls[-1]['route'] == '/api/brief-vault/research-brief' and calls[-1]['query']['fragment'] == ['c1']
    assert out['trust'] == {'data': ['goal']} and out['counts']['research'] == 1 and 'text' not in out['fragment']
    assert all(call['method'] == 'GET' for call in calls)
    assert run(monkeypatch, capsys, 'research-brief', *SCOPE)[0] == 1


def test_get_waits_sixty_seconds_and_timeout_is_not_retried(monkeypatch, capsys):
    """Pomalý server: GET čeká 60 s; po vypršení skript skončí chybou a dotaz neopakuje (karta P1)."""
    seen = []

    def slow(req, timeout):
        seen.append(timeout)
        raise TimeoutError('timed out')

    monkeypatch.setattr(opora_read, '_open', slow)
    code, out, err = run(monkeypatch, capsys, 'view', *SCOPE)
    assert opora_read.GET_TIMEOUT == 60
    assert code == 1 and out is None and json.loads(err)['writesPerformed'] == 0
    assert seen == [60]


def test_drawing_reads_sketch_layer_and_summarizes(net, monkeypatch, capsys):
    calls, answers = net
    answers['/api/drawing'] = {'scene': {'elements': [{'type': 'arrow'}, {'type': 'text', 'text': 'tady zrychlit'},
                                                      {'type': 'text', 'text': 'x', 'isDeleted': True}]}, 'revision': 2}
    code, out, _ = run(monkeypatch, capsys, 'drawing', *SCOPE, '--layer', 'sb/n1/m-3f9a1c2e')
    assert code == 0 and out['elementCount'] == 2 and out['types'] == {'arrow': 1, 'text': 1} and out['texts'] == ['tady zrychlit']
    assert calls[-1]['method'] == 'GET' and calls[-1]['query']['layer'] == ['sb/n1/m-3f9a1c2e']
    code, _, err = run(monkeypatch, capsys, 'drawing', *SCOPE)
    assert code == 1 and '--layer' in err


def test_node_brief_summary_carries_architecture_slice_only_when_present():
    architecture = {'journeys': [{'id': 'j', 'name': 'Poptávka', 'actor': 'Majitel zahrady', 'pointA': 'Zahrada ho tíží.',
                                  'pointB': 'Má plán.', 'youAre': {'step': 'k', 'index': 1}, 'label': 'Formulář',
                                  'shift': 'Chce prohlídku.', 'objection': 'Bojí se telefonátů.',
                                  'next': [{'step': 'd', 'path': '/dekujeme', 'realized': True,
                                            'via': {'do': 'submit', 'section': 'form'}}]}],
                    'page': {'path': '/kontakt'}}
    data = {'node': {}, 'architecture': architecture}
    assert opora_read.summary('node-brief', data, None, None)['architecture'] == architecture
    assert 'architecture' not in opora_read.summary('node-brief', {'node': {}}, None, None)
