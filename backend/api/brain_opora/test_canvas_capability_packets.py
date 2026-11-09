"""Packet/assignment writes are native immutable snapshots, with digest CAS and replay."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.editor.agent_memory.test_block_access import prepared
from backend.editor.agent_packet.specification_context import capture_specification


def test_packet_preview_snapshot_and_assignment_preserve_native_pins(setup):
    client, service, auth = setup
    prepared(client)
    data = {'nodeId': 'focus', 'path': '', 'sessionId': '', 'references': [], 'note': 'Original request'}
    preview = call(client, auth, 'desktop_v3_routes.packet_preview', data)
    assert preview.status_code == 200 and preview.json()['result'] == service.desktop_packets.build({**SCOPE, **data})
    request = {**data, 'digest': preview.json()['result']['digest']}
    snapshot = call(client, auth, 'desktop_v3_routes.packet_snapshot', request, 'snapshot')
    assert snapshot.status_code == 200 and snapshot.json()['verified'], snapshot.text
    assert call(client, auth, 'desktop_v3_routes.packet_snapshot', request, 'snapshot').json() == snapshot.json()
    stored = call(client, auth, 'desktop_v3_routes.packet_snapshot_read', {'snapshot_id': snapshot.json()['result']['id']})
    assert stored.json()['result'] == snapshot.json()['result']
    assert call(client, auth, 'desktop_v3_routes.packet_snapshot', {**request, 'digest': 'stale'}, 'stale').status_code == 409
    assert call(client, auth, 'desktop_v3_routes.packet_snapshot', {**request, 'note': 'Changed'}, 'snapshot').status_code == 409
    capture = capture_specification(service, 'draft', 'draft', 'focus')
    data = {'nodeId': 'focus', 'contextVersion': capture['contextVersion']}
    assignment = call(client, auth, 'desktop_v3_routes.write_assignment_snapshot', data, 'assignment')
    assert assignment.status_code == 200 and assignment.json()['verified'], assignment.text
    assert call(client, auth, 'desktop_v3_routes.write_assignment_snapshot', data, 'assignment').json() == assignment.json()
    assert assignment.json()['result']['specification'] == capture['specification']
    assert call(client, auth, 'desktop_v3_routes.write_assignment_snapshot', {**data, 'contextVersion': 'stale'}, 'stale-assignment').status_code == 409


def test_external_export_immutable_file_and_readback_in_real_git_workspace(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.factory import create_app
    from backend.canvas.test_workspace_graph import repository, workspace, GRAPH, ORIGIN
    from backend.brain_opora.determinism import tokens
    data_root = tmp_path / 'data'
    app = create_app(data_root)
    service = app.state.service
    project, wid, _ = workspace(service, repository(tmp_path, data_root))
    service.save_graph(project, wid, GRAPH, service.view(project, wid)['digest'])
    scope = {'project': project, 'workspace': wid}
    payload = {**scope, 'nodeId': 'card', 'path': '', 'sessionId': '', 'references': [], 'note': 'Export proof'}
    preview = service.desktop_packets.build(payload)
    snapshot = service.desktop_packets.snapshot({**payload, 'digest': preview['digest']})
    _, token = tokens.issue_heart(service, project, wid)
    with TestClient(app, base_url=ORIGIN) as client:
        auth = {'origin': ORIGIN, tokens.HEADER: token}
        inputs = {'snapshot_id': snapshot['id'], 'nodeId': 'card', 'digest': snapshot['digest']}
        saved = call(client, auth, 'desktop_v3_routes.external_export', inputs, 'export', scope)
        assert saved.status_code == 200 and saved.json()['verified'], saved.text
        assert call(client, auth, 'desktop_v3_routes.external_export', inputs, 'export', scope).json() == saved.json()
        read = call(client, auth, 'desktop_v3_routes.external_read', inputs, scope=scope)
        assert read.json()['result'] == saved.json()['result']
        target = service.folder(project).external_task(wid, 'card')
        target.write_text('Existing worker Result must survive', encoding='utf-8')
        refused = call(client, auth, 'desktop_v3_routes.external_export', inputs, 'new-export', scope)
        assert refused.status_code == 409
        assert target.read_text(encoding='utf-8') == 'Existing worker Result must survive'
