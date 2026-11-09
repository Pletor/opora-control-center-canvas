"""Native full workspace snapshots with authenticated authorship and content CAS."""
from urllib.parse import urlencode

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.canvas.payload_errors import NextStep
from backend.editor.canvas_versions.canvas_versions import CanvasVersions

CONTRACTS = {'canvas_version_routes.save_canvas_version': contract(('digest', 'expectedToken'),
    effect='snapshot', replay=True, cas='native graph digest plus full workspace content token',
    output='Native immutable full-content version; author is verified Heart identity')}
CONTRACTS['canvas_version_routes.save_canvas_version']['test'] = 'backend/api/brain_opora/test_canvas_capability_versions.py'

CONTRACTS['canvas_version_routes.restore_canvas_version'] = contract(
    ('versionId', 'digest', 'expectedToken'), effect='human-decision',
    cas='Native full-content restore preflight; human repeats current CAS before restoration',
    output='Verified immutable version and selected history review URL; no restore or acceptance')
CONTRACTS['canvas_version_routes.restore_canvas_version']['test'] = 'backend/api/brain_opora/test_canvas_capability_versions.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    versions = CanvasVersions(service)
    if capability == 'canvas_version_routes.restore_canvas_version':
        preview = versions.preview_restore({'project': project, 'workspace': workspace, **data,
                                            'author': session['worker_name']})
        return {'state': 'awaiting_human', 'applied': False, 'result': preview,
                'url': '/?' + urlencode({'project': project, 'workspace': workspace,
                                        'canvasVersion': data['versionId']})}
    def snapshot():
        return versions.list(project, workspace)
    def action():
        return versions.save({'project': project, 'workspace': workspace, **data,
                              'author': session['worker_name']}, actor='agent')
    def verify(before, after, result):
        stored = versions.read(project, workspace, result['version']['id'])
        if stored['version'] != result['version'] or stored['integrity'] != 'verified' or after['currentToken'] != result['currentToken']:
            raise NextStep('Native version readback failed.', code='operation_incomplete', hint='Inspect existing immutable version.')
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=action, verify=verify)
