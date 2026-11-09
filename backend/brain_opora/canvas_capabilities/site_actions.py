"""Site edits prepare the existing human-review proposal, never write the live document."""
from urllib.parse import urlencode
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.api.project.site_admin_routes import _errors
from backend.project.site_admin import proposals, store
from backend.project.site_admin.design_system import normalize
from backend.project.site_admin.tokens import SiteAdminInvalid
from backend.project.site_admin.store import SiteAdminConflict
from backend.canvas.payload_errors import NextStep

PREFIX = 'site_admin_routes.'
CONTRACTS = {
    PREFIX + 'site_admin_save': contract(('expectedRevision', 'document'), ('note',), effect='proposal', replay=True,
        cas='native site document revision', output='Existing native pending SiteAdmin proposal; human review required'),
    PREFIX + 'proposal_create': contract(('expectedRevision', 'changes'), ('note', 'attachments'), effect='proposal', replay=True,
        cas='native site document revision'),
    PREFIX + 'proposal_accept': contract(('proposal_id',), effect='human-decision', output='Existing pending native proposal and actual UI review URL'),
    PREFIX + 'proposal_reject': contract(('proposal_id',), effect='human-decision', output='Existing pending native proposal and actual UI review URL'),
}
ATTACHMENTS = {
    PREFIX+'asset_upload': ('asset', 'put'), PREFIX+'asset_delete': ('asset', 'delete'),
    PREFIX+'font_upload': ('font', 'put'), PREFIX+'font_delete': ('font', 'delete'),
}
for operation, (kind, action) in ATTACHMENTS.items():
    required = ('expectedRevision', 'name') + (('group',) if kind == 'asset' else ()) + (('data',) if action == 'put' else ())
    CONTRACTS[operation] = contract(required, ('note',), effect='proposal', replay=True,
        cas='native site revision and immutable attachment baseDigest at human acceptance',
        output='Native staged attachment proposal and usable human review URL; live files unchanged')
for _contract in CONTRACTS.values():
    _contract['test'] = 'backend/api/brain_opora/test_canvas_capability_site.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    url = '/?' + urlencode({'project': project, 'workspace': workspace, 'screen': 'canvas',
                            'environment': 'project', 'projectView': 'site'})
    if capability in (PREFIX + 'proposal_accept', PREFIX + 'proposal_reject'):
        proposal = _errors(lambda: proposals._pending_one(service, project, data['proposal_id']))
        return {'state': 'awaiting_human', 'applied': False, 'proposal': proposal, 'url': url,
                'requestedDecision': 'accept' if capability.endswith('accept') else 'reject'}

    def snapshot():
        return {'document': store.read(service, project), 'pending': proposals.pending(service, project)}

    def action():
        current = store.read(service, project)
        if type(data['expectedRevision']) is not int or data['expectedRevision'] < 0:
            raise SiteAdminInvalid('expectedRevision must be a nonnegative integer.')
        if data['expectedRevision'] != current['revision']:
            raise SiteAdminConflict('Site document changed; read the current revision.')
        if capability in ATTACHMENTS:
            kind, op = ATTACHMENTS[capability]
            attachment = {'kind': kind, 'op': op, **{key: data[key] for key in ('name', 'group', 'data') if key in data}}
            return proposals.propose(service, project, {}, data.get('note'), session['worker_name'], attachments=[attachment])
        if capability.endswith('site_admin_save'):
            document, _ = normalize(data['document'], current)
            changes = {key: document[key] for key in proposals.PARTS}
        else:
            changes = data['changes']
        return proposals.propose(service, project, changes, data.get('note'), session['worker_name'],
                                 attachments=data.get('attachments'))

    def verify(before, after, result):
        if before['document'] != after['document'] or proposals._pending_one(service, project, result['id']) != result:
            raise NextStep('Native site proposal readback failed.', code='operation_incomplete', hint='Inspect the pending proposal.')

    receipt = _errors(lambda: run(service, project, workspace, session, capability, data, request_id,
                                  snapshot=snapshot, action=action, verify=verify))
    return {**receipt, 'state': 'awaiting_human', 'applied': False, 'url': url}
