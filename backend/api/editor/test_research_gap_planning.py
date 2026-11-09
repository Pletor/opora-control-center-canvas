"""Synthetic planner output through native HTTP; no live LLM, web research or Ample writes."""
from copy import deepcopy

from backend.api.brain_opora.test_gate_routes import open_session, worker
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, edge
from backend.brain_opora.determinism import tokens
from backend.editor.node.test_removals import HEADERS, SCOPE
from backend.editor.research import continuations
from backend.editor.research.planning_source import pins
from backend.editor.research.test_continuations import imported
from backend.editor.research.test_finalization import FIELDS, finish

GRAPH = '/api/oporahub/graph-proposals'
EXEC = '/api/oporahub/executions'


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def heart(client):
    session, token = tokens.issue_heart(client.app.state.service, 'draft', 'draft')
    return session, {**HEADERS, tokens.HEADER: token, 'X-Opora-Actor': 'agent; name=heart'}


def propose(client, auth, plan, operation):
    context = ok(client.get(GRAPH + '/context', params=SCOPE, headers=auth))
    payload = {**SCOPE, 'operationId': operation, 'parentRevision': context['acceptedHead'],
               'expectedGraphDigest': context['graphDigest'], 'subject': 'Synthetic bounded verification plan', 'plan': plan}
    result = ok(client.post(GRAPH, headers=auth, json=payload))
    assert ok(client.post(GRAPH, headers=auth, json=payload)) == result
    assert ok(client.get(GRAPH + '/' + result['id'], params=SCOPE, headers=auth)) == result
    return result


def accept_fixture(client, proposal):
    context = ok(client.get(GRAPH + '/context', params=SCOPE))
    payload = {**SCOPE, 'expectedAcceptedHead': context['acceptedHead'], 'expectedGraphDigest': context['graphDigest'],
               'reviewedChangesId': proposal['id'], 'adoptBaseGraphDigest': None}
    if proposal.get('contentBase', {}).get('requiresAdoption'):
        payload['adoptBaseContentDigest'] = proposal['contentBase']['digest']
    return ok(client.post(GRAPH + '/' + proposal['id'] + '/accept', headers=HEADERS, json=payload))


def claim(client, auth, node, request):
    context = ok(client.post(EXEC + '/context', headers=auth,
                            json={**SCOPE, 'nodeId': node, 'contextProtocolVersion': 2}))
    return client.post(EXEC + '/claim', headers=auth, json={**SCOPE, 'nodeId': node, 'contextProtocolVersion': 2,
        'requestId': request, 'ttlSeconds': 60, 'expectedAcceptedHead': context['acceptedHead'],
        'expectedContextVersion': context['contextVersion']})


