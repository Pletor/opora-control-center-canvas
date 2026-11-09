"""Native Flow drafts retain immutable versions, scope and persistent operation identity."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.api.flow.test_flow_routes import GRAPH
from backend.brain_opora.determinism import tokens
from backend.flow import workflows


def test_workflow_and_version_draft_native_replay_and_foreign_ownership(setup):
    client, service, auth = setup
    project = service.project_hub.empty_project({'name': 'Own', 'confirmed': True})['id']
    foreign = service.project_hub.empty_project({'name': 'Foreign', 'confirmed': True})['id']
    _, token = tokens.issue_heart(service, project, 'draft')
    auth = {**auth, tokens.HEADER: token}
    scope = {'project': project, 'workspace': 'draft'}
    data = {'kind': 'heart', 'name': 'Reviewable process'}
    response = call(client, auth, 'flow_routes.workflow_create', data, 'workflow', scope)
    assert response.status_code == 200 and response.json()['verified'], response.text
    workflow = response.json()['result']
    assert workflow['project_id'] == project
    assert call(client, auth, 'flow_routes.workflow_create', data, 'workflow', scope).json() == response.json()
    assert call(client, auth, 'flow_routes.workflow_create', {**data, 'name': 'Other'}, 'workflow', scope).status_code == 409
    payload = {'workflow_id': workflow['id'], 'graph': GRAPH, 'note': 'First draft'}
    first = call(client, auth, 'flow_routes.version_draft', payload, 'draft', scope)
    assert first.status_code == 200 and first.json()['verified'], first.text
    version = first.json()['result']
    assert version['graph'] == GRAPH and version['status'] == 'draft'
    assert workflows.get_version(service.db, version['id']) == version
    assert call(client, auth, 'flow_routes.version_draft', payload, 'draft', scope).json() == first.json()
    assert len(workflows.list_versions(service.db, workflow['id'])) == 1
    with service.registry_lock:
        other = workflows.create_workflow(service.db, 'heart', 'Foreign hidden', foreign)
        other_version = workflows.create_draft(service.db, other['id'], GRAPH)
    for changed in ({**payload, 'workflow_id': other['id']}, {**payload, 'parent_version_id': other_version['id']},
                    {**payload, 'learnedFrom': {'project': foreign, 'result': 'verified'}}):
        assert call(client, auth, 'flow_routes.version_draft', changed, 'foreign', scope).status_code == 403
    invalid = call(client, auth, 'flow_routes.version_draft', {**payload, 'graph': {'nodes': [{'bad': True}]}}, 'invalid', scope)
    assert invalid.status_code == 422
    assert len(workflows.list_versions(service.db, workflow['id'])) == 1
    assert not any(row['active_version_id'] for row in workflows.list_workflows(service.db, project))
