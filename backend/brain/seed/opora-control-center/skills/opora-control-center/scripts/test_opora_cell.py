"""Spustitelná buňka end-to-end (docs/schranka-bunka.md §4): skutečný server na loopbacku nad dočasnou složkou,
navrhovatel, potvrzovatel, vykonavatel a ověřovatel jako různí aktéři přes `opora_cycle.py`; kontroly se opravdu
spustí. Kolo 1: artefakt chybí → `tests: fail` → antipattern a nové kolo. Kolo 2: artefakt hotový → `pass` → pattern."""

import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[7]))

import opora_cycle  # noqa: E402

PROJECT = 'draft'
CHECKS = [{'id': 'unit', 'command': 'python -m pytest -q test_slug.py'}]
SYNTH = {'type': 'TOOL', 'done': 'Funkce slug(text) vrací malá písmena s pomlčkami a test_slug.py projde.',
         'prediction': {'tests': 'pass', 'criticRounds': 0, 'risk': 'diakritika'},
         'steps': ['Napiš slug.py s funkcí slug.'], 'checks': CHECKS}
TEST_SLUG = 'from slug import slug\n\n\ndef test_slug():\n    assert slug("Ahoj Svete") == "ahoj-svete"\n'
SLUG = 'def slug(text):\n    return "-".join(text.lower().split())\n'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture
def live(tmp_path, monkeypatch):
    import uvicorn

    from backend.app.factory import create_app

    port = free_port()
    monkeypatch.setenv('OPORA_CANVAS_PORT', str(port))
    base = f'http://127.0.0.1:{port}'
    server = uvicorn.Server(uvicorn.Config(create_app(tmp_path / 'data'), host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    monkeypatch.setenv('OPORA_BASE_URL', base)
    for name in ('OPORA_AGENT_NAME', 'OPORA_LEASE_TOKEN', 'OPORA_ACTOR'):
        monkeypatch.delenv(name, raising=False)
    with httpx.Client(base_url=base, headers={'Origin': base}) as http:
        scope = {'project': PROJECT, 'workspace': 'draft'}
        digest = http.get('/api/view', params=scope).json()['digest']
        graph = {'nodes': [{'id': 's1', 'parentId': None, 'kind': 'sector', 'name': 's1', 'purpose': '', 'x': 0, 'y': 0}],
                 'edges': []}
        assert http.post('/api/graph', json={**scope, 'graph': graph, 'digest': digest}).status_code == 200
        yield http, scope
    server.should_exit = True
    thread.join(timeout=10)


def cycle(capsys, actor, *argv):
    code = opora_cycle.main(list(argv) + ['--project', PROJECT, '--workspace', 'draft', '--actor', actor])
    out = json.loads(capsys.readouterr().out)
    return code, out


def ok(capsys, actor, *argv):
    code, out = cycle(capsys, actor, *argv)
    assert code == 0, out
    return out


def propose(capsys, tmp_path, fragment, gate, payload):
    path = tmp_path / f'{gate}.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    ok(capsys, 'navrhovatel', 'propose', fragment, gate, '--json-file', str(path), '--note', f'návrh {gate}')


def confirm(capsys, fragment, gate):
    return ok(capsys, 'potvrzovatel', 'yes', fragment, gate, '--note', f'potvrzeno {gate}')


def detail(http, scope, fragment):
    return http.get('/api/brief-vault/fragment', params={**scope, 'id': fragment}).json()


def card_of(http, scope, fragment):
    """Uzel grafu karty (nese checks a goal_mode), jejíž stav odkazuje na fragment."""
    nodes = http.get('/api/desktop-v3/state', params=scope).json()['state']['nodes']
    card = next(key for key, node in nodes.items()
                if any(ref.get('fragmentId') == fragment for ref in node.get('fragmentRefs') or []))
    return next(node for node in http.get('/api/view', params=scope).json()['graph']['nodes'] if node['id'] == card)


def through_placed(capsys, tmp_path, fragment):
    confirm(capsys, fragment, 'scoped')
    propose(capsys, tmp_path, fragment, 'weighed', {'benefit': 'Čitelné adresy.', 'risk': 'Kolize slugů.'})
    confirm(capsys, fragment, 'weighed')
    propose(capsys, tmp_path, fragment, 'synthesized', SYNTH)
    confirm(capsys, fragment, 'synthesized')
    propose(capsys, tmp_path, fragment, 'decided', {'verdict': 'yes', 'reason': 'Malé a ověřitelné testem.'})
    confirm(capsys, fragment, 'decided')
    confirm(capsys, fragment, 'planned')
    confirm(capsys, fragment, 'placed')


def test_one_pass_from_brief_to_verified_lesson(live, capsys, tmp_path):
    http, scope = live
    created = http.post('/api/brief-vault', headers={'X-Opora-Actor': 'agent; name=zadavatel'},
                        json={**scope, 'op': 'create', 'scopeNodeId': 's1', 'discipline': 'be', 'title': 'Slug',
                              'text': 'Potřebujeme funkci slug pro čitelné adresy.'})
    assert created.status_code == 200, created.text
    fragment = created.json()['fragment']['id']
    work, checks_dir = tmp_path / 'work', tmp_path / 'checks'
    work.mkdir()
    checks_dir.mkdir()
    (checks_dir / 'test_slug.py').write_text(TEST_SLUG, encoding='utf-8')  # napsáno při synthesized, mimo vykonavatele

    through_placed(capsys, tmp_path, fragment)
    card = card_of(http, scope, fragment)
    assert card['checks'] == CHECKS and card['goal_mode'] == 'until_checks_pass'

    # Kolo 1: vykonavatel dodal jen podvržený test `assert True` a žádný slug.py → platí pravý test z checks, běh selže.
    (work / 'test_slug.py').write_text('def test_slug():\n    assert True\n', encoding='utf-8')
    code, _ = cycle(capsys, 'vykonavatel', 'run-checks', fragment, '--root', str(work), '--tests', str(checks_dir), '--executor', 'vykonavatel')
    assert code == 2  # vykonavatel nesmí ověřovat sám sebe
    ran = ok(capsys, 'overovatel', 'run-checks', fragment, '--root', str(work), '--tests', str(checks_dir), '--executor', 'vykonavatel')
    assert ran['tests'] == 'fail' and ran['checks'][0]['exitCode'] != 0  # podvrh nepomohl
    code, _ = cycle(capsys, 'vykonavatel', 'yes', fragment, 'verified', '--note', 'sám sobě')
    assert code != 0  # vykonavatel bránu verified nezapne
    verified = confirm(capsys, fragment, 'verified')
    assert verified['gates']['verified'] is True
    stored = detail(http, scope, fragment)['gateDetail']['verified']['payload']['actual']
    assert stored['tests'] == 'fail' and stored['run']['executor'] == 'vykonavatel' and stored['run']['verifier'] == 'overovatel'
    code, _ = cycle(capsys, 'navrhovatel', 'propose', fragment, 'learned', '--json',
                      json.dumps({'lesson': 'Funguje vždy.', 'kind': 'pattern'}), '--note', 'špatný druh')
    assert code != 0  # po neúspěchu jen antipattern
    propose(capsys, tmp_path, fragment, 'learned', {'lesson': 'Bez funkce test padá na importu; nejdřív modul.',
                                                    'kind': 'antipattern'})
    confirm(capsys, fragment, 'learned')

    # Nové kolo od synthesized se stejnou kontrolou; vykonavatel dodá funkci.
    ok(capsys, 'potvrzovatel', 'no', fragment, 'synthesized', '--note', 'Kolo 1: test padá, chybí slug.py')
    (work / 'slug.py').write_text(SLUG, encoding='utf-8')
    propose(capsys, tmp_path, fragment, 'synthesized', SYNTH)
    confirm(capsys, fragment, 'synthesized')
    propose(capsys, tmp_path, fragment, 'decided', {'verdict': 'yes', 'reason': 'Oprava kola 1.'})
    confirm(capsys, fragment, 'decided')
    confirm(capsys, fragment, 'planned')
    confirm(capsys, fragment, 'placed')
    ran = ok(capsys, 'overovatel', 'run-checks', fragment, '--root', str(work), '--tests', str(checks_dir), '--executor', 'vykonavatel',
             '--plan-score', '9')
    assert ran['tests'] == 'pass' and ran['checks'][0]['exitCode'] == 0
    confirm(capsys, fragment, 'verified')
    found = detail(http, scope, fragment)
    actual = found['gateDetail']['verified']['payload']['actual']
    assert actual['tests'] == 'pass' and actual['planApproved'] is True and len(actual['run']['checks'][0]['outputSha256']) == 64
    # Běh je jen nahlášený (docs/schranka-bunka.md §5); návrh se i s razítkem serveru počítá jako použitý.
    assert found['gateDetail']['verified']['payload']['runTrust'] == 'reported'
    assert found['proposals']['verified']['status'] == 'used'
    propose(capsys, tmp_path, fragment, 'learned', {'lesson': 'Slug: modul a test v jednom kroku, kontrola pytest.',
                                                    'kind': 'pattern'})
    learned = confirm(capsys, fragment, 'learned')
    assert learned['gateStep'] == 8
    lessons = ok(capsys, 'navrhovatel', 'lessons', '--discipline', 'be')
    assert 'Slug' in json.dumps(lessons, ensure_ascii=False)
