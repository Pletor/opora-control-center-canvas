"""Připravené příkazy agent-state: `command` jen u ready akcí, claim = start, ostatní = act."""

from backend.canvas import opora_agent_state_commands as commands


def test_ready_actions_carry_a_ready_command_line():
    actions = [
        {"id": "act_1", "verb": "propose_graph", "targetId": None, "status": "ready"},
        {"id": "act_2", "verb": "claim", "targetId": "n7", "status": "ready"},
        {"id": "act_3", "verb": "accept", "targetId": "g1", "status": "ready", "autonomy": "full"},
        {"id": "act_4", "verb": "link_pull_request", "targetId": "e1", "status": "ready"},
        {"id": "act_5", "verb": "accept", "targetId": "g2", "status": "blocked", "blockReason": "human_only"},
    ]
    out = commands.attach(actions)
    assert [item.get("command", "missing") for item in out] == [
        "opora_hub.py act --action-id act_1", "opora_hub.py start --node n7", "opora_hub.py act --action-id act_3",
        None, "missing"]
    assert out[4] == actions[4] and "command" not in actions[0]  # blokovaná beze změny, vstup se nemění
