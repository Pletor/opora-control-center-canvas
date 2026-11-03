// Seznam běhů a prostojů srdce jako řádky: čas, stav, verze, spouštěč, doba, cena a příznak prostoje. Filtr
// „jen zobrazená verze“ (n8n filtruje běhy podle verze) a prostoje jen z verzí tohoto workflow.
import type { FlowRun, FlowVersion, RunStatus, Stall } from "@/shared/flow-editor/logic/flow-types";
import { formatCost, formatDuration } from "@/shared/flow-editor/logic/run-overlay";

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  queued: "ve frontě", running: "běží", waiting: "čeká", succeeded: "hotovo", failed: "chyba", cancelled: "zrušeno",
};
export type RunRow = { id: string; when: string; status: RunStatus; statusLabel: string; version: string; trigger: string; facts: string; stalled: boolean };
export type StallRow = { id: string; runId: string; nodeId: string; reason: string; version: string };

const versionName = (versions: readonly FlowVersion[], id: string) => {
  const version = versions.find((item) => item.id === id);
  return version ? `v${version.n}` : "cizí verze";
};

export function timeLabel(iso: string, now = new Date()): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  const sameDay = at.toDateString() === now.toDateString();
  return sameDay ? at.toLocaleTimeString("cs-CZ") : at.toLocaleString("cs-CZ");
}

export function runRows(runs: readonly FlowRun[], versions: readonly FlowVersion[], stalls: readonly Stall[], onlyVersion: string | null, now = new Date()): RunRow[] {
  const stalled = new Set(stalls.map((stall) => stall.run_id));
  return runs.filter((run) => !onlyVersion || run.workflow_version_id === onlyVersion).map((run) => {
    const ms = Date.parse(run.updated_at) - Date.parse(run.created_at);
    const facts = [Number.isFinite(ms) && run.status !== "running" ? formatDuration(Math.max(0, ms)) : "", run.cost_usd ? formatCost(run.cost_usd) : "",
      run.tokens ? `${run.tokens} tok` : ""].filter(Boolean).join(" · ");
    const trigger = [run.trigger?.source, run.trigger?.node_id].filter(Boolean).join(" · ") || "—";
    return { id: run.id, when: timeLabel(run.created_at, now), status: run.status, statusLabel: RUN_STATUS_LABEL[run.status] ?? run.status,
      version: versionName(versions, run.workflow_version_id), trigger, facts, stalled: stalled.has(run.id) };
  });
}

export function stallRows(stalls: readonly Stall[], versions: readonly FlowVersion[]): StallRow[] {
  const own = new Set(versions.map((version) => version.id));
  return stalls.filter((stall) => own.has(stall.workflow_version_id))
    .map((stall) => ({ id: stall.id, runId: stall.run_id, nodeId: stall.node_id, reason: stall.reason, version: versionName(versions, stall.workflow_version_id) }));
}
