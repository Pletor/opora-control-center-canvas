import type { PlanStep } from "../../spec-tab/logic/spec-diff";

// Postup kroků plánu: definice kroků jsou v přijatém zadání, průběh v `stepResults` výsledků běhů
// (docs/oporahub-plan-steps.md). Pro každý krok platí nejnovější hlášení; `current` je první nehotový
// krok v topologickém pořadí, pokud ho agent-state (`cards[].steps.current`) neurčí sám.
export type StepEvidence = { notes: string; checks: string[]; commits: string[] };
export type StepResult = { stepId: string; status: "done" | "failed" | "skipped"; evidence: StepEvidence; at: string; executionId: string };
export type StepStatus = "done" | "failed" | "skipped" | "current" | "waiting";
export type StepRow = PlanStep & { status: StepStatus; isCurrent: boolean; depth: number; result: StepResult | null;
  acceptanceMet: number; blockedBy: string[] };
export type ReceiptLike = { executionId: string; createdAt: string; result: Record<string, unknown> };

const STATUSES = ["done", "failed", "skipped"] as const;
const texts = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

/** Výsledky kroků ze všech potvrzení; novější potvrzení přepíše starší hlášení téhož kroku. */
export function collectStepResults(receipts: ReceiptLike[]): Map<string, StepResult> {
  const latest = new Map<string, StepResult>();
  const ordered = [...receipts].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  for (const receipt of ordered) {
    const raw = receipt.result?.stepResults;
    if (!Array.isArray(raw)) continue;
    for (const item of raw) {
      if (!item || typeof item !== "object") continue;
      const value = item as Record<string, unknown>, evidence = (value.evidence ?? {}) as Record<string, unknown>;
      if (typeof value.stepId !== "string" || !STATUSES.includes(value.status as never)) continue;
      latest.set(value.stepId, { stepId: value.stepId, status: value.status as StepResult["status"], at: receipt.createdAt, executionId: receipt.executionId,
        evidence: { notes: typeof evidence.notes === "string" ? evidence.notes : "", checks: texts(evidence.checks), commits: texts(evidence.commits) } });
    }
  }
  return latest;
}

/** Hloubka kroku v DAG = nejdelší cesta závislostí; cyklus ani neznámá závislost hloubku nezvýší. */
export function stepDepths(steps: PlanStep[]): Map<string, number> {
  const byId = new Map(steps.map(step => [step.id, step])), depth = new Map<string, number>(), visiting = new Set<string>();
  const visit = (id: string): number => {
    if (depth.has(id)) return depth.get(id)!;
    const step = byId.get(id);
    if (!step || visiting.has(id)) return -1;
    visiting.add(id);
    const value = 1 + Math.max(-1, ...step.dependsOn.map(visit));
    visiting.delete(id); depth.set(id, value);
    return value;
  };
  steps.forEach(step => visit(step.id));
  return depth;
}

const finished = (status: StepStatus) => status === "done" || status === "skipped";

/** Řádky kroků: stav, aktuální krok, hloubka v DAG a co krok ještě blokuje. */
export function stepRows(steps: PlanStep[], results: Map<string, StepResult>, currentId: string | null = null): StepRow[] {
  const depths = stepDepths(steps);
  const base = steps.map(step => ({ step, result: results.get(step.id) ?? null }));
  const statusOf = new Map(base.map(({ step, result }) => [step.id, (result?.status ?? "waiting") as StepStatus]));
  const topo = [...base].sort((a, b) => (depths.get(a.step.id) ?? 0) - (depths.get(b.step.id) ?? 0) || a.step.order - b.step.order);
  const current = currentId && statusOf.has(currentId) ? currentId
    : topo.find(({ step }) => !finished(statusOf.get(step.id)!))?.step.id ?? null;
  return base.map(({ step, result }) => {
    const raw = statusOf.get(step.id)!;
    const status: StepStatus = step.id === current && !finished(raw) && raw !== "failed" ? "current" : raw;
    return { ...step, status, isCurrent: step.id === current, depth: depths.get(step.id) ?? 0, result,
      acceptanceMet: status === "done" ? step.acceptance.length : 0,
      blockedBy: step.dependsOn.filter(id => !finished(statusOf.get(id) ?? "waiting")) };
  });
}

/** Sloupce DAG pro náhled: kroky seskupené podle hloubky. */
export function stepColumns(rows: StepRow[]): StepRow[][] {
  const columns: StepRow[][] = [];
  for (const row of rows) (columns[Math.max(0, row.depth)] ??= []).push(row);
  return columns.filter(Boolean);
}

export function stepProgress(rows: StepRow[]) {
  return { total: rows.length, done: rows.filter(row => row.status === "done" || row.status === "skipped").length,
    current: rows.find(row => row.isCurrent) ?? null };
}
