"""The actual native review API exposes immutable revision without agent acceptance."""
from backend.api.editor.test_opora_graph_routes import client, create, BASE, HEADERS, AGENT, SCOPE
from backend.canvas.test_opora_graph_complete import full_plan


def test_revise_http_reload_and_replay(client):
    base = create(client)
    assert client.post(BASE + '/' + base['id'] + '/accept', headers=HEADERS, json={**SCOPE,
        'expectedAcceptedHead': None, 'expectedGraphDigest': base['graphDigest'],
        'adoptBaseGraphDigest': base['graphDigest']}).status_code == 200
    context = client.get(BASE + '/context', params=SCOPE).json()
    created = client.post(BASE, headers=AGENT, json={**SCOPE, 'parentRevision': context['acceptedHead'],
        'expectedGraphDigest': context['graphDigest'], 'subject': 'Original', 'plan': full_plan()})
    assert created.status_code == 200, created.text
    old = created.json()
    plan = full_plan()
    plan['nodes'][0]['name'] = 'Readable title'
    payload = {**SCOPE, 'expectedAcceptedHead': context['acceptedHead'], 'expectedGraphDigest': context['graphDigest'],
        'subject': 'Reviewed titles', 'plan': plan, 'observeResearchSources': True, 'operationId': 'http-revision'}
    response = client.post(BASE + '/' + old['id'] + '/revise', headers=AGENT, json=payload)
    assert response.status_code == 200, response.text
    item = response.json()
    assert item['refs'] == old['refs'] and item['supersedes'] == old['id'] and not item['accepted']
    assert client.get(BASE + '/' + item['id'], params=SCOPE).json() == item
    assert client.get(BASE + '/' + old['id'], params=SCOPE).json() == {**old, 'supersededBy': item['id'], 'latestProposalId': item['id']}
    assert client.post(BASE + '/' + old['id'] + '/revise', headers=AGENT, json=payload).json() == item
    assert client.get(BASE + '/context', params=SCOPE).json()['acceptedHead'] == context['acceptedHead']
    assert client.post(BASE + '/' + item['id'] + '/accept', headers=AGENT, json={}).status_code == 403
