"""Actual Heart CLI crosses HTTP with a valid multi-file native bundle."""
import base64
import json

from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE, BASE
from backend.brain_opora.heart import opora_heart
from backend.project.site_admin import proposals, store


def test_large_multifile_bundle_real_cli_and_other_capability_transport_bound(setup, monkeypatch, tmp_path, capsys):
    client, service, auth = setup
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><!--' + b'x' * 1_500_000 + b'--></svg>'
    assert len(raw) < store.SVG_LIMIT < store.ASSET_LIMIT
    data = {'expectedRevision': store.read(service, 'draft')['revision'], 'changes': {'title': 'Large bundle'},
        'attachments': [{'kind': 'asset', 'op': 'put', 'group': 'Logos', 'name': name,
                         'data': base64.b64encode(raw).decode()} for name in (f'part-{index}.svg' for index in range(8))]}
    path = tmp_path / 'bundle.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    assert path.stat().st_size > 14_500_000
    def http(method, path, body=None, query=None, **kwargs):
        response = client.request(method, path, json=body, params=query, headers=auth)
        if response.status_code >= 400:
            raise opora_heart.Failure({'error': response.text})
        return response.json()
    monkeypatch.setattr(opora_heart, 'call', http)
    monkeypatch.setenv('OPORA_PROJECT', 'draft')
    monkeypatch.setenv('OPORA_WORKSPACE', 'draft')
    args = ['canvas', 'invoke', 'site_admin_routes.proposal_create', '--file', str(path), '--request-id', 'large-bundle']
    assert opora_heart.main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert opora_heart.main(args) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert len(first['result']['attachments']) == 8 and len(proposals.pending(service, 'draft')) == 1
    for index in (0, 7):
        read = call(client, auth, 'site_admin_routes.proposal_attachment', {'proposal_id': first['result']['id'], 'index': index})
        assert base64.b64decode(read.json()['result']['data']) == raw
    assert opora_heart.main(['canvas', 'invoke', 'canvas_routes.view', '--file', str(path)]) == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'canvas_input'
    # Real wire bytes, including whitespace, retain the old limit for unrelated operations.
    wire = json.dumps({**SCOPE, 'capability': 'canvas_routes.view', 'input': {}}).encode() + b' ' * 14_500_000
    denied = client.post(BASE + '/invoke', content=wire, headers={**auth, 'content-type': 'application/json'})
    assert denied.status_code == 413 and denied.json()['code'] == 'body_too_large'
