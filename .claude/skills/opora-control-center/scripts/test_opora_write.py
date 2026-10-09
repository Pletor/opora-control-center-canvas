"""Zapisovací skript nad falešnou sítí: `_open` se podvrhne, nic neodchází (docs/asistent.md §5.1)."""

import io
import json
import sys
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import opora_write  # noqa: E402

BASE = 'http://127.0.0.1:8741'
SCOPE = ['--project', 'p1', '--workspace', 'draft']


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def net(monkeypatch):
    calls = []
    behaviour = {'status': 200}

    def fake_open(req, timeout):
        calls.append({'method': req.get_method(), 'url': req.full_url, 'route': urlsplit(req.full_url).path,
                      'body': json.loads(req.data) if req.data else None,
                      'headers': {k.lower(): v for k, v in req.header_items()}})
        if behaviour['status'] != 200:
            body = io.BytesIO(json.dumps({'error': 'Revize nesouhlasí.'}).encode('utf-8'))
            raise HTTPError(req.full_url, behaviour['status'], 'x', Message(), body)
        return Response(json.dumps({'ok': True, 'revision': 4}).encode('utf-8'))

    monkeypatch.setattr(opora_write, '_open', fake_open)
    monkeypatch.setenv(opora_write.BASE_ENV, BASE)
    return calls, behaviour


def test_posts_allowed_route_with_scope_and_headers(net, capsys):
    calls, _ = net
    code = opora_write.main(['/api/node-spec', *SCOPE, '--json', '{"node": "n1", "expected_revision": 3}'])
    assert code == 0
    assert calls == [{'method': 'POST', 'url': BASE + '/api/node-spec', 'route': '/api/node-spec',
                      'body': {'node': 'n1', 'expected_revision': 3, 'project': 'p1', 'workspace': 'draft'},
                      'headers': calls[0]['headers']}]
    headers = calls[0]['headers']
    assert headers['content-type'] == 'application/json' and headers['origin'] == BASE
    assert json.loads(capsys.readouterr().out)['result'] == {'ok': True, 'revision': 4}


def test_every_write_is_reported_as_agent(net, monkeypatch):
    """Záznam činnosti (docs/zaznam-cinnosti.md): zápis skriptu nese X-Opora-Actor agenta."""
    calls, _ = net
    monkeypatch.setenv(opora_write.AGENT_ENV, 'Claude <Code> 1')
    opora_write.main(['/api/node-spec', *SCOPE, '--json', '{"node": "n1", "expected_revision": 3}'])
    monkeypatch.delenv(opora_write.AGENT_ENV)
    opora_write.main(['/api/node-spec', *SCOPE, '--json', '{"node": "n1", "expected_revision": 3}'])
    assert [c['headers']['x-opora-actor'] for c in calls] == ['agent; name=Claude Code 1', 'agent; name=agent']


def test_every_contract_route_is_allowed():
    assert opora_write.WRITE_ROUTES == {
        '/api/desktop-v3/lease',
        '/api/desktop-v3/realize-source',
        '/api/canvas-layout',
        '/api/desktop-v3/assignment-snapshot',
        '/api/canvas-versions',
        '/api/desktop-v3/rule', '/api/desktop-v3/decision',
        '/api/graph', '/api/node-spec', '/api/node-text', '/api/desktop-v3/state', '/api/desktop-v3/block',
        '/api/desktop-v3/agent-workspace', '/api/desktop-v3/agent-output', '/api/canvas-plan',
        '/api/desktop-v3/pipeline', '/api/brief-vault'}


