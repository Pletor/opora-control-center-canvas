"""Native node image storage with scoped node ownership and durable write receipts."""
import base64
import hashlib
from fastapi import HTTPException
from backend.canvas.payload_errors import InvalidPayload, NextStep
from backend.editor.node.node_materials import NodeMaterials, FILE_NAME, decode_upload
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run

PREFIX = 'node_routes.'
CONTRACTS = {
    PREFIX+'upload_material': contract(('nodeId', 'dataUrl'), effect='draft-asset', replay=True,
        cas='native node existence/editable workspace; immutable receipt filename'),
    PREFIX+'material_file': contract(('nodeId', 'file'), output='Complete base64 bytes, MIME and SHA256'),
    PREFIX+'remove_material': contract(('nodeId', 'file', 'expectedSha256'), effect='draft-asset', replay=True,
        cas='current native file SHA256'),
}
for item in CONTRACTS.values():
    item['test'] = 'backend/api/brain_opora/test_canvas_capability_materials.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    native = NodeMaterials(service)
    def owned():
        view = service.view(project, workspace)
        if not any(node['id'] == data['nodeId'] for node in view['graph']['nodes']):
            raise HTTPException(404, 'Node does not exist in this workspace.')
        if capability != PREFIX+'material_file' and view['readOnly']:
            raise InvalidPayload('Workspace is read-only.', field='workspace')
    def content(name):
        path, mime = native.file_path(project, data['nodeId'], name)
        raw = path.read_bytes()
        return {'file': name, 'mime': mime, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                'encoding': 'base64', 'data': base64.b64encode(raw).decode('ascii')}
    if capability == PREFIX+'material_file':
        owned()
        try:
            return {'state': 'read', 'result': content(data['file'])}
        except FileNotFoundError:
            raise HTTPException(404, 'Material does not exist.') from None
    def snapshot():
        owned()
        folder = native._folder(project, data['nodeId'])
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*'))
                if p.is_file() and FILE_NAME.fullmatch(p.name)}
    def action():
        if capability == PREFIX+'upload_material':
            return native.save_upload({'project': project, 'workspace': workspace, **data})
        try:
            current = content(data['file'])
        except FileNotFoundError:
            raise HTTPException(404, 'Material does not exist.') from None
        if current['sha256'] != data['expectedSha256']:
            raise NextStep('Material bytes changed.', code='material_conflict', hint='Read the current material before removal.')
        return {'removed': native.remove(project, data['nodeId'], data['file']), 'file': data['file']}
    def verify(before, after, result):
        if capability == PREFIX+'upload_material':
            actual = content(result['file'])
            mime, submitted = decode_upload(data['dataUrl'])
            valid = (all(actual[key] == result[key] for key in ('file', 'bytes', 'mime'))
                     and actual['sha256'] == hashlib.sha256(submitted).hexdigest() and actual['mime'] == mime)
            expected = {**before, result['file']: actual['sha256']}
        else:
            expected = {key: value for key, value in before.items() if key != data['file']}
            valid = result['removed'] is True
        if not valid or expected != after:
            raise NextStep('Native material readback failed.', code='operation_incomplete', hint='Inspect existing material and receipt.')
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=action, verify=verify)
