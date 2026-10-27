// Rozvrh jednoho kroku (prototyp `simulation.mjs`, `schedule`): použitelné vazby, pořadí uzlů průchodem do hloubky
// a zpožděné hrany, které uzavírají cyklus (jejich tok dorazí až v dalším kroku). Plus společné konstanty kroku.
import type { CachePlan, Incoming } from "./cache-settlement";
import type { ModelConfig, SimDomain, SimEdge, SimNode, SimulationState } from "./simulation-types";

export const round = (n: number) => Math.round(n * 100) / 100;
export const SOURCES = new Set(["client", "event-producer", "scheduled-job-cron"]);
export const QUEUES = new Set(["queue", "message-broker", "sync-client"]);
export const SYNCHRONOUS = new Set(["http-request", "sql-query", "cache-command", "record-command", "search-query"]);

/** Kapacita obecného uzlu: menší z nastavené propustnosti a souběhu × replik / doby obsluhy (Slow ji zpomalí). */
export const capacity = (c: ModelConfig, replicas: number = c.replicas, slow = 1) => Math.min(c.capacity * replicas / slow, c.concurrency * replicas * 1000 / (c.latencyMs * slow));

/** Vazba nese tok, když je zapnutá a nemá textovou podmínku (kromě `always`); podmínky model nevyhodnocuje. */
export const usable = (edge: SimEdge) => edge.enabled && (!edge.condition || edge.condition.trim() === "always");

export function schedule(domain: SimDomain): { order: string[]; edges: SimEdge[]; delayed: Set<string> } {
  const edges = domain.edges.filter(usable), visited = new Set<string>(), active = new Set<string>(), delayed = new Set<string>(), post: string[] = [];
  const visit = (id: string) => {
    if (visited.has(id)) return;
    active.add(id);
    for (const e of edges.filter((e) => e.from.nodeId === id)) {
      if (active.has(e.to.nodeId)) delayed.add(e.id);
      else visit(e.to.nodeId);
    }
    active.delete(id);
    visited.add(id);
    post.push(id);
  };
  for (const node of domain.nodes) visit(node.id);
  return { order: post.reverse(), edges, delayed };
}

/** Sdílený kontext jednoho kroku pro dopředný, zpětný a souhrnný průchod. */
export type StepContext = {
  domain: SimDomain;
  previous: SimulationState;
  s: SimulationState;
  preview: boolean;
  order: string[];
  edges: SimEdge[];
  delayed: Set<string>;
  plans: CachePlan[];
  byId: Map<string, SimNode>;
  incoming: Incoming;
  emitEvent: (nodeId: string, kind: string, message: string) => void;
};
