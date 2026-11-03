// Stav běhu na plátně: z `node_runs` vybraného běhu (poslední pokus uzlu vyhrává) a z prostojů (`/api/flow/stalls`)
// vznikne stav každého uzlu a popisek hran (tokeny · cena · doba výstupního uzlu, místo „položek“ v n8n).
import type { FlowEdge, NodeRun, NodeRunStatus, Stall } from "./flow-types";

export type NodeOverlay = {
  status: NodeRunStatus; attempt: number; waitingFor: string | null; deadline: string | null; stall: string | null;
  error: string | null; model: string | null; tokens: number; costUsd: number; durationMs: number | null; nodeRunId: string;
};
export type RunOverlay = ReadonlyMap<string, NodeOverlay>;

export const STATUS_LABEL: Record<NodeRunStatus, string> = {
  queued: "ve frontě", running: "běží", waiting: "čeká", succeeded: "hotovo", failed: "chyba",
};

function duration(run: NodeRun): number | null {
  if (!run.started_at) return null;
  const end = run.ended_at ? Date.parse(run.ended_at) : NaN, start = Date.parse(run.started_at);
  return Number.isFinite(end) && Number.isFinite(start) ? Math.max(0, end - start) : null;
}

export function runOverlay(nodeRuns: readonly NodeRun[], stalls: readonly Stall[] = []): RunOverlay {
  const latest = new Map<string, NodeRun>();
  for (const run of nodeRuns) {
    const seen = latest.get(run.node_id);
    if (!seen || run.attempt >= seen.attempt) latest.set(run.node_id, run);
  }
  const stallOf = new Map(stalls.map((stall) => [stall.id, stall.reason]));
  return new Map([...latest].map(([nodeId, run]) => [nodeId, {
    status: run.status, attempt: run.attempt, waitingFor: run.waiting_for ?? null, deadline: run.deadline ?? null,
    stall: stallOf.get(run.id) ?? null, error: run.error ?? null, model: run.model ?? null,
    tokens: (run.tokens_in ?? 0) + (run.tokens_out ?? 0), costUsd: run.cost_usd ?? 0, durationMs: duration(run), nodeRunId: run.id,
  }]));
}

export function formatTokens(tokens: number): string {
  return tokens >= 1000 ? `${(tokens / 1000).toFixed(1).replace(".", ",")}k tok` : `${tokens} tok`;
}
export function formatCost(usd: number): string {
  return `${usd.toFixed(usd < 0.1 ? 3 : 2).replace(".", ",")} $`;
}
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
  return `${Math.round(ms / 60_000)} min`;
}

/** Popisek hrany z výstupního uzlu; jen hlavní tok, a jen když uzel doběhl. */
export function edgeLabel(edge: FlowEdge, overlay: RunOverlay): string {
  const source = overlay.get(edge.source_node);
  if (edge.kind !== "main" || !source || source.status !== "succeeded") return "";
  const parts = [source.tokens ? formatTokens(source.tokens) : "", source.costUsd ? formatCost(source.costUsd) : "",
    source.durationMs !== null ? formatDuration(source.durationMs) : ""].filter(Boolean);
  return parts.join(" · ");
}
