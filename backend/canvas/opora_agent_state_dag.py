"""Card DAG facts for the agent-state document (docs/oporahub-agent-state.md, "Graf karet").

A card is unblocked when every `next` predecessor is merged + written back (OporaHub chain) or,
for older data, confirmed done (`done.confirmed`). A blocked card's claim action is blocked with
`blocked_by_predecessor`. Each `cards[]` entry gains `kind`, `layer`, `order` (intended order or null),
`blockedBy`, `topoIndex` (ties broken by `order`), `nextActionId` and `gate`. Pure over facts the caller
collected under the project locks.
"""
from backend.canvas import card_dag
from backend.canvas import opora_agent_state_rules as rules
from backend.canvas.card_context import card_layer, effective_type
from backend.canvas.opora_event_stage import gate_summary
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

BLOCKED = "blocked_by_predecessor"


def facts(canvas, project, workspace, linked):
    """`{nodes, blockedBy, topoIndex}` for every card (node or sector) of the workspace graph."""
    graph = canvas.view(project, workspace)["graph"]
    nodes = {node["id"]: node for node in graph["nodes"] if node["kind"] in card_dag.CARD_KINDS}
    pairs = card_dag.next_edges(graph)
    stored = DesktopV3State(canvas).current(project, workspace)["state"]["nodes"]
    satisfied = {key for key, value in stored.items() if value.get("done", {}).get("confirmed")}
    satisfied |= {item["cardId"] for item in linked or []
                  if item.get("cardId") and item["state"] == "merged" and item.get("planWrittenBack") is True}
    intended = {key: node["order"] for key, node in nodes.items() if "order" in node}
    order = card_dag.topo_order(nodes, pairs, intended)
    return {"nodes": nodes, "blockedBy": card_dag.blocked_by(nodes, pairs, satisfied),
            "topoIndex": {key: index for index, key in enumerate(order)}}


def block_claims(claims, dag):
    """A ready claim of a card with unfinished predecessors becomes blocked (budget reasons keep priority)."""
    for item in claims:
        if item["status"] == "ready" and dag["blockedBy"].get(item["nodeId"]):
            item["status"], item["blockReason"] = "blocked", BLOCKED


def retag(actions, dag):
    """A predecessor-blocked claim gets a new id whenever its blocker set changes (same id = same intent)."""
    for action in actions:
        if action["verb"] == "claim" and action.get("blockReason") == BLOCKED:
            action["id"] = rules.stable_id("act_", action["id"], dag["blockedBy"][action["targetId"]])
    return actions


def enrich(cards, dag, actions, reviewing):
    gates = {}
    for gate in (reviewing or {}).get("gates", []):
        gates.setdefault(gate["cardId"], {})[gate["executionId"]] = gate
    result = []
    for entry in cards:
        node, key = dag["nodes"].get(entry["nodeId"], {}), entry["nodeId"]
        targets = {key, entry["executionId"]} - {None}
        action = next((item["id"] for item in actions if item["targetId"] in targets), None)
        own = gates.get(key, {})
        gate = own.get(entry["executionId"]) or (own[min(own)] if own else None)
        result.append({**entry, "kind": effective_type(node), "layer": card_layer(node),
                       "order": node.get("order"), "blockedBy": dag["blockedBy"].get(key, []),
                       "topoIndex": dag["topoIndex"].get(key),
                       "nextActionId": action, "gate": gate_summary(gate)})
    return result
