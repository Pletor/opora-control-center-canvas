"""Duel změny směru end-to-end (docs/schranka-duel.md): skutečný server na loopbacku nad dočasnou složkou, zadavatel,
navrhovatel (strana B), obhájce (strana A), soudce a člověk jako různí aktéři přes `opora_cycle.py duel`.
Duel 1: grill → odpověď → hodnocení → `adopt` (pattern); vítězný směr se uplatní sám (nový text předmětu, brány
zneplatněné, `/next` ho vrací od scoped). Duel 2: platný směr obstojí → `keep` (antipattern), předmět beze změny."""

import json
import math
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
P0_LOGIT = math.log(0.35 / 0.65)


def sigma(x):
    return 1 / (1 + math.exp(-x))


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
    return code, json.loads(capsys.readouterr().out)


def duel(capsys, actor, *argv):
    return cycle(capsys, actor, 'duel', *argv)


def ok(capsys, actor, *argv):
    code, out = duel(capsys, actor, *argv)
    assert code == 0, out
    return out


def make_fragment(http, scope, title, text):
    created = http.post('/api/brief-vault', headers={'X-Opora-Actor': 'agent; name=zadavatel'},
                        json={**scope, 'op': 'create', 'scopeNodeId': 's1', 'discipline': 'be', 'title': title, 'text': text})
    assert created.status_code == 200, created.text
    return created.json()['fragment']['id']


def open_duel(capsys, fragment, incumbent, challenger):
    out = ok(capsys, 'navrh', 'open', '--subject-kind', 'fragment', '--subject', fragment, '--incumbent', incumbent,
             '--challenger', challenger, '--scope', 's1')
    assert out['op'] == 'duel-open' and out['id'] and out['status'] == 'open'
    return out['id']


def turn(capsys, actor, duel_id, side, kind, text, *extra):
    return ok(capsys, actor, 'turn', duel_id, '--side', side, '--kind', kind, '--text', text, *extra)


def score(capsys, duel_id, turn_id, strength, supports, actor='soudce', *extra):
    return ok(capsys, actor, 'score', duel_id, '--turn', turn_id, '--strength', str(strength), '--supports', supports, *extra)


