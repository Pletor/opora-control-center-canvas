"""Configured native Desktop readers retain pinned evidence and enforce snapshot scope."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.editor.agent_memory.test_block_access import prepared
from backend.editor.agent_memory.assignment_snapshots import save_assignment
from backend.editor.agent_packet.specification_context import capture_specification


def test_native_configured_brief_results_assignment_and_snapshot_readback(setup):
    client, service, auth = setup
    prepared(client)
    captured = capture_specification(service, 'draft', 'draft', 'focus')
    assignment = save_assignment(service, {**SCOPE, 'nodeId': 'focus', 'contextVersion': captured['contextVersion']})
    payload = {**SCOPE, 'nodeId': 'focus', 'path': '', 'sessionId': 'proof', 'references': [], 'note': 'Complete source'}
    preview = service.desktop_packets.build(payload)
    snapshot = service.desktop_packets.snapshot({**payload, 'digest': preview['digest']})
    for capability, data, path in (
        ('read_node_brief', {'nodeId': 'focus'}, '/api/desktop-v3/node-brief'),
        ('read_agent_results', {'nodeId': 'focus'}, '/api/desktop-v3/agent-results'),
        ('read_assignment_comparison', {'nodeId': 'focus', 'id': assignment['id'], 'source': 'handoff'}, '/api/desktop-v3/assignment-comparison'),
        ('packet_snapshot_read', {'snapshot_id': snapshot['id']}, '/api/desktop-v3/packet/snapshots/' + snapshot['id']),
    ):
        result = call(client, auth, 'desktop_v3_routes.' + capability, data)
        native = client.get(path, params={**SCOPE, **data})
        assert result.status_code == native.status_code == 200, result.text
        assert result.json()['result'] == native.json()
    assert call(client, auth, 'desktop_v3_routes.packet_snapshot_read', {'snapshot_id': 'missing'}).status_code == 409
    assert call(client, auth, 'desktop_v3_routes.read_assignment_comparison', {'nodeId': 'dalsi', 'id': assignment['id'], 'source': 'handoff'}).status_code == 409


def test_external_snapshot_read_uses_actual_git_export_and_rejects_wrong_digest(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.factory import create_app
    from backend.canvas.test_workspace_graph import repository, workspace, GRAPH, ORIGIN
    from backend.brain_opora.determinism import tokens
    from backend.editor.agent_handoff.external_agent_tasks import ExternalAgentTasks
    data_root = tmp_path / 'data'
    app = create_app(data_root)
    service = app.state.service
    project, wid, _ = workspace(service, repository(tmp_path, data_root))
    view = service.view(project, wid)
    service.save_graph(project, wid, GRAPH, view['digest'])
    scope = {'project': project, 'workspace': wid}
    payload = {**scope, 'nodeId': 'card', 'path': '', 'sessionId': '', 'references': [], 'note': 'Export proof'}
    preview = service.desktop_packets.build(payload)
    snapshot = service.desktop_packets.snapshot({**payload, 'digest': preview['digest']})
    export = ExternalAgentTasks(service.desktop_packets).export(snapshot['id'], {**scope, 'nodeId': 'card', 'digest': snapshot['digest']})
    _, token = tokens.issue_heart(service, project, wid)
    with TestClient(app, base_url=ORIGIN) as client:
        auth = {'origin': ORIGIN, tokens.HEADER: token}
        inputs = {'snapshot_id': snapshot['id'], 'nodeId': 'card', 'digest': snapshot['digest']}
        actual = call(client, auth, 'desktop_v3_routes.external_read', inputs, scope=scope)
        assert actual.status_code == 200 and actual.json()['result'] == export, actual.text
        assert call(client, auth, 'desktop_v3_routes.external_read', {**inputs, 'digest': 'wrong'}, scope=scope).status_code == 409
