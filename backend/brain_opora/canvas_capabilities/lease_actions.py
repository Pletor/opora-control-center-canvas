"""Native expiring leases with stable claim replay and verified ownership."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.canvas.payload_errors import InvalidPayload, NextStep
from backend.editor.agent_memory.card_leases import CardLeases

CONTRACTS = {'desktop_v3_routes.write_lease': contract(('nodeId', 'op'), ('token', 'ttlSeconds', 'touched'),
    effect='draft', replay=True, cas='Native lease token for heartbeat/release; conditional claim',
    output='Native lease receipt; replay does not renew expiry, use read_leases for current status')}
CONTRACTS['desktop_v3_routes.write_lease']['test'] = 'backend/api/brain_opora/test_canvas_capability_leases.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    if not isinstance(data['nodeId'], str):
        raise InvalidPayload('nodeId must be a string.', field='nodeId')
    native = CardLeases(service)
    def snapshot():
        db = service.db_for(project)
        return {table: [dict(row) for row in db.execute(
            f'SELECT * FROM {table} WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY rowid',
            (project, workspace, data['nodeId'])).fetchall()]
            for table in ('card_leases', 'assignment_snapshots', 'card_work_activity')}
    def action():
        payload = {'project': project, 'workspace': workspace, **data}
        if data['op'] == 'claim':
            payload['owner'] = session['worker_name']
        return native.apply(payload, actor='agent')
    def verify(before, after, result):
        rows = after['card_leases']
        valid = not rows if data['op'] == 'release' else len(rows) == 1 and rows[0]['expires_at'] == result['expiresAt']
        if data['op'] == 'claim':
            valid = valid and rows[0]['owner'] == session['worker_name'] and rows[0]['token'] == result['token']
            valid = valid and any(row['id'] == result['assignment']['id'] for row in after['assignment_snapshots'])
        if not valid:
            raise NextStep('Lease readback failed.', code='operation_incomplete', hint='Inspect native lease before retry.')
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=action, verify=verify)