def test_brief_vault_op_is_posted_with_scope_and_lease(net, monkeypatch):
    """Schránka zadání: op jde na /api/brief-vault s rozsahem; podcesty čtení zápisem nejsou."""
    calls, _ = net
    monkeypatch.setenv(opora_write.LEASE_ENV, 'a' * 64)
    body = {'op': 'split', 'fragmentId': 'f1', 'expectedRevision': 1, 'splitter': 'heading-number'}
    assert opora_write.main(['/api/brief-vault', *SCOPE, '--json', json.dumps(body)]) == 0
    assert calls[0]['route'] == '/api/brief-vault'
    assert calls[0]['body'] == {**body, 'project': 'p1', 'workspace': 'draft'}
    assert calls[0]['headers']['x-opora-lease'] == 'a' * 64
    for route in ('/api/brief-vault/fragment', '/api/brief-vault/research-brief', '/api/brief-vault/../graph'):
        assert opora_write.main([route, *SCOPE, '--json', '{}']) == 1
    assert len(calls) == 1


@pytest.mark.parametrize('route', ['/api/remove', '/api/local-project', '/api/node-spec/../remove', '/api/graph?x=1'])
def test_other_route_sends_nothing(net, route):
    calls, _ = net
    assert opora_write.main([route, *SCOPE, '--json', '{}']) == 1
    with pytest.raises(ValueError):
        opora_write.post(BASE, route, {})
    assert calls == []


def test_conflict_prints_conflict_and_exits_3(net, capsys):
    calls, behaviour = net
    behaviour['status'] = 409
    assert opora_write.main(['/api/desktop-v3/state', *SCOPE, '--json', '{"expectedRevision": 1}']) == 3
    captured = capsys.readouterr()
    assert captured.out.strip() == 'conflict: Revize nesouhlasí.'
    err = json.loads(captured.err)
    assert err['conflict'] is True and err['detail'] == 'Revize nesouhlasí.'
    assert len(calls) == 1


def test_other_http_error_exits_1(net, capsys):
    _, behaviour = net
    behaviour['status'] = 422
    assert opora_write.main(['/api/graph', *SCOPE, '--json', '{}']) == 1
    assert json.loads(capsys.readouterr().err)['error'] == 'HTTP 422'


@pytest.mark.parametrize('base', ['https://127.0.0.1:8741', 'http://example.com:80', 'http://127.0.0.1',
                                  'http://user:pw@127.0.0.1:1', 'http://127.0.0.1:1/api', ''])
def test_only_loopback_base(net, monkeypatch, base):
    calls, _ = net
    monkeypatch.setenv(opora_write.BASE_ENV, base)
    assert opora_write.main(['/api/graph', *SCOPE, '--json', '{}']) == 1
    assert calls == []


def test_base_url_argument_wins_over_env(net):
    calls, _ = net
    assert opora_write.main(['/api/graph', *SCOPE, '--json', '{}', '--base-url', 'http://localhost:9000']) == 0
    assert calls[0]['url'] == 'http://localhost:9000/api/graph'
    assert calls[0]['headers']['origin'] == 'http://localhost:9000'


def test_payload_must_match_scope_and_be_object(net):
    calls, _ = net
    assert opora_write.main(['/api/graph', *SCOPE, '--json', '{"project": "jiny"}']) == 1
    assert opora_write.main(['/api/graph', *SCOPE, '--json', '[1]']) == 1
    assert opora_write.main(['/api/graph', *SCOPE, '--json', '{nejson']) == 1
    assert opora_write.main(['/api/graph', *SCOPE]) == 1
    assert calls == []


def test_json_file(net, tmp_path):
    calls, _ = net
    path = tmp_path / 'payload.json'
    path.write_text('{"nodeId": "n1", "text": "Č"}', encoding='utf-8')
    assert opora_write.main(['/api/desktop-v3/block', *SCOPE, '--json-file', str(path)]) == 0
    assert calls[0]['body']['text'] == 'Č'
    assert opora_write.main(['/api/desktop-v3/block', *SCOPE, '--json-file', str(path), '--json', '{}']) == 1


def test_redirect_is_refused():
    with pytest.raises(ValueError):
        opora_write.NoRedirect().redirect_request(None, None, 302, 'x', {}, 'http://evil')


