"""Native frontier composition shared by UI and authenticated Heart capabilities."""
from backend.canvas import opora_agent_state_pulls as pulls
from backend.editor.agent_packet.card_checklist import checklists, missing
from backend.editor.agent_packet.frontier import frontier


def read_frontier(state, agent_workspace, leases, project, workspace, nodeId=""):
    with state.canvas.reading(project):
        graph = state.canvas.view(project, workspace)["graph"]
        stored = state.read(project, workspace)["state"]
        spaces = agent_workspace.read_many(project, workspace, [n["id"] for n in graph["nodes"]])
        linked = pulls.read(state.canvas, project, workspace) or []
        merged = {item["cardId"] for item in linked
                  if item.get("cardId") and item["state"] == "merged" and item.get("planWrittenBack") is True}
        out = frontier(graph, stored, nodeId, {key: value.get("frame", "") for key, value in spaces.items()},
                       leases.summary(project, workspace)["nodes"], merged=merged)
        # Kontrolní pás: co každé kartě chybí (klíče polí), aby relace věděla, co doplnit.
        rows = [row for group in ("frontier", "claimed", "blocked", "waiting", "closed") for row in out[group]]
        lists = checklists(state.canvas, project, workspace, graph, stored, {row["id"] for row in rows})
        for row in rows:
            if row["id"] in lists:
                row["missing"] = missing(lists[row["id"]])
        return out
