"""Working memory uses native CAS, proposal authority and immutable replay."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import proposal, accept
from backend.editor.agent_memory.test_memory_items import rule, decision
from backend.editor.agent_memory.memory_items import MemoryItems
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def test_native_agent_workspace_partial_sections_cas_and_attribution(setup):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    data = {'nodeId': item['refs']['new'], 'expectedRevision': 0, 'sections': {'frame': 'Current evidence', 'handoff': 'Next step'}}
    first = call(client, auth, 'desktop_v3_routes.write_agent_workspace', data, 'space')
    assert first.status_code == 200, first.text
    result = first.json()
    assert result['result']['workspace']['by'] == 'agent'
    assert call(client, auth, 'desktop_v3_routes.write_agent_workspace', data, 'space').json() == result
    changed = call(client, auth, 'desktop_v3_routes.write_agent_workspace', {**data, 'expectedRevision': 1, 'sections': {'log': 'Progress'}}, 'space2')
    assert changed.status_code == 200, changed.text
    assert changed.json()['result']['workspace']['frame'] == 'Current evidence'
    assert call(client, auth, 'desktop_v3_routes.write_agent_workspace', data, 'stale').status_code == 409
    assert call(client, auth, 'desktop_v3_routes.write_agent_workspace', {**data, 'by': 'human'}, 'forged').status_code == 422
    assert native.context(**SCOPE)['acceptedHead'] == result['acceptedHead']


def test_native_rule_decision_proposals_cas_and_human_rule_protection(setup):
    client, service, auth = setup
    for name, make in (('rule', rule), ('decision', decision)):
        operation = 'desktop_v3_routes.write_'+name
        data = {'id': name, 'op': 'add', 'expected': None, 'item': {**make(name), 'by': 'human'}}
        first = call(client, auth, operation, data, name)
        assert first.status_code == 200, first.text
        saved = first.json()
        assert saved['result']['item']['by'] == 'agent'
        assert call(client, auth, operation, data, name).json() == saved
        old = saved['result']['item']
        changed = call(client, auth, operation, {'id': name, 'op': 'update', 'expected': old, 'item': {**old, 'text': 'Updated evidence'}}, name+'-update')
        assert changed.status_code == 200, changed.text
        assert call(client, auth, operation, {'id': name, 'op': 'remove', 'expected': old, 'item': None}, name+'-stale').status_code == 409
    human = rule('human-rule')
    MemoryItems(DesktopV3State(service)).apply('rules', {**SCOPE, 'id': human['id'], 'op': 'add', 'expected': None, 'item': human}, actor='human')
    refused = call(client, auth, 'desktop_v3_routes.write_rule', {'id': human['id'], 'op': 'remove', 'expected': human, 'item': None}, 'remove-human')
    assert refused.status_code == 403
