"""Reviewed research decisions use their existing task proposal and reverse-link services."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.editor.research import decisions, decision_tasks, service as research
from backend.canvas.payload_errors import NextStep

CONTRACTS = {
    'research_decision_routes.tasks': contract(('id', 'tasks'), effect='proposal', replay=True,
        cas='immutable review and native task materialization receipt'),
    'research_decision_routes.reconcile': contract(('id',), effect='research', replay=True,
        cas='actual native accepted proposal and current research revisions'),
}
for _contract in CONTRACTS.values():
    _contract['test'] = 'backend/api/brain_opora/test_canvas_capability_research_tasks.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    review = decisions.read(service, project, workspace, data['id'])
    cards = list(dict.fromkeys(item['id'] for item in [review['problem'], review['decision'], *review['evidence']]))

    def snapshot():
        row = service.db_for(project).execute('SELECT payload FROM research_materializations '
            'WHERE project_id=? AND workspace_id=? AND review_id=?', (project, workspace, data['id'])).fetchone()
        return {'receipt': row[0] if row else None,
                'cards': [research.detail(service, project, workspace, cid)['card'] for cid in cards]}

    def verify(before, after, result):
        if decision_tasks.status(service, project, workspace, data['id']) != result:
            raise NextStep('Native task receipt differs from readback.', code='operation_incomplete', hint='Inspect existing task proposal.')
        if capability.endswith('.reconcile'):
            if not result['accepted'] or any(not set(result['nodeIds'].values()).issubset(card['refs']['nodeIds']) for card in after['cards']):
                raise NextStep('Native research reverse links are incomplete.', code='operation_incomplete', hint='Inspect accepted proposal and research refs.')

    return run(service, project, workspace, session, capability, data, request_id, snapshot=snapshot,
        action=lambda: decision_tasks.materialize(service, project, workspace, data['id'], data['tasks'],
            {'kind': 'agent', 'name': session['worker_name']}) if capability.endswith('.tasks')
            else decision_tasks.reconcile(service, project, workspace, data['id']), verify=verify)
