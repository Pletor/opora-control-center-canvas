"""Snapshot CAS covers node content as well as graph structure; replay keeps immutable IDs."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import proposal, accept
from backend.editor.canvas_versions.canvas_versions import CanvasVersions


def test_native_full_snapshot_replay_content_cas_and_verified_actor(setup):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    versions = CanvasVersions(service)
    view = service.view('draft', 'draft')
    token = versions.head('draft', 'draft')['currentToken']
    data = {'digest': view['digest'], 'expectedToken': token}
    first = call(client, auth, 'canvas_version_routes.save_canvas_version', data, 'version')
    assert first.status_code == 200, first.text
    result = first.json()
    assert result['result']['version']['actor'] == 'agent'
    stored = versions.read('draft', 'draft', result['result']['version']['id'])
    assert stored['graph'] == view['graph'] and stored['snapshot']['records']
    assert stored['integrity'] == 'verified'
    assert call(client, auth, 'canvas_version_routes.save_canvas_version', data, 'version').json() == result
    assert call(client, auth, 'canvas_version_routes.save_canvas_version', {**data, 'expectedToken': 'wrong'}, 'version').status_code == 409
    assert call(client, auth, 'canvas_version_routes.save_canvas_version', {**data, 'author': 'human'}, 'forged').status_code == 422
    node = item['refs']['new']
    journal = call(client, auth, 'node_routes.save_node_journal', {'node': node, 'day': '2026-11-09', 'expected_revision': 0, 'text': 'New evidence'}, 'journal')
    assert journal.status_code == 200, journal.text
    stale = call(client, auth, 'canvas_version_routes.save_canvas_version', data, 'stale')
    assert stale.status_code in (409, 422), stale.text
    assert versions.read('draft', 'draft', result['result']['version']['id']) == stored
    assert native.context('draft', 'draft')['acceptedHead'] == result['acceptedHead']


def test_restore_preparation_pins_full_version_without_writing(setup):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    versions = CanvasVersions(service)
    view = service.view('draft', 'draft')
    saved = versions.save({'project': 'draft', 'workspace': 'draft', 'digest': view['digest'], 'author': 'Human'})
    version_id = saved['version']['id']
    before = versions.list('draft', 'draft')
    accepted = native.context('draft', 'draft')['acceptedHead']
    data = {'versionId': version_id, 'digest': view['digest'], 'expectedToken': before['currentToken']}
    prepared = call(client, auth, 'canvas_version_routes.restore_canvas_version', data)
    assert prepared.status_code == 200, prepared.text
    result = prepared.json()
    assert result['state'] == 'awaiting_human' and result['applied'] is False
    assert result['result']['version']['id'] == version_id
    assert result['result']['graph'] == view['graph']
    assert 'canvasVersion=' + version_id in result['url']
    assert versions.list('draft', 'draft') == before
    assert native.context('draft', 'draft')['acceptedHead'] == accepted
    bad = call(client, auth, 'canvas_version_routes.restore_canvas_version', {**data, 'expectedToken': 'stale'})
    assert bad.status_code in (409, 422), bad.text
    wrong = call(client, auth, 'canvas_version_routes.restore_canvas_version', {**data, 'versionId': 'f' * 32})
    assert wrong.status_code == 409, wrong.text
    assert versions.list('draft', 'draft') == before
