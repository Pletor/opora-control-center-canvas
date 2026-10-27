// Dopředný průchod kroku (prototyp `stepSimulation`): příprava řádků vazeb, tok zpožděných vazeb z minulého kroku,
// a pro každý uzel v pořadí rozvrhu příprava → chování → výstupy → řádek uzlu → rozdělení výstupu na vazby.
import { settleCacheReceipts } from "./cache-settlement";
import { config } from "./simulation-config";
import type { NodeRow } from "./simulation-types";
import { applyBehaviour } from "./step-node-behaviour";
import { applyOutputs } from "./step-node-outputs";
import { prepareNode, type NodeEval } from "./step-node-prepare";
import { usable, type StepContext } from "./step-schedule";
import { aiMetrics } from "./technology";

/** Řádky všech vazeb (i vypnutých, s důvodem) a tok zpožděných vazeb, který odeslal minulý krok. */
export function initEdges(ctx: StepContext): void {
  const { domain, s, previous, edges, delayed, incoming } = ctx;
  for (const e of domain.edges) {
    s.edges[e.id] = { offered: 0, accepted: 0, rejected: 0, response: 0, type: e.type, delayed: delayed.has(e.id), reason: e.enabled ? (usable(e) ? "" : "Podmínka není podporována modelem.") : "Vazba je vypnutá." };
    if (e.enabled && !usable(e)) s.warnings.push(`Vazba ${e.id}: textová podmínka se nevyhodnocuje.`);
  }
  for (const e of edges) if (delayed.has(e.id)) {
    const offered = previous.edges[e.id]?.nextOffered || 0;
    s.edges[e.id].offered = offered;
    s.edges[e.id].dispatchTick = previous.edges[e.id]?.nextDispatchTick ?? previous.tick;
    incoming.get(e.to.nodeId)?.push({ edge: e, amount: offered });
  }
}

function nodeState(n: NodeEval): string {
  const { failed, incident, resilience, circuit, profile, old, slow, backlog, rejected } = n, t = n.technology;
  if (failed) return incident?.kind === "recovering" || resilience.autoState === "recovering" ? "recovering" : "failed";
  if (circuit === "open") return "open";
  if (circuit === "half-open") return "half-open";
  if (profile === "workflow")
    return t!.configurationPending && !old.technology ? "idle" : t!.overflow ? "overloaded" : slow > 1 ? "slow" : t!.queued ? "pressured" : t!.held ? "idle" : resilience.autoState || "healthy";
  if (n.managedPool) return slow > 1 ? "slow" : resilience.autoState || "healthy";
  return t?.alert ? "degraded" : backlog > 0 || rejected > 0 ? "overloaded" : slow > 1 ? "slow" : resilience.autoState || "healthy";
}

function nodeRow(n: NodeEval): NodeRow {
  const { node, c, processed, technology, meshPlan, resilience, slow } = n;
  return {
    nodeId: n.nodeId, source: "educational-model", state: nodeState(n), slow: slow > 1, fault: n.incident?.kind || (resilience.autoFailed ? "automatic-overload" : null),
    offered: n.offered, processed, admitted: n.admitted, rejected: n.rejected, backlog: n.backlog, utilization: Math.min(1, n.pressurePct / 100), pressurePct: n.pressurePct,
    ...resilience, latencyMs: n.managedObject || n.managedPool || n.managedPartitioned ? technology!.latencyMs : c.latencyMs * slow * (meshPlan ? 1 + meshPlan.retryRatio : 1),
    ...(meshPlan ? { meshEjected: meshPlan.ejected } : {}), replicas: n.replicas, capacity: n.cap, internal: n.internal, circuit: n.circuit, openUntil: n.openUntil,
    failures: n.failures, outputs: n.outputs, inputAcceptance: n.inputAcceptance,
    ...(node.type === "ai-inference" ? { technology: aiMetrics(c, processed) } : technology ? { technology } : {}), completed: processed, dependencySuccess: 1,
  };
}

/** Rozdělí výstupy portu rovným dílem (balancer podle vah zdravých cílů); zpožděná vazba doručí až další krok. */
function dispatchOutputs(ctx: StepContext, n: NodeEval): void {
  const { s, delayed, incoming } = ctx;
  for (const [portId, amount] of Object.entries(n.outputs)) {
    const group = n.outEdges.filter((e) => e.from.portId === portId);
    for (const edge of group) {
      const flow = n.profile === "load-balancer" && portId === "http-out" ? amount * (n.technology!.weights[edge.id] || 0) : amount / group.length;
      if (delayed.has(edge.id)) { s.edges[edge.id].nextOffered = flow; s.edges[edge.id].nextDispatchTick = s.tick; }
      else { s.edges[edge.id].offered = flow; s.edges[edge.id].dispatchTick = s.tick; incoming.get(edge.to.nodeId)?.push({ edge, amount: flow }); }
    }
  }
}

export function forwardPass(ctx: StepContext): void {
  for (const nodeId of ctx.order) {
    const n = prepareNode(ctx, nodeId);
    applyBehaviour(ctx, n);
    applyOutputs(n);
    ctx.s.nodes[nodeId] = nodeRow(n);
    dispatchOutputs(ctx, n);
    settleCacheReceipts(ctx.plans, ctx.s, ctx.incoming, ctx.byId, config, ctx.delayed);
  }
}
