"""Real native material bytes, scoped ownership, replay and deletion CAS."""
import base64
import hashlib
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import proposal, accept


def test_native_material_upload_read_remove_and_replay(setup):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    node = item['refs']['new']
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><text>full evidence</text></svg>'
    upload = {'nodeId': node, 'dataUrl': 'data:image/svg+xml;base64,'+base64.b64encode(raw).decode()}
    first = call(client, auth, 'node_routes.upload_material', upload, 'upload')
    assert first.status_code == 200, first.text
    result = first.json()
    assert result['verified'] and result['acceptedHead']
    assert call(client, auth, 'node_routes.upload_material', upload, 'upload').json() == result
    assert call(client, auth, 'node_routes.upload_material', {**upload, 'dataUrl': 'invalid'}, 'upload').status_code == 409
    data = {'nodeId': node, 'file': result['result']['file']}
    read = call(client, auth, 'node_routes.material_file', data)
    assert read.status_code == 200, read.text
    content = read.json()['result']
    assert base64.b64decode(content['data']) == raw
    assert content['sha256'] == hashlib.sha256(raw).hexdigest()
    assert client.get('/api/node-materials/file', params={'project': 'draft', **data}).content == raw
    bad = call(client, auth, 'node_routes.remove_material', {**data, 'expectedSha256': 'stale'}, 'bad')
    assert bad.status_code == 409
    assert call(client, auth, 'node_routes.material_file', data).status_code == 200
    remove = {**data, 'expectedSha256': content['sha256']}
    deleted = call(client, auth, 'node_routes.remove_material', remove, 'remove')
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()['result']['removed']
    assert call(client, auth, 'node_routes.remove_material', remove, 'remove').json() == deleted.json()
    assert call(client, auth, 'node_routes.material_file', data).status_code == 404
    assert native.context('draft', 'draft')['acceptedHead'] == result['acceptedHead']
    assert call(client, auth, 'node_routes.material_file', {**data, 'file': '../secret'}).status_code == 404
    assert call(client, auth, 'node_routes.upload_material', {**upload, 'nodeId': 'foreign'}, 'foreign').status_code == 404
    assert call(client, auth, 'node_routes.material_file', data, scope={'project': 'foreign', 'workspace': 'draft'}).status_code == 403


def test_real_heart_cli_upload_over_two_megabytes_uses_native_http(setup, monkeypatch, tmp_path, capsys):
    import json
    from backend.brain_opora.heart import opora_heart
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    raw = b'x' * 2_100_000
    data = {'nodeId': item['refs']['new'], 'dataUrl': 'data:image/png;base64,'+base64.b64encode(raw).decode()}
    path = tmp_path / 'material.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    assert path.stat().st_size > 2_000_000
    calls = []
    def http(method, path, body=None, query=None, **kwargs):
        calls.append(path)
        response = client.request(method, path, json=body, params=query, headers=auth)
        if response.status_code >= 400:
            raise opora_heart.Failure({'error': response.text})
        return response.json()
    monkeypatch.setattr(opora_heart, 'call', http)
    monkeypatch.setenv('OPORA_PROJECT', 'draft')
    monkeypatch.setenv('OPORA_WORKSPACE', 'draft')
    argv = ['canvas', 'invoke', 'node_routes.upload_material', '--file', str(path), '--request-id', 'large-cli']
    assert opora_heart.main(argv) == 0
    saved = json.loads(capsys.readouterr().out)
    file = saved['result']['file']
    result = call(client, auth, 'node_routes.material_file', {'nodeId': data['nodeId'], 'file': file}).json()['result']
    assert base64.b64decode(result['data']) == raw
    assert opora_heart.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == saved
    assert len(calls) == 2
    # The larger bound is finite: ordinary graph/read input retains its original cap.
    assert opora_heart.main(['canvas', 'invoke', 'canvas_routes.view', '--file', str(path)]) == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'canvas_input'
    assert len(calls) == 2


def test_same_length_native_file_corruption_never_claims_verified(setup, monkeypatch):
    from backend.editor.node.node_materials import NodeMaterials
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    original = NodeMaterials.save_upload
    def corrupt(self, payload):
        result = original(self, payload)
        path, _ = self.file_path(payload['project'], payload['nodeId'], result['file'])
        path.write_bytes(b'Y' * result['bytes'])
        return result
    monkeypatch.setattr(NodeMaterials, 'save_upload', corrupt)
    data = {'nodeId': item['refs']['new'], 'dataUrl': 'data:image/png;base64,' + base64.b64encode(b'XXXX').decode()}
    first = call(client, auth, 'node_routes.upload_material', data, 'corrupted')
    assert first.status_code == 409 and first.json()['code'] == 'operation_incomplete'
    monkeypatch.setattr(NodeMaterials, 'save_upload', original)
    retry = call(client, auth, 'node_routes.upload_material', data, 'corrupted')
    assert retry.status_code == 409 and retry.json()['code'] == 'operation_incomplete'
