// Závěr kroku (prototyp `stepSimulation`): potvrzenky workflow, události změn stavu, dokončení řádků vazeb (latence,
// odpověď, zaokrouhlení), události zdrojů, náhled nechá backlog z autoritativního stavu, souhrn a vzorky historie.
import type { Summary } from "./simulation-types";
import { round, SOURCES, SYNCHRONOUS, type StepContext } from "./step-schedule";
import { captureWorkflowReceipts } from "./workflow-routing";

export function finishStep(ctx: StepContext): void {
  const { domain, s, previous, preview, edges, byId, emitEvent } = ctx;
  if (!preview) captureWorkflowReceipts(domain, s);
  for (const [nodeId, row] of Object.entries(s.nodes)) {
    const old = previous.nodes[nodeId];
    if (old && old.state !== row.state) emitEvent(nodeId, row.state === "healthy" ? "recovery" : row.state === "failed" ? "failure" : "state", `${old.state} → ${row.state}`);
  }
  for (const edge of edges) {
    const flow = s.edges[edge.id], target = s.nodes[edge.to.nodeId], source = s.nodes[edge.from.nodeId];
    flow.synchronous = SYNCHRONOUS.has(edge.type); flow.latencyMs = Math.max(target.latencyMs, source.latencyMs); flow.slow = target.slow || source.slow;
    flow.response = flow.synchronous ? flow.accepted * target.dependencySuccess : 0;
    for (const key of ["offered", "accepted", "rejected", "response"] as const) flow[key] = round(flow[key]);
  }
  const sourceRows = domain.nodes.filter((n) => SOURCES.has(n.type)).map((n) => s.nodes[n.id]);
  for (const row of sourceRows) if (row.offered > 0) emitEvent(row.nodeId, "flow", `MODEL: nabídka ${round(row.offered)}, dokončeno / přijato ${round(row.completed)} jednotek.`);
  if (preview) for (const [id, row] of Object.entries(s.nodes)) {
    row.backlog = previous.nodes[id]?.backlog || 0;
    if (byId.get(id)!.type === "cdc-connector") row.technology.lag = row.backlog;
  }
  const rows = Object.values(s.nodes);
  const summary: Summary = {
    offered: round(sourceRows.reduce((n, r) => n + r.offered, 0)), completed: round(sourceRows.reduce((n, r) => n + r.completed, 0)),
    rejected: round(rows.reduce((n, r) => n + r.rejected, 0)), backlog: round(rows.reduce((n, r) => n + r.backlog, 0)), maxLatencyMs: round(Math.max(0, ...rows.map((r) => r.latencyMs))),
  };
  s.summary = summary;
  if (!preview) { s.samples.push({ tick: s.tick, ...summary }); s.samples = s.samples.slice(-200); s.events = s.events.slice(-1000); }
}
