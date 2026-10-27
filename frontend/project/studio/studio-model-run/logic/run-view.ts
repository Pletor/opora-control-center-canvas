// Převod stavu simulace na to, co ukazuje plátno a lišta MODELu (prototyp `component-visuals.mjs` – tři stupně karty
// s čísly – přijato, buffer nebo využití, dokončeno; `app.mjs` – souhrn běhu): karta dostane stav, tři čísla stupňů (přijato, buffer nebo využití, dokončeno),
// propustnost, využití, latenci a odmítnutí; vazba přijaté, odmítnuté a chybové odpovědi pro částice; lišta propustnost,
// chybovost a nejvytíženější uzel. Všechno je výpočet modelu, nikdy měření a nikdy zápis do karet OPORY.
// Čistá logika bez Reactu.
import type { SimulationState } from "../../model/simulation/logic";
import type { EditModel } from "../../studio-model/logic/model-edit";

export type CardRun = {
  state: string; stateLabel: string; stages: [string, string, string];
  rps: number; utilization: number; latencyMs: number; errors: number; slow: boolean; failed: boolean;
};
export type LinkFlow = { type: string; accepted: number; rejected: number; response: number; errorResponse: number; latencyMs: number };
export type RunSummary = { throughput: number; offered: number; errorRate: number; backlog: number; busiest: { name: string; utilization: number } | null };

const STATE_LABELS: Readonly<Record<string, string>> = {
  healthy: "v pořádku", failed: "výpadek", idle: "nečinné", stressed: "zátěž", pressured: "tlak", degraded: "zhoršené",
  overloaded: "přetížení", slow: "zpomaleno", open: "rozpojeno", "half-open": "zkouší", recovering: "obnova", unconnected: "nepřipojeno",
};
export const stateLabel = (state: string) => STATE_LABELS[state] ?? state;

const round = (value: number) => Math.round(value * 10) / 10;

/** Karty běhu podle uzlů stavu; uzel bez řádku (běh nezačal) kartu nechá bez čísel. */
export function cardRuns(sim: SimulationState): Map<string, CardRun> {
  const runs = new Map<string, CardRun>();
  for (const [id, row] of Object.entries(sim.nodes)) {
    const utilization = Math.max(0, row.utilization || 0), backlog = row.backlog || 0;
    runs.set(id, {
      state: row.state, stateLabel: stateLabel(row.state),
      stages: [formatNumber(round(row.offered || 0)), backlog ? `${formatNumber(round(backlog))} ve frontě` : formatPercent(Math.min(1, utilization)), formatNumber(round(row.completed || 0))],
      rps: round(row.completed || 0), utilization, latencyMs: Math.round(row.latencyMs || 0), errors: round(row.rejected || 0),
      slow: Boolean(row.slow) || row.state === "slow", failed: row.state === "failed" || row.state === "recovering",
    });
  }
  return runs;
}

/** Toky vazeb pro částice; chybové odpovědi jen u synchronní vazby (přijato, ale nedokončeno po proudu). */
export function linkFlows(sim: SimulationState): Map<string, LinkFlow> {
  const flows = new Map<string, LinkFlow>();
  if (sim.definitionPending) return flows;
  for (const [id, flow] of Object.entries(sim.edges)) {
    const errorResponse = flow.synchronous ? Math.max(0, round(flow.accepted - flow.response)) : 0;
    flows.set(id, { type: flow.type, accepted: flow.accepted || 0, rejected: flow.rejected || 0, response: flow.response || 0, errorResponse, latencyMs: flow.latencyMs || 0 });
  }
  return flows;
}

/** Souhrn modelu: propustnost (dokončeno u zdrojů za tick), chybovost (nedokončený podíl nabídky zdrojů), backlog a
 *  nejvytíženější uzel podle využití. */
export function runSummary(sim: SimulationState, model: EditModel): RunSummary {
  const summary = sim.summary ?? { offered: 0, completed: 0, rejected: 0, backlog: 0, maxLatencyMs: 0 };
  const errorRate = summary.offered > 0 ? Math.min(1, Math.max(0, 1 - summary.completed / summary.offered)) : 0;
  let busiest: RunSummary["busiest"] = null;
  for (const node of model.nodes) {
    const utilization = sim.nodes[node.id]?.utilization ?? 0;
    if (utilization > 0 && (!busiest || utilization > busiest.utilization)) busiest = { name: node.name, utilization };
  }
  return { throughput: summary.completed, offered: summary.offered, errorRate, backlog: summary.backlog, busiest };
}

/** Číslo pro kartu a lištu: česky, nejvýš jedno desetinné místo. */
export const formatNumber = (value: number) => value.toLocaleString("cs-CZ", { maximumFractionDigits: 1 });
export const formatPercent = (ratio: number) => `${Math.round(ratio * 100)} %`;
