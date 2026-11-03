"""Nástrojové uzly srdce: ticket.issue a ticket.answer jsou registrované typy s pevným podpříkazem, mimo Srdce v1."""
from backend.flow.catalogs.heart import nodes, seed
from backend.flow.node_types import NODE_TYPES


def tool(type_, **params):
    return {"node_id": type_, "type": type_, "params": params, "port": "tool"}


def test_ticket_tools_are_registered_and_grant_only_their_subcommand():
    for name in ("tool.ticket_issue", "tool.ticket_answer"):
        assert NODE_TYPES[name].port("tool", "out").kind == "tool"
    assert nodes._subcommands([tool("tool.ticket_issue"), tool("tool.ticket_answer")]) == ("ticket-issue",
                                                                                           "ticket-answer")
    assert nodes._subcommands([tool("tool.opora_heart", subcommands=["plan"]), tool("tool.ticket_issue")]) == (
        "plan", "ticket-issue")
    assert nodes._subcommands([tool("tool.opora_heart", subcommands=None), tool("tool.ticket_issue")]) is None
    assert nodes._subcommands([]) == ()


def test_heart_v1_seed_does_not_use_the_ticket_tools():
    assert {node["type"] for node in seed.GRAPH["nodes"]}.isdisjoint(nodes.TOOL_SUBCOMMANDS)
