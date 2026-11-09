"""Native layout semantics remain draft-only or explicitly reviewed with original identities."""
import pytest
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.canvas.test_canvas_layout import prepared
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import proposal, accept
from backend.canvas.test_opora_graph_changes import approve
from backend.canvas.opora_graph_changes import OporaGraphChanges


@pytest.mark.parametrize('accepted', [False, True])
def test_layout_native_initial_or_reviewed_color_parent_positions(setup, accepted):
    client, service, auth = setup
    prepared(client)
    native = OporaGraphProposals(service)
    if accepted:
        accept(native, proposal(native))
    before = native.context('draft', 'draft')
    data = {'parentRevision': before['acceptedHead'], 'expectedGraphDigest': before['graphDigest'],
            'subject': 'Readable area layout', 'area': '@a0', 'order': ['@n1', '@n0'], 'columns': 2, 'color': 'teal'}
    response = call(client, auth, 'canvas_routes.canvas_layout', data, 'layout')
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['verified'] and saved['acceptedHead'] == before['acceptedHead']
    assert call(client, auth, 'canvas_routes.canvas_layout', data, 'layout').json() == saved
    assert call(client, auth, 'canvas_routes.canvas_layout', {**data, 'color': 'rose'}, 'layout').status_code == 409
    if accepted:
        assert native.context('draft', 'draft') == before
        record = saved['result']['result']
        assert record['schemaVersion'] == 3 and not record['accepted']
        area = next(row for row in record['changes']['nodes'] if row['id'] == 'a0')
        assert area['proposedWorking']['color'] == 'teal' and 'color' in area['fields']
        approve(OporaGraphChanges(service), record)  # Explicit human test fixture, never adapter acceptance.
    graph = service.view('draft', 'draft')['graph']
    nodes = {node['id']: node for node in graph['nodes']}
    assert nodes['a0']['color'] == 'teal'
    assert nodes['n0']['parentId'] == nodes['n1']['parentId'] == 's0'
    assert nodes['n1']['x'] < nodes['n0']['x']
    context = native.context('draft', 'draft')
    invalid = {**data, 'parentRevision': context['acceptedHead'], 'expectedGraphDigest': context['graphDigest'], 'color': 'invalid'}
    assert call(client, auth, 'canvas_routes.canvas_layout', invalid, 'bad-color').status_code in (409, 422)
    assert service.view('draft', 'draft')['graph'] == graph
