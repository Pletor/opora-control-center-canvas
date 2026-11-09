"""Legacy main Heart planning is project-owned; private capability scope never delegates."""
import pytest
from backend.api.brain_opora.test_heart_workspace import heart, tool, ARCHITECTURE
from backend.brain_opora.determinism import tokens, brain_files
from backend.brain_opora.determinism.token_read_scope import enforce
from backend.brain_opora.determinism.gate_payloads import GateError


def test_new_owned_workspace_before_active_has_only_bounded_planning_delegation(heart):
    client, _, project, brain = heart
    web = tool('plan', plan=ARCHITECTURE)['refs']['web']
    workspace = tool('workspace', '--domain', web, '--reuse')['workspace']
    assert brain_files.active_workspace(brain) is None
    service = client.app.state.service
    _, token = tokens.issue_heart(service, project, 'main')
    scope = {'project': project, 'workspace': workspace}
    assert enforce(service, 'GET', '/api/oporahub/graph-proposals/context', token, scope)
    assert enforce(service, 'POST', '/api/canvas-plan', token, {}, scope)
    for path, query in (
        ('/api/brain/canvas/capabilities', scope), ('/api/research', scope),
        ('/api/view', {**scope, 'workspace': 'unknown'}), ('/api/view', {**scope, 'project': 'foreign'}),
    ):
        with pytest.raises(GateError) as failure:
            enforce(service, 'GET', path, token, query)
        assert failure.value.status == 403
    worker = tokens.issue_worker(service, project, 'main', {'name': 'worker'})['token']
    with pytest.raises(GateError):
        enforce(service, 'GET', '/api/view', worker, scope)
    _, foreign = tokens.issue_heart(service, 'draft', 'main')
    with pytest.raises(GateError):
        enforce(service, 'GET', '/api/view', foreign, {'project': 'draft', 'workspace': workspace})