def test_duel_adopt_then_keep_with_lessons_and_trajectory(live, capsys):
    http, scope = live
    text_a = 'Přihlášení jen heslem.'
    f1 = make_fragment(http, scope, 'Přihlášení', text_a)

    # Člověk = prohlížeč s dokladem UI (cookie) a bez X-Opora-Actor.
    session = http.get('/api/access/ui-session', headers={'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors'})
    assert session.status_code == 200
    # Člověk (HTTP bez X-Opora-Actor) založí představu rozsahu; agent to smět nesmí.
    vision = {**scope, 'op': 'vision-set', 'text': 'Přihlášení je jednoduché a bezpečné.', 'scopeNodeId': 's1',
              'note': 'představa'}
    assert http.post('/api/brief-vault', headers={'X-Opora-Actor': 'agent; name=navrh'}, json=vision).status_code == 403
    assert http.post('/api/brief-vault', json=vision).status_code == 200

    # f1 už prošel bránou scoped; po přijetí nového směru se brány zneplatní a smyčka jde od scoped znovu.
    scoped = http.post('/api/brief-vault', headers={'X-Opora-Actor': 'agent; name=zadavatel'},
                       json={**scope, 'op': 'gate', 'fragmentId': f1, 'expectedRevision': 1, 'gate': 'scoped',
                             'value': True, 'note': 'scoped'})
    assert scoped.status_code == 200, scoped.text

    # Konkurent ve frontě be (nezablokovaný, čeká na scoped): duel musí být hlavou i za jeho přítomnosti.
    rival = make_fragment(http, scope, 'Konkurent', 'Konkurenční zadání ve frontě.')
    # Před duelem je konkurent způsobilou hlavou TÉŽE fronty (be), kterou níž kontroluje priorita duelu.
    code, before = cycle(capsys, 'obhajce', 'next', '--discipline', 'be')
    assert code == 0 and before['fragment']['id'] == rival and before['gate'] == 'scoped'
    assert not before['blockedBy'].get('duel')
    # Duel 1: předmět f1 zmizí z fronty, hlavou be je duel (ne konkurent).
    d1 = open_duel(capsys, f1, text_a, 'Přihlášení e-mailem s jednorázovým kódem.')
    code, nxt = cycle(capsys, 'obhajce', 'next', '--discipline', 'be')
    assert code == 0 and nxt['needs'] == 'duel' and nxt['fragment']['id'] == d1 and nxt['blockedBy']['duel'] >= 1
    assert nxt['fragment']['id'] != rival
    assert nxt['subject'] == {'kind': 'fragment', 'id': f1}
    code, second = duel(capsys, 'navrh', 'open', '--subject-kind', 'fragment', '--subject', f1, '--incumbent', 'x',
                        '--challenger', 'y', '--scope', 's1')
    assert code == 3  # druhý otevřený duel téhož předmětu

    a1 = turn(capsys, 'obhajce', d1, 'A', 'claim', 'Heslo stačí, kód přidá závislost na e-mailu.')['turnId']
    g1 = turn(capsys, 'obhajce', d1, 'A', 'grill', 'Co když e-mail nedojde?')
    assert g1['onTurn'] == [{'side': 'B', 'grillId': g1['turnId']}] and g1['rounds'] == {'A': 1, 'B': 0}
    g1 = g1['turnId']

    code, out = duel(capsys, 'obhajce', 'turn', d1, '--side', 'B', '--kind', 'claim', '--text', 'Hájím i B')
    assert code == 1 and 'různé aktéry' in out['detail']  # obhájce A nesmí za B
    code, out = duel(capsys, 'soudce', 'decide', d1)
    assert code == 3 and 'nejde rozhodnout' in out['detail']  # otevřená grill

    b1 = turn(capsys, 'navrh', d1, 'B', 'answer', 'Kód jde přes fronty s opakováním.', '--ref', g1)
    assert b1['onTurn'] == []
    b2 = turn(capsys, 'navrh', d1, 'B', 'claim', 'Slabá hesla jsou hlavní zdroj incidentů.', '--evidence', 'docs/a.md:3|incidenty')['turnId']
    b3 = turn(capsys, 'navrh', d1, 'B', 'claim', 'Uživatel si nemusí nic pamatovat.')['turnId']
    b1 = b1['turnId']

    # Soudce: A slabší (4, 3), B silnější (9, 8 s doložením ×1.5, 8): ℓ = logit(0.35) + Σ znaménko·(s/10)·w.
    score(capsys, d1, a1, 4, 'A')
    score(capsys, d1, g1, 3, 'A')
    score(capsys, d1, b1, 9, 'B')
    score(capsys, d1, b2, 8, 'B', 'soudce', '--evidence-ok')
    last = score(capsys, d1, b3, 8, 'B')
    expected = sigma(P0_LOGIT - 0.4 - 0.3 + 0.9 + 0.8 * 1.5 + 0.8)
    assert last['n'] == 5 and last['p'] == pytest.approx(expected, abs=1e-9) and last['p'] >= 0.75
    assert last['canDecide'] is True and last['onTurn'] == []

    for actor in ('navrh', 'obhajce'):  # strana nehodnotí
        code, out = duel(capsys, actor, 'score', d1, '--turn', a1, '--strength', '9', '--supports', 'B')
        assert code == 2 and out['refused'] is True
    code, out = duel(capsys, 'soudce', 'score', d1, '--turn', a1, '--strength', '1', '--supports', 'A')
    assert code == 3  # druhé skóre téhož soudce na výměnu

    code, shown = duel(capsys, 'soudce', 'show', d1)
    assert code == 0 and shown['p'] == pytest.approx(expected, abs=1e-9) and shown['n'] == 5
    assert shown['canDecide'] is True and shown['trajectory'] == 'insufficient' and len(shown['turns']) == 5

    # Override smí jen člověk: agent dostane 403 (CLI override nemá vůbec).
    first = http.get('/api/brief-vault/fragment', params={**scope, 'id': d1}).json()['latestRevision']
    body = {**scope, 'op': 'duel-decide', 'fragmentId': d1, 'expectedRevision': first,
            'override': {'outcome': 'keep', 'reason': 'Chci to jinak.'}}
    assert http.post('/api/brief-vault', headers={'X-Opora-Actor': 'agent; name=soudce'}, json=body).status_code == 403

    decided = ok(capsys, 'soudce', 'decide', d1)
    assert decided['outcome'] == 'adopt' and decided['p'] == pytest.approx(expected, abs=1e-9)
    assert decided['decision']['text'] == 'Přihlášení e-mailem s jednorázovým kódem.'
    assert decided['lesson']['kind'] == 'pattern'
    assert decided['applied'] is True and decided['appliedRevision'] == 3
    f1_now = http.get('/api/brief-vault/fragment', params={**scope, 'id': f1}).json()
    assert f1_now['fragment']['text'] == 'Přihlášení e-mailem s jednorázovým kódem.' and f1_now['latestRevision'] == 3
    node = next(item for item in http.get('/api/brief-vault', params=scope).json()['roots'] if item['id'] == f1)
    # Uplatnění vypne všechny brány (docs/schranka-duel.md §3.2 restart bran): smyčka jde znovu od scoped.
    assert node['gateStep'] == 0 and node['gatesStale'] is False
    assert not any(value for name, value in node['gates'].items() if name != 'predictionError')
    # Konkurenta smaže člověk (HTTP s dokladem UI), aby hlava fronty níže izolovaně dokazovala návrat f1 od scoped.
    rival_rev = http.get('/api/brief-vault/fragment', params={**scope, 'id': rival}).json()['latestRevision']
    removed = http.post('/api/brief-vault', json={**scope, 'op': 'delete', 'fragmentId': rival, 'expectedRevision': rival_rev,
                                                  'note': 'konkurent splnil účel'})
    assert removed.status_code == 200, removed.text
    head = http.get('/api/brief-vault/next', params=scope).json()
    assert f1_now['gateStep'] == 0 and not any(entry['valid'] for entry in (f1_now.get('gateDetail') or {}).values())
    # Ve frontě je teď jen f1 (konkurent smazán, f2 a f3 vznikají až níž), takže hlava je důkaz, že uplatněný f1 jde znovu od scoped.
    assert head['fragment']['id'] == f1 and head['gate'] == 'scoped'
    f2 = make_fragment(http, scope, 'Export', 'Export jen do CSV.')
    f3 = make_fragment(http, scope, 'Report', 'Report jen měsíčně.')
    code, out = duel(capsys, 'soudce', 'decide', d1)
    assert code == 3  # rozhodnutý duel se nemění

    # Trajektorie: jeden bod na rozhodnutý duel; autor challengeru (strana B) nehodnotí.
    code, out = duel(capsys, 'navrh', 'align', '--score', '6', '--note', 'blíž', '--scope', 's1', '--duel', d1)
    assert code == 1
    one = ok(capsys, 'soudce', 'align', '--score', '5', '--note', 'po duelu 1', '--scope', 's1', '--duel', d1)
    assert one['trajectory']['state'] == 'insufficient' and one['trajectory']['n'] == 1
    code, out = duel(capsys, 'soudce', 'align', '--score', '5', '--note', 'znovu', '--scope', 's1', '--duel', d1)
    assert code == 3  # jeden bod na duel

    # Duel 2: platný směr obstojí → keep, antipattern.
    d2 = open_duel(capsys, f2, 'Export jen do CSV.', 'Export do XLSX.')
    code, nxt = cycle(capsys, 'obhajce', 'next', '--discipline', 'be')
    assert nxt['needs'] == 'duel' and nxt['fragment']['id'] == d2
    c1 = turn(capsys, 'obhajce', d2, 'A', 'claim', 'CSV čte všechno.', '--evidence', 'docs/b.md:1|csv')['turnId']
    c2 = turn(capsys, 'navrh', d2, 'B', 'claim', 'XLSX je pohodlnější.')['turnId']
    c3 = turn(capsys, 'obhajce', d2, 'A', 'claim', 'XLSX přidá závislost.')['turnId']
    score(capsys, d2, c1, 8, 'A', 'soudce', '--evidence-ok')
    score(capsys, d2, c2, 3, 'B')
    final = score(capsys, d2, c3, 7, 'A')
    expected2 = sigma(P0_LOGIT - 0.8 * 1.5 + 0.3 - 0.7)
    assert final['p'] == pytest.approx(expected2, abs=1e-9) and final['p'] <= 0.40
    kept = ok(capsys, 'soudce', 'decide', d2)
    assert kept['outcome'] == 'keep' and kept['lesson']['kind'] == 'antipattern'
    assert kept['decision']['text'] == 'Export jen do CSV.'
    assert kept['applied'] is False and kept['appliedRevision'] is None and kept['appliedReason'].startswith('keep')
    assert http.get('/api/brief-vault/fragment', params={**scope, 'id': f2}).json()['latestRevision'] == 1

    two = ok(capsys, 'soudce', 'align', '--score', '6', '--note', 'po duelu 2', '--scope', 's1', '--duel', d2)
    assert two['trajectory']['n'] == 2 and two['trajectory']['state'] == 'insufficient'

    # Duel 3: střední P → synthesis; bez obhájené syntézy to nejde, s ní ano.
    d3 = open_duel(capsys, f3, 'Report jen měsíčně.', 'Report týdně.')
    e1 = turn(capsys, 'obhajce', d3, 'A', 'claim', 'Měsíční report stačí.')['turnId']
    e2 = turn(capsys, 'navrh', d3, 'B', 'claim', 'Týdně zachytíme výpadky dřív.')['turnId']
    e3 = turn(capsys, 'navrh', d3, 'B', 'claim', 'Týdenní report je automatický.')['turnId']
    score(capsys, d3, e1, 6, 'A')
    score(capsys, d3, e2, 6, 'B')
    mid = score(capsys, d3, e3, 8, 'B')
    assert mid['p'] == pytest.approx(sigma(P0_LOGIT - 0.6 + 0.6 + 0.8), abs=1e-9) and 0.40 < mid['p'] < 0.75
    code, out = duel(capsys, 'soudce', 'decide', d3)
    assert code == 3 and 'obhájena' in out['detail']  # chybí obhájená syntéza
    syn = turn(capsys, 'navrh', d3, 'B', 'synthesis', 'Měsíční report, týdně jen přehled výpadků.')['turnId']
    code, out = duel(capsys, 'soudce', 'decide', d3, '--synthesis-turn', syn)
    assert code == 3  # syntéza ještě není ohodnocená soudcem
    last3 = score(capsys, d3, syn, 7, 'B')
    assert 0.40 < last3['p'] < 0.75
    merged = ok(capsys, 'soudce', 'decide', d3, '--synthesis-turn', syn)
    assert merged['outcome'] == 'synthesis' and merged['lesson']['kind'] == 'pattern'
    assert merged['decision']['text'] == 'Měsíční report, týdně jen přehled výpadků.'
    three = ok(capsys, 'soudce', 'align', '--score', '8', '--note', 'po duelu 3', '--scope', 's1', '--duel', d3)
    assert three['trajectory']['n'] == 3 and three['trajectory']['state'] == 'approaching'
    assert three['trajectory']['p'] > 0.9
    vision_now = http.get('/api/brief-vault/vision', params={**scope, 'scopeNodeId': 's1'}).json()
    assert vision_now['trajectory']['n'] == 3 and len(vision_now['vision']['points']) == 3

    code, lessons = cycle(capsys, 'obhajce', 'lessons', '--discipline', 'be')
    kinds = {item['kind'] for item in lessons['lessons']}
    assert code == 0 and kinds == {'pattern', 'antipattern'}

    # Po obou rozhodnutích se předmětové fragmenty vracejí do fronty bran.
    code, nxt = cycle(capsys, 'obhajce', 'next', '--discipline', 'be')
    assert code == 0 and nxt['needs'] != 'duel' and nxt['fragment']['id'] in (f1, f2, f3)
    assert nxt['gate'] == 'scoped' and not nxt['blockedBy'].get('duel')
