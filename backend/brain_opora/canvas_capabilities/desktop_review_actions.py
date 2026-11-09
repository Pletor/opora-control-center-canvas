"""Human-only Desktop operations prepare exact native review, never approval."""
from urllib.parse import urlencode

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.canvas.payload_errors import NextStep
from backend.editor.agent_memory.desktop_review import FIELDS, prepare, read

CONTRACTS = {'desktop_v3_routes.' + operation: contract(tuple(sorted(fields)), effect='proposal', replay=True,
    cas='Immutable preparation pins exact graph/state revision and native target preimages',
    output='awaiting_human with persisted preparation and scoped review URL; no native action applied')
    for operation, fields in FIELDS.items()}
CONTRACTS['desktop_review_routes.review'] = contract(('identifier',), output='Exact immutable Desktop preparation and current native freshness')
CONTRACTS['desktop_review_routes.decide'] = contract(('identifier', 'digest'), effect='human-decision',
    output='Existing exact preparation URL; human action remains unapplied')
for item in CONTRACTS.values():
    item['test'] = 'backend/api/brain_opora/test_canvas_capability_desktop_reviews.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    if capability.startswith('desktop_review_routes.'):
        result = read(service, project, workspace, data['identifier'])
        if capability.endswith('.review'):
            return {'state': 'read', 'result': result}
        if result['review']['digest'] != data['digest'] or result['state'] != 'ready':
            raise NextStep('Review is stale or does not match.', code='review_conflict', hint='Inspect current native state.')
        return {'state': 'awaiting_human', 'applied': False, 'result': result,
                'url': '/?' + urlencode({'project': project, 'workspace': workspace, 'screen': 'canvas',
                                        'environment': 'project', 'desktopReview': data['identifier']})}
    return prepare(service, project, workspace, capability.split('.')[1], data, request_id,
                   {'kind': 'agent', 'name': session['worker_name']})
