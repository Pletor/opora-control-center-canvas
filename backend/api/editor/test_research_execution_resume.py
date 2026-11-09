"""Synthetic M4 acceptance proof; never reads or accepts the real Ample project."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_execution_start_deliver import ready, commit_card
from backend.app.test_local_merge_autonomy import head, ok
from backend.api.brain_opora.test_gate_routes import open_session, worker
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN


def test_research_task_new_authenticated_session_resumes_exact_work(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path / 'data'), base_url=ORIGIN) as client:
        repo, scope, node = ready(client, tmp_path)
        view = ok(client.get('/api/view', params=scope))
        sector = next(item['parentId'] for item in view['graph']['nodes'] if item['id'] == node)
        root = ok(client.post('/api/brief-vault', headers=HEADERS, json={**scope,
            'op': 'create', 'scopeNodeId': sector, 'discipline': 'security', 'title': 'Synthetic inputs',
            'text': 'Fixture only: tenant isolation must be verified.'}))['fragment']
        source = ok(client.post('/api/brief-vault', headers=HEADERS, json={**scope,
            'op': 'research', 'fragmentId': root['id'], 'title': 'Synthetic research',
            'text': 'Verify tenant separation', 'question': 'Does tenant isolation hold?', 'status': 'done'}))['fragment']
        base = '/api/oporahub/graph-proposals'
        context = ok(client.get(base + '/context', params=scope))
        proposal = ok(client.post(base, headers=HEADERS, json={**scope,
            'operationId': 'synthetic-research-task', 'parentRevision': context['acceptedHead'],
            'expectedGraphDigest': context['graphDigest'], 'subject': 'Research-derived fixture task',
            'plan': {'draftVersion': 3, 'extend': [{'node': '@' + node,
                'expectedRevision': context['stateRevision'],
                'fragmentRef': {'fragmentId': source['id'], 'revision': source['revision']}}]}}))
        assert proposal['accepted'] is False
        acceptance = {**scope, 'expectedAcceptedHead': context['acceptedHead'],
            'expectedGraphDigest': context['graphDigest'], 'reviewedChangesId': proposal['id'], 'adoptBaseGraphDigest': None}
        if proposal.get('contentBase', {}).get('requiresAdoption'):
            acceptance['adoptBaseContentDigest'] = proposal['contentBase']['digest']
        accepted = ok(client.post(base + '/' + proposal['id'] + '/accept', headers=HEADERS, json=acceptance))
        first_session = open_session(client, {**scope, 'worker': {'name': 'first', 'office': 'synthetic'}})
        second_session = open_session(client, {**scope, 'worker': {'name': 'second', 'office': 'synthetic'}})
        first_auth, second_auth = worker(first_session['token']), worker(second_session['token'])
        executions = '/api/oporahub/executions'
        first = ok(client.post(executions + '/start', headers=first_auth, json={**scope, 'nodeId': node}))
        assert first['assignment']['researchEvidence']['records']
        assert first['acceptedRevision'] == accepted['id']
        original_head = head(repo)
        assert first['assignment']['codeContext']['headSha'] == original_head
        assignment_path = executions + '/' + first['executionId'] + '/assignment'
        first_read_auth = {**first_auth, 'X-Opora-Execution-Token': first['token']}
        assert client.get(assignment_path, params=scope, headers=first_read_auth).status_code == 200
        assert client.get(assignment_path, params={**scope, 'workspace': 'foreign'}, headers=first_read_auth).status_code == 403
        assert client.get(assignment_path, params={**scope, 'project': 'draft'}, headers=first_read_auth).status_code == 403
        foreign = open_session(client, {'project': 'draft', 'workspace': 'draft',
                                       'worker': {'name': 'foreign', 'office': 'synthetic'}})
        hidden = client.get(assignment_path, params={'project': 'draft', 'workspace': 'draft'},
                            headers={**worker(foreign['token']), 'X-Opora-Execution-Token': first['token']})
        assert hidden.status_code == 409 and first['executionId'] not in hidden.text
        for suffix in ('', '/context', '/' + first['executionId'] + '/results'):
            params = {**scope, **({'nodeId': node} if suffix == '/context' else {})}
            assert client.get(executions + suffix, params=params, headers=first_auth).status_code == 200
        assert client.post(executions + '/start', headers=second_auth, json={**scope, 'nodeId': node}).status_code == 409
        credential = {**scope, 'token': first['token'], 'epoch': first['epoch']}
        for step, status, notes in [('s1', 'done', 'Synthetic partial result retained'),
                                    ('s2', 'failed', 'BLOCKER: missing independent tenant fixture')]:
            ok(client.post(executions + '/' + first['executionId'] + '/steps', headers=first_auth,
                json={**credential, 'requestId': step, 'stepId': step, 'status': status,
                      'evidence': {'notes': notes, 'commits': [head(repo)], 'checks': ['synthetic fixture']}}))
        current_head = commit_card(repo, node)
        assert current_head != original_head
        # Simulate elapsed lease time only; no graph, evidence or execution receipt is fabricated.
        with client.app.state.service.db_for(scope['project']) as db:
            db.execute('UPDATE card_leases SET expires_at=0 WHERE project_id=? AND workspace_id=? AND node_id=?',
                       (scope['project'], scope['workspace'], node))
        resumed_session = open_session(client, {**scope, 'worker': {'name': 'fresh-after-crash', 'office': 'synthetic'}})
        assert resumed_session['sessionId'] not in {first_session['sessionId'], second_session['sessionId']}
        second_auth = worker(resumed_session['token'])
        second = ok(client.post(executions + '/start', headers=second_auth, json={**scope, 'nodeId': node}))
        read = ok(client.get(executions + '/' + second['executionId'] + '/assignment', params=scope,
                            headers={**second_auth, 'X-Opora-Execution-Token': second['token']}))
        assert second['executionId'] != first['executionId']
        assert {k: v for k, v in read['assignment'].items() if k not in {'codeContext', 'resumedFrom'}} == {
            k: v for k, v in first['assignment'].items() if k != 'codeContext'}
        assert read['assignment']['codeContext']['headSha'] == current_head
        assert read['assignment']['resumedFrom'] == {'executionId': first['executionId'],
            'acceptedRevision': accepted['id'], 'codeContext': first['assignment']['codeContext']}
        assert read['progress']['current'] == 's2'
        details = ok(client.get(executions + '/' + first['executionId'] + '/results', params=scope, headers=second_auth))
        assert 'Synthetic partial result retained' in str(details), 'New session must retrieve persisted partial checkpoint evidence on demand'
        assert 'BLOCKER: missing independent tenant fixture' in str(details)
        assert details['results'] == [] and len(details['checkpoints']) == 2
        assert {item['acceptedRevision'] for item in details['checkpoints']} == {accepted['id']}
        assert read['assignment']['codeContext']['headSha'] == head(repo)
        assert read['assignment']['codeContext']['worktree'] == str(repo.resolve())
        def unexpected_git(*args, **kwargs):
            raise AssertionError('Stored assignment/heartbeat must not re-read Git')
        monkeypatch.setattr('backend.canvas.opora_execution_code_context.git', unexpected_git)
        reread = ok(client.get(executions + '/' + first['executionId'] + '/assignment', params=scope,
                              headers=first_read_auth))
        assert reread['assignment']['codeContext']['headSha'] == original_head
        renewed = ok(client.post(executions + '/' + second['executionId'] + '/heartbeat', headers=second_auth,
            json={**scope, 'token': second['token'], 'epoch': second['epoch'], 'ttlSeconds': 60}))
        assert renewed['assignment']['codeContext']['headSha'] == current_head
        denied = client.post(executions + '/' + first['executionId'] + '/heartbeat', headers=first_auth,
                             json={**credential, 'ttlSeconds': 60})
        assert denied.status_code == 409
