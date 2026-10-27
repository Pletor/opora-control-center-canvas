// Krátká historie telemetrie běhu MODELu pro sparkliny inspektoru: posledních 60 ticků každého uzlu a vazby
// (dokončeno za tick, využití, latence, odmítnutí; u vazby přijato a odmítnuto) a souhrn modelu. Zapisuje se jen po
// skutečném kroku, ne po náhledu incidentu, takže graf ukazuje jen vykonané ticky. Hodnoty jsou výpočet modelu.
// Čistá logika bez Reactu.
import type { SimulationState } from "../../model/simulation/logic";

export const HISTORY_TICKS = 60;

export type NodeSample = { tick: number; completed: number; utilization: number; latencyMs: number; rejected: number };
export type EdgeSample = { tick: number; accepted: number; rejected: number };
export type SummarySample = { tick: number; completed: number; offered: number };
export type RunHistory = { nodes: Record<string, NodeSample[]>; edges: Record<string, EdgeSample[]>; summary: SummarySample[] };

export const emptyHistory = (): RunHistory => ({ nodes: {}, edges: {}, summary: [] });

const push = <T>(list: readonly T[] | undefined, item: T): T[] => [...(list ?? []), item].slice(-HISTORY_TICKS);

/** Přidá tick `sim` do historie; uzly a vazby, které v modelu už nejsou, z historie vypadnou. */
export function recordTick(history: RunHistory, sim: SimulationState): RunHistory {
  const tick = sim.tick;
  const nodes: RunHistory["nodes"] = {}, edges: RunHistory["edges"] = {};
  for (const [id, row] of Object.entries(sim.nodes))
    nodes[id] = push(history.nodes[id], { tick, completed: row.completed || 0, utilization: row.utilization || 0, latencyMs: row.latencyMs || 0, rejected: row.rejected || 0 });
  for (const [id, flow] of Object.entries(sim.edges))
    edges[id] = push(history.edges[id], { tick, accepted: flow.accepted || 0, rejected: flow.rejected || 0 });
  const summary = push(history.summary, { tick, completed: sim.summary?.completed ?? 0, offered: sim.summary?.offered ?? 0 });
  return { nodes, edges, summary };
}
