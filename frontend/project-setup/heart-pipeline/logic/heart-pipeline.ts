// Souhrn srdce pro stránku projektu: které workflow srdce projekt má, jeho aktivní verze, kolik běhů vidíme a kolik
// uzlů právě stojí. Prostoje (`/api/flow/stalls`) jsou globální, proto se počítají jen ty z verzí tohoto workflow.
import type { FlowRun, FlowVersion, FlowWorkflow, Stall } from "@/shared/flow-editor/logic/flow-types";

/** Strop výpisu běhů v `/api/flow/runs` (`flowUrls.runs`); plný výpis znamená „aspoň tolik“. */
export const RUNS_LIMIT = 50;
export type HeartPipelineSummary = { name: string; scope: string; active: string; runs: string; stalls: number };

export function heartPipelineSummary(workflow: FlowWorkflow | null, versions: readonly FlowVersion[], runs: readonly FlowRun[],
  stalls: readonly Stall[]): HeartPipelineSummary | null {
  if (!workflow) return null;
  const own = new Set(versions.map((version) => version.id));
  const active = versions.find((version) => version.status === "active");
  return {
    name: workflow.name,
    scope: workflow.project_id ? "workflow projektu" : "sdílené workflow",
    active: active ? `v${active.n}` : "bez aktivní verze",
    runs: runs.length >= RUNS_LIMIT ? `${RUNS_LIMIT}+` : String(runs.length),
    stalls: stalls.filter((stall) => own.has(stall.workflow_version_id)).length,
  };
}
