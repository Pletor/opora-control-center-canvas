// Potvrzenky workflow (prototyp `workflow-routing.mjs`): volá se jen po skutečném kroku grafu, když je známé dokončení
// dál po proudu. Snímek váže souhrnný výsledek na původní odeslání, ne na budoucí zapojení vazeb.
import { WORKFLOW_VERSION } from "./workflow-model";
import type { SimDomain, SimEdge, SimulationState } from "./simulation-types";

const signature = (e: SimEdge) => JSON.stringify([e.from, e.to, e.type, e.enabled, e.condition]);
const usable = (e: SimEdge) => e.enabled && (!e.condition || e.condition.trim() === "always");

type Route = { edgeId: string; signature: string; targetId: string; amount: number; settled: boolean; success: number; reason?: string; observed?: Record<string, number> };

export function captureWorkflowReceipts(domain: SimDomain, state: SimulationState): SimulationState {
  for (const node of domain.nodes) {
    const technology = state.nodes[node.id]?.technology;
    if (technology?.modelVersion !== WORKFLOW_VERSION) continue;
    const outgoing = domain.edges.filter((e) => e.from.nodeId === node.id && e.from.portId === "job-out" && usable(e));
    for (const batch of technology.batches) {
      if (batch.stage !== "inflight" || batch.outcome !== null) continue;
      const receipt: { tick: number; routes: Route[]; success?: number } = batch.receipt ? structuredClone(batch.receipt)
        : { tick: batch.dispatchTick, routes: outgoing.map((edge) => ({ edgeId: edge.id, signature: signature(edge), targetId: edge.to.nodeId, amount: batch.amount / outgoing.length, settled: false, success: 0 })) };
      for (const route of receipt.routes) {
        if (route.settled) continue;
        const edge = domain.edges.find((e) => e.id === route.edgeId), flow = state.edges[route.edgeId], target = state.nodes[route.targetId];
        if (!edge || signature(edge) !== route.signature) { route.settled = true; route.reason = "route-changed"; continue; }
        if (flow?.dispatchTick === receipt.tick && flow.offered > 0) {
          const completedRatio = target?.admitted ? Math.max(0, Math.min(1, target.completed / target.admitted)) : 0;
          route.success = Math.max(0, Math.min(1, flow.accepted / flow.offered)) * completedRatio;
          route.settled = true; route.reason = "observed-fluid-completion";
          route.observed = { tick: state.tick, offered: flow.offered, accepted: flow.accepted, downstreamCompleted: target?.completed || 0 };
        } else if (state.tick > receipt.tick + 1) { route.settled = true; route.reason = "dispatch-not-observed"; }
      }
      if (receipt.routes.every((r) => r.settled)) {
        const amount = receipt.routes.reduce((n, r) => n + r.amount, 0);
        receipt.success = amount ? receipt.routes.reduce((n, r) => n + r.amount * r.success, 0) / amount : 0;
        batch.outcome = receipt.success;
      }
      batch.receipt = receipt;
    }
    technology.receiptsPending = technology.batches.filter((b: { stage: string; outcome: unknown }) => b.stage === "inflight" && b.outcome === null).length;
  }
  return state;
}
