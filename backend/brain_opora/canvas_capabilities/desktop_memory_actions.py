"""Native working memory writes preserve per-item CAS and authenticated agent attribution."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.agent_workspace import AgentWorkspace
from backend.editor.agent_memory.memory_items import MemoryItems
from backend.canvas.payload_errors import NextStep

PREFIX = 'desktop_v3_routes.'
CONTRACTS = {
    PREFIX+'write_agent_workspace': contract(('nodeId', 'expectedRevision', 'sections'), effect='working-memory', replay=True,
        cas='native agent workspace revision', output='Native partial-section write, by agent; optional external memory mirroring is not requested'),
    PREFIX+'write_rule': contract(('id', 'op', 'expected', 'item'), effect='rule-proposal', replay=True,
        cas='native exact expected item; human rules remain protected', output='Native pending agent rule, never effective human approval'),
    PREFIX+'write_decision': contract(('id', 'op', 'expected', 'item'), effect='working-memory', replay=True,
        cas='native exact expected item and immutable decision history', output='Native agent decision record'),
}
for item in CONTRACTS.values():
    item['test'] = 'backend/api/brain_opora/test_canvas_capability_memory.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    state = DesktopV3State(service)
    agent_space = AgentWorkspace(service, state)
    memory = MemoryItems(state)
    is_space = capability.endswith('write_agent_workspace')
    collection = 'rules' if capability.endswith('write_rule') else 'decisions'
    def snapshot():
        return agent_space.read(project, workspace, data['nodeId']) if is_space else state.read(project, workspace)
    def action():
        payload = {'project': project, 'workspace': workspace, **data}
        if not is_space and isinstance(payload.get('item'), dict):
            payload['item'] = {**payload['item'], 'by': 'agent'}
        return agent_space.save({**payload, 'by': 'agent'}) if is_space else memory.apply(collection, payload, actor='agent')
    def verify(before, after, result):
        if is_space:
            valid = result == after and after['workspace']['by'] == 'agent'
        else:
            readback = memory.read(collection, project, workspace, data['id'])
            valid = readback['revision'] == result['revision'] and readback['item'] == result['item']
        if not valid:
            raise NextStep('Native working memory readback failed.', code='operation_incomplete', hint='Inspect existing native revision.')
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=action, verify=verify)
