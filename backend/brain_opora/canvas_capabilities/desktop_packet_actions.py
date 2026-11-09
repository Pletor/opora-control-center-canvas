"""Native packet and assignment snapshots/export retain CAS, scope and immutable readback."""
import hashlib
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.editor.agent_memory.assignment_snapshots import save_assignment
from backend.editor.agent_handoff.external_agent_tasks import ExternalAgentTasks
from backend.canvas.payload_errors import NextStep

PREFIX = 'desktop_v3_routes.'
REQUEST = ('nodeId', 'path', 'sessionId', 'references', 'note')
CONTRACTS = {
    PREFIX + 'packet_preview': contract(REQUEST, ('blockId',), types={'references': 'json'}),
    PREFIX + 'packet_snapshot': contract((*REQUEST, 'digest'), effect='snapshot', replay=True, cas='native preview digest'),
    PREFIX + 'write_assignment_snapshot': contract(('nodeId', 'contextVersion'), effect='snapshot', replay=True,
        cas='native captured assignment contextVersion'),
    PREFIX + 'external_export': contract(('snapshot_id', 'nodeId', 'digest'), effect='draft-file', replay=True,
        cas='native immutable snapshot digest; existing file content'),
}
for _contract in CONTRACTS.values():
    _contract['test'] = 'backend/api/brain_opora/test_canvas_capability_packets.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    payload = {'project': project, 'workspace': workspace, **{key: value for key, value in data.items() if key != 'snapshot_id'}}
    packets = service.desktop_packets
    if capability.endswith('packet_preview'):
        return {'state': 'read', 'result': packets.build(payload)}
    external = ExternalAgentTasks(packets)

    def snapshot():
        if capability.endswith('external_export'):
            external._snapshot(data['snapshot_id'], payload)
            _, path = external._target(payload)
            return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
        table = 'assignment_snapshots' if capability.endswith('write_assignment_snapshot') else 'desktop_v3_snapshots'
        rows = service.db_for(project).execute(f'SELECT id FROM {table} WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY id',
                                              (project, workspace, data['nodeId']))
        return [row[0] for row in rows]

    def action():
        if capability.endswith('packet_snapshot'):
            return packets.snapshot(payload)
        if capability.endswith('write_assignment_snapshot'):
            return save_assignment(service, payload)
        return external.export(data['snapshot_id'], payload)

    def verify(before, after, result):
        if capability.endswith('external_export'):
            actual = external.read(data['snapshot_id'], payload)
        elif capability.endswith('packet_snapshot'):
            stored = packets.load(result['id'], project, workspace)
            actual = {key: stored[key] for key in ('id', 'digest', 'packet', 'createdAt')}
        else:
            import json
            row = service.db_for(project).execute('SELECT record FROM assignment_snapshots WHERE id=? AND project_id=? AND workspace_id=? AND node_id=?',
                (result['id'], project, workspace, data['nodeId'])).fetchone()
            actual = json.loads(row[0]) if row else None
        if actual != result:
            raise NextStep('Native snapshot/export readback failed.', code='operation_incomplete', hint='Inspect existing native snapshot; do not duplicate it.')

    return run(service, project, workspace, session, capability, data, request_id, snapshot=snapshot, action=action, verify=verify)
