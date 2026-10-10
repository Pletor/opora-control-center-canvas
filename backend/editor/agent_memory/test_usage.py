import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, output, payload, prepared, send


def summary(client):
    response = client.get('/api/desktop-v3/usage-summary', params=SCOPE)
    assert response.status_code == 200, response.text
    return response.json()


def test_usage_persists_aggregates_by_sector_and_preserves_unknowns(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        before = client.get('/api/view', params=SCOPE).json()
        graph = before['graph']
        graph['nodes'][0]['parentId'] = 'sector'
        graph['nodes'].append({'id': 'sector', 'kind': 'sector', 'parentId': None, 'name': 'S', 'purpose': '', 'x': 0, 'y': 0})
        assert client.post('/api/graph', headers=HEADERS, json={**SCOPE, 'digest': before['digest'], 'graph': graph}).status_code == 200
        assert summary(client)['nodes']['focus']['tokens'] is None
        for revision, tokens in [(1, 30), (2, 0)]:
            response = send(client, payload(revision, output=output(usage={'tokens': tokens, 'durationMs': 500, 'attempts': 1})))
            assert response.status_code == 200, response.text
        measured = summary(client)
        assert measured['nodes']['focus'] == {'tokens': 30, 'durationMs': 1000, 'attempts': 2, 'reports': 2}
        assert measured['sectors']['sector'] == measured['nodes']['focus']
        assert summary(client)['nodes']['dalsi']['tokens'] is None
        brief = client.get('/api/desktop-v3/node-brief', params={**SCOPE, 'nodeId': 'focus'}).json()
        assert brief['usage']['own'] == measured['nodes']['focus']
        assert send(client, payload(3, output=output(usage={'tokens': None, 'attempts': 1}))).status_code == 200
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert summary(client)['sectors']['sector'] == {'tokens': None, 'durationMs': None, 'attempts': 3, 'reports': 3}


@pytest.mark.parametrize('usage', [None, {'tokens': True}, {'tokens': -1}, {'durationMs': 1.5}, {'cost': 42}, {'attempts': 10**20}])
def test_invalid_usage_rejects_entire_output(tmp_path, usage):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        before = client.get('/api/desktop-v3/state', params=SCOPE).json()
        assert send(client, payload(output=output(usage=usage))).status_code == 409
        assert client.get('/api/desktop-v3/state', params=SCOPE).json() == before
        assert summary(client)['nodes']['focus']['reports'] == 0


def test_summary_is_cached_until_the_next_accepted_output(tmp_path):
    """Karta P3: součty se drží v cache podle tokenu dat; nový výstup agenta je přepočítá."""
    from backend.editor.agent_memory.usage import usage_summary

    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        prepared(client)
        service = app.state.service
        first = usage_summary(service, 'draft', 'draft')
        assert usage_summary(service, 'draft', 'draft') is first and first['nodes']['focus']['reports'] == 0
        assert send(client, payload(1, output=output(usage={'tokens': 7, 'durationMs': 1, 'attempts': 1}))).status_code == 200
        after = usage_summary(service, 'draft', 'draft')
        assert after is not first and after['nodes']['focus'] == {'tokens': 7, 'durationMs': 1, 'attempts': 1, 'reports': 1}