@pytest.mark.parametrize(("value", "expected"), [
    ("/api/node-spec", "/api/node-spec"),
    ("C:/Program Files/Git/api/node-spec", "/api/node-spec"),
    (r"C:\Program Files\Git\api\desktop-v3\block", "/api/desktop-v3/block"),
    ("C:/Program Files/Git/api/remove", "/api/remove"),
    ("api/node-spec", "api/node-spec"),
])
def test_msys_converted_route_is_restored_before_allowlist(value, expected):
    assert opora_write.route_of(value) == expected
    if expected == "/api/remove":
        assert expected not in opora_write.WRITE_ROUTES


def test_plan_draft_goes_to_canvas_plan_and_size_is_capped(net, tmp_path):
    calls, _ = net
    path = tmp_path / 'plan.json'
    path.write_text('{"dryRun": true, "plan": {"nodes": [], "edges": []}}', encoding='utf-8')
    assert opora_write.main(['/api/canvas-plan', *SCOPE, '--json-file', str(path)]) == 0
    assert calls[0]['body']['dryRun'] is True and calls[0]['body']['plan'] == {'nodes': [], 'edges': []}
    # Stejný strop jako koncept v approvals.py: 2 MiB projde, o bajt víc ne.
    assert opora_write.MAX_PAYLOAD == 2 * 1024 * 1024
    big = tmp_path / 'big.json'
    big.write_bytes(b'{"t": "' + b'x' * (opora_write.MAX_PAYLOAD - 8) + b'"}')
    assert big.stat().st_size == opora_write.MAX_PAYLOAD + 1
    assert opora_write.main(['/api/canvas-plan', *SCOPE, '--json-file', str(big)]) == 1
    assert len(calls) == 1


def test_dry_run_flag_sets_dry_run_even_when_draft_says_false(net, tmp_path):
    calls, _ = net
    path = tmp_path / 'plan.json'
    path.write_text('{"dryRun": false, "plan": {"nodes": [], "edges": []}}', encoding='utf-8')
    assert opora_write.main(['/api/canvas-plan', *SCOPE, '--json-file', str(path), '--dry-run']) == 0
    assert calls[0]['body']['dryRun'] is True
    assert opora_write.main(['/api/canvas-plan', *SCOPE, '--json-file', str(path)]) == 0
    assert calls[1]['body']['dryRun'] is False


def test_dry_run_flag_on_other_route_fails_without_sending(net, capsys):
    calls, _ = net
    assert opora_write.main(['/api/graph', *SCOPE, '--json', '{}', '--dry-run']) == 1
    assert calls == [] and '--dry-run' in capsys.readouterr().err


def test_documented_write_routes_match_the_allowlist():
    """Kritika #39: SKILL.md a api.md uvádějí přesně ty cesty, které skript pustí."""
    import pathlib
    import opora_write
    skill = pathlib.Path(__file__).resolve().parent.parent
    for doc in (skill / "SKILL.md", skill / "references" / "api.md"):
        text = doc.read_text(encoding="utf-8")
        missing = sorted(route for route in opora_write.WRITE_ROUTES if f"`{route}`" not in text)
        assert not missing, (doc.name, missing)


def test_lease_token_from_environment_is_sent_as_header(monkeypatch):
    import opora_write
    sent = {}
    monkeypatch.setattr(opora_write, "_read", lambda request, timeout: sent.update(request.headers) or {})
    monkeypatch.setenv("OPORA_LEASE_TOKEN", "a" * 64)
    opora_write.post("http://127.0.0.1:8740", "/api/desktop-v3/agent-output", {})
    assert sent["X-opora-lease"] == "a" * 64
    monkeypatch.setenv("OPORA_LEASE_TOKEN", "not-a-token")
    sent.clear()
    opora_write.post("http://127.0.0.1:8740", "/api/desktop-v3/agent-output", {})
    assert "X-opora-lease" not in sent