def test_completed_no_evidence_research_persists_actionable_verification_gap(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, auth = heart(client)
        _, imported_result, source = imported(client, finalization=FIELDS)
        finish(client, source)
        service = client.app.state.service
        assert continuations.wakes(service, 'draft', 0)  # Native HeartDriver polling boundary.
        receipt = ok(client.get('/api/research/continuations', params=SCOPE, headers=auth))['continuations'][0]
        original = ok(client.get('/api/research/originals/' + source['id'], params=SCOPE, headers=auth))
        assert original['original']['details']['research']['status'] == 'done'
        assert original['original']['details']['research']['verdict'] == 'unverified'
        question = ok(client.get('/api/research/cards/' + receipt['researchId'], params=SCOPE, headers=auth))['card']
        assert question['verification']['status'] == 'unverified' and question['sources'] == []
        # Explicit synthetic planner response, not a claim that a live LLM produced this task.
        proposal = propose(client, auth, {'draftVersion': 3, 'researchSource': pins(receipt), 'nodes': [{
            'ref': 'verify-gap', 'kind': 'node', 'name': 'Verify unsupported tenant-isolation claim',
            'text': 'No supporting evidence was found. Capture two independent tenant sessions and reproduce the boundary test.',
            'spec': {'goal': 'Resolve original question ' + receipt['researchId'],
                     'acceptance': 'Attach reproducible cross-tenant test output and exact source revision; otherwise retain unverified verdict.'}}]}, receipt['operationId'])
        assert proposal['accepted'] is False
        assert proposal['researchSource']['sourceFragmentId'] == source['id']
        assert proposal['researchSource']['researchId'] == question['id']
        spec = next(item for item in proposal['contentEffects']['documents'] if item['kind'] == 'spec')
        assert 'cross-tenant test output' in spec['value']['acceptance']
        assert continuations.wakes(service, 'draft', 1) == []
        completed = ok(client.get('/api/research/continuations', params=SCOPE, headers=auth))['continuations'][0]
        assert completed['status'] == 'complete' and completed['proposalId'] == proposal['id']
        assert completed['acceptedAtReadback'] is False
        assert ok(client.get('/api/research/cards/' + question['id'], params=SCOPE, headers=auth))['card'] == question
        assert proposal['refs']['verify-gap'] not in {n['id'] for n in ok(client.get('/api/view', params=SCOPE))['graph']['nodes']}


def test_partial_findings_plan_blocks_dependency_only_and_unrelated_execution_continues(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, auth = heart(client)
        finding = card('partial-finding', title='Observed login screen only', content='Synthetic screenshot confirms a login screen, not tenant isolation.',
            verification={'status': 'observed', 'method': 'Synthetic fixture screenshot', 'at': '2026-11-09'},
            sources=[{'ref': 'fixture://login-screen', 'platform': 'file', 'title': 'Synthetic screen', 'quote': 'Login', 'accessedAt': '2026-11-09'}])
        _, result, source = imported(client, extra_operations=[finding, edge(id='partial-evidence', fromId='partial-finding', toId='rc_login', evidenceIds=['partial-finding'])], finalization=FIELDS)
        finish(client, source)
        service = client.app.state.service
        assert continuations.wakes(service, 'draft', 0)
        receipt = continuations.listing(service, 'draft', 'draft')[0]
        independent = propose(client, auth, {'draftVersion': 3, 'nodes': [{'ref': 'independent', 'kind': 'node', 'name': 'Independent copy correction', 'text': 'No tenant-isolation assumption.'}]}, 'independent')
        accept_fixture(client, independent)
        session = open_session(client, {**SCOPE, 'worker': {'name': 'independent-worker'}})
        owner = worker(session['token'])
        running = ok(claim(client, owner, independent['refs']['independent'], 'independent-claim'))
        proposal = propose(client, auth, {'draftVersion': 3, 'researchSource': pins(receipt), 'nodes': [
            {'ref': 'verify', 'kind': 'node', 'name': 'Verify missing tenant boundary', 'text': 'Capture independent tenant sessions; retain unverified until tested.'},
            {'ref': 'dependent', 'kind': 'node', 'name': 'Implement tenant optimization after verification', 'text': 'Blocked by missing boundary proof.'}],
            'edges': [{'from': 'verify', 'to': 'dependent', 'port': 'next'}]}, receipt['operationId'])
        assert not proposal['accepted']
        assert continuations.wakes(service, 'draft', 1) == []
        accept_fixture(client, proposal)  # Explicit synthetic human fixture, never Ample acceptance.
        denied = claim(client, owner, proposal['refs']['dependent'], 'dependent-claim')
        assert denied.status_code == 409, denied.text
        assert denied.json()['code'] == 'blocked_by_predecessor'
        assert ok(claim(client, owner, proposal['refs']['verify'], 'verify-claim'))['state'] == 'running'
        alive = ok(client.post(EXEC + '/' + running['executionId'] + '/heartbeat', headers=owner,
            json={**SCOPE, 'token': running['token'], 'epoch': running['epoch'], 'ttlSeconds': 60}))
        assert alive['state'] == 'running' and alive['assignment'] == running['assignment']
        assert ok(client.get('/api/research/cards/partial-finding', params=SCOPE, headers=auth))['card']['verification']['status'] == 'observed'
        assert ok(client.get('/api/research/cards/rc_login', params=SCOPE, headers=auth))['card']['verification']['status'] == 'unverified'


def test_two_independent_authenticated_sessions_cannot_overwrite_same_drawing_revision(tmp_path):
    from backend.editor.node.test_drawings import ELEMENT
    with client_with_sector(tmp_path) as client:
        one, first = heart(client)
        two, second = heart(client)
        assert one != two and first[tokens.HEADER] != second[tokens.HEADER]
        scope = {**SCOPE, 'layer': ''}
        before = ok(client.get('/api/drawing', params=scope, headers=first))
        assert ok(client.get('/api/drawing', params=scope, headers=second)) == before
        scene = {'elements': [deepcopy(ELEMENT)]}
        saved = ok(client.post('/api/drawing', headers=first, json={**scope, 'expected_revision': before['revision'], 'scene': scene}))
        other_scene = {'elements': [{**ELEMENT, 'x': 999}]}
        denied = client.post('/api/drawing', headers=second, json={**scope, 'expected_revision': before['revision'], 'scene': other_scene})
        assert denied.status_code == 409, denied.text
        current = ok(client.get('/api/drawing', params=scope, headers=second))
        assert current['revision'] == saved['revision'] and current['scene'] == scene
