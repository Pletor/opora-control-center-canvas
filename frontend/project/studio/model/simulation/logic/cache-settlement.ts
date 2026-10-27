// Vyrovnání sdílené cache (prototyp `cache-settlement.mjs`): cache-aside obsluha dostane slevu SQL jen ze skutečných
// zásahů cache ve stejném kroku. Závislosti pořadí (cache před databází) existují jen během výpočtu, nikdy v modelu.
import { cloudProfile } from "./cloud-profiles";
import type { EdgeFlow, ModelConfig, SimDomain, SimEdge, SimNode, SimulationState } from "./simulation-types";

export type Incoming = Map<string, { edge: SimEdge; amount: number }[]>;
export type CachePlan = { node: SimNode; links: SimEdge[]; sql: SimEdge[]; creditAllowed: boolean; manualSql: boolean; resolved: boolean };
export type Schedule = { order: string[]; edges: SimEdge[]; delayed: Set<string> };

const handler = (node: SimNode) => ["service", "pod", "worker", "kubernetes-deployment"].includes(node.type) || cloudProfile(node.type) === "serverless-function";

export function planCacheSettlement(domain: SimDomain, { order, edges, delayed }: Schedule): { order: string[]; plans: CachePlan[]; warnings: string[] } {
  const adjacency = new Map(order.map((id) => [id, new Set<string>()])), plans: CachePlan[] = [], warnings: string[] = [];
  for (const e of edges) if (!delayed.has(e.id)) adjacency.get(e.from.nodeId)!.add(e.to.nodeId);
  const reaches = (from: string, to: string, seen = new Set<string>()): boolean => {
    if (from === to) return true;
    if (seen.has(from)) return false;
    seen.add(from);
    return [...adjacency.get(from)!].some((id) => reaches(id, to, seen));
  };
  for (const node of domain.nodes.filter(handler)) {
    const outgoing = edges.filter((e) => e.from.nodeId === node.id), links = outgoing.filter((e) => e.from.portId === "cache-out"), sql = outgoing.filter((e) => e.from.portId === "sql-out");
    if (!links.length) continue;
    const dependencies = links.flatMap((cache) => sql.map((query) => [cache.to.nodeId, query.to.nodeId] as const));
    let cyclic = [...links, ...sql].some((e) => delayed.has(e.id));
    const added: (readonly [string, string])[] = [];
    if (!cyclic) for (const [cache, db] of dependencies) {
      if (reaches(db, cache)) { cyclic = true; break; }
      if (!adjacency.get(cache)!.has(db)) { adjacency.get(cache)!.add(db); added.push([cache, db]); }
    }
    if (cyclic) {
      for (const [cache, db] of added) adjacency.get(cache)!.delete(db);
      warnings.push(`Cache ${node.id}: cyclic dependency; no same-tick SQL discount is credited.`);
    }
    const manualSql = (node.config.outputOverrides as ModelConfig | undefined)?.["sql-out"] !== undefined || node.deployment?.outputOverrides?.["sql-out"] !== undefined;
    plans.push({ node, links, sql, creditAllowed: !cyclic, manualSql, resolved: false });
  }
  const degree = new Map(order.map((id) => [id, 0]));
  for (const targets of adjacency.values()) for (const id of targets) degree.set(id, degree.get(id)! + 1);
  const sorted: string[] = [];
  while (sorted.length < order.length) {
    const id = order.find((id) => degree.get(id) === 0);
    if (id === undefined) throw new Error("Cache evaluation ordering cycle");
    degree.set(id, -1);
    sorted.push(id);
    for (const target of adjacency.get(id)!) degree.set(target, degree.get(target)! - 1);
  }
  return { order: sorted, plans, warnings };
}

export function settleCacheReceipts(plans: CachePlan[], state: SimulationState, incoming: Incoming, byId: Map<string, SimNode>, config: (node: SimNode) => ModelConfig, delayed: Set<string>): void {
  for (const plan of plans) {
    const { node, links, sql } = plan, row = state.nodes[node.id];
    if (plan.resolved || !row || !links.every((e) => state.nodes[e.to.nodeId])) continue;
    plan.resolved = true;
    let hits = 0, queries = 0;
    for (const edge of links) {
      const target = state.nodes[edge.to.nodeId], offered = state.edges[edge.id].offered;
      queries += offered;
      const actualHits = target.technology?.modelVersion === "cache-model/1" ? target.technology.hits
        : byId.get(edge.to.nodeId)!.type === "redis" ? target.processed * config(byId.get(edge.to.nodeId)!).hitRatio : 0;
      if (plan.creditAllowed && target.offered > 0) hits += actualHits * offered / target.offered;
    }
    hits = Math.min(row.processed, Math.max(0, hits));
    const fallback = Math.max(0, row.processed - hits);
    row.cacheReceipt = { modelVersion: "cache-receipt/1", cacheQueries: queries, cacheHits: hits, cacheFallback: fallback, creditAllowed: plan.creditAllowed };
    const serverless = cloudProfile(node.type) === "serverless-function";
    if (serverless) Object.assign(row.technology, { cacheQueries: queries, cacheHits: hits, cacheFallback: fallback });
    const controller = state.controllers?.[node.id], podOverride = controller?.instances.some((p: { overrides: Record<string, number> }) => p.overrides["sql-out"] !== undefined);
    if (plan.manualSql || podOverride || !sql.length) continue;
    const amount = fallback * (serverless ? 1 : config(node).sqlShare);
    row.outputs["sql-out"] = amount;
    for (const edge of sql) {
      const flow = amount / sql.length, edgeFlow: EdgeFlow = state.edges[edge.id];
      if (delayed.has(edge.id)) edgeFlow.nextOffered = flow;
      else {
        edgeFlow.offered = flow;
        const pending = incoming.get(edge.to.nodeId)!.find((f) => f.edge.id === edge.id);
        if (!pending) throw new Error("Missing pending SQL flow");
        pending.amount = flow;
      }
    }
  }
}
