"""Human-reviewed evidence produces pending native tasks; acceptance alone unlocks reverse links."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.canvas_plan import apply_plan
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import accept
from backend.editor.research.test_decision_tasks import setup as seed_review, TASKS
from backend.editor.research import decisions, service as research


def test_materialization_and_reconcile_use_native_acceptance_and_replay(setup):
    client, service, auth = setup
    apply_plan(service, {**SCOPE, 'digest': service.view('draft', 'draft')['digest'],
        'plan': {'nodes': [{'ref': 'seed', 'kind': 'node', 'name': 'Seed'}]}})
    review = decisions.review(service, 'draft', 'draft', seed_review(service), 'human')
    before = service.view('draft', 'draft')['graph']
    payload = {'id': review['id'], 'tasks': TASKS}
    proposed = call(client, auth, 'research_decision_routes.tasks', payload, 'task-proposal')
    assert proposed.status_code == 200, proposed.text
    result = proposed.json()['result']
    assert proposed.json()['verified'] and not result['accepted']
    assert service.view('draft', 'draft')['graph'] == before
    assert call(client, auth, 'research_decision_routes.tasks', payload, 'task-proposal').json() == proposed.json()
    changed = {**payload, 'tasks': [{**TASKS[0], 'goal': 'Changed'}]}
    assert call(client, auth, 'research_decision_routes.tasks', changed, 'task-proposal').status_code == 409
    early = call(client, auth, 'research_decision_routes.reconcile', {'id': review['id']}, 'sync')
    assert early.status_code == 409
    native = OporaGraphProposals(service)
    accepted = accept(native, native.read('draft', 'draft', result['proposalId']))  # Isolated explicit human fixture.
    synced = call(client, auth, 'research_decision_routes.reconcile', {'id': review['id']}, 'sync')
    assert synced.status_code == 200 and synced.json()['verified'], synced.text
    assert synced.json()['acceptedHead'] == accepted['id']
    assert synced.json()['result']['acceptedRevision'] == accepted['id']
    for cid in ('rc_problem', 'rc_decision', 'rc_fact'):
        assert research.detail(service, 'draft', 'draft', cid)['card']['refs']['nodeIds'] == list(result['nodeIds'].values())
    assert call(client, auth, 'research_decision_routes.reconcile', {'id': review['id']}, 'sync').json() == synced.json()
    assert call(client, auth, 'research_decision_routes.tasks', payload, 'task-proposal').json() == proposed.json()
    assert decisions.read(service, 'draft', 'draft', review['id']) == review
