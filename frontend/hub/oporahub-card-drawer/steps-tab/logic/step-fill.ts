import type { StepRow } from "./step-status";

// Výplň lišty postupu: podíl hotových kroků a závažnost z reálných stavů kroků. Čistá data, barvu vybírá CSS.
export type FillSeverity = "normal" | "warn" | "error";
export type StepFill = { ratio: number; percent: number; severity: FillSeverity };

/** Selhaný krok = chyba, přeskočený = varování (plán se obešel), jinak běžná modrá. Hotové = done + skipped (jako `stepProgress`). */
export function stepFill(rows: Pick<StepRow, "status">[]): StepFill {
  const total = rows.length;
  const done = rows.filter((row) => row.status === "done" || row.status === "skipped").length;
  const ratio = total ? done / total : 0;
  const severity: FillSeverity = rows.some((row) => row.status === "failed") ? "error"
    : rows.some((row) => row.status === "skipped") ? "warn" : "normal";
  return { ratio, percent: Math.round(ratio * 100), severity };
}
