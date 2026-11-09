"""First HTTP failure reports committed native bytes honestly, including receipt failures."""
import base64
import pytest

from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import proposal, accept
from backend.canvas.operation_receipts import Receipt
from backend.editor.node.node_materials import NodeMaterials


@pytest.mark.parametrize('stage', ['native_return', 'readback', 'complete'])
@pytest.mark.parametrize('error_type', [OSError, RuntimeError])
def test_first_postwrite_error_has_pending_identity_and_never_duplicates(setup, monkeypatch, stage, error_type):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    node = item['refs']['new']
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><text>immutable evidence</text></svg>'
    data = {'nodeId': node, 'dataUrl': 'data:image/svg+xml;base64,' + base64.b64encode(raw).decode()}
    real_save = NodeMaterials.save_upload
    writes = []
    def save(self, payload):
        result = real_save(self, payload)
        writes.append(result)
        if stage == 'native_return':
            raise error_type('injected after file write')
        return result
    def fail(*args, **kwargs):
        raise error_type('injected after native return')
    with monkeypatch.context() as patch:
        patch.setattr(NodeMaterials, 'save_upload', save)
        if stage == 'readback':
            patch.setattr(NodeMaterials, 'file_path', fail)
        if stage == 'complete':
            patch.setattr(Receipt, 'complete', fail)
        first = call(client, auth, 'node_routes.upload_material', data, 'fault-proof')
    assert first.status_code == 409, first.text
    assert first.json()['code'] == 'operation_incomplete'
    assert 'fault-proof' in first.json()['hint'] and 'may have changed' in first.json()['error']
    assert len(writes) == 1
    stored, _ = NodeMaterials(service).file_path('draft', node, writes[0]['file'])
    assert stored.read_bytes() == raw
    assert service.db_for('draft').execute("SELECT status FROM canvas_operation_receipts WHERE operation_id='fault-proof'").fetchone()[0] == 'pending'
    retry = call(client, auth, 'node_routes.upload_material', data, 'fault-proof')
    assert retry.status_code == 409 and retry.json()['code'] == 'operation_incomplete'
    assert list(stored.parent.iterdir()) == [stored]
