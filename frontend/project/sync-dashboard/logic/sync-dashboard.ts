// Celkový pohled na proces jednoho projektu: co je zelené, co čeká, co blokuje a proč. Čisté funkce
// nad `docs/synchronizace-pravdy.md`, části 5 (stavy a barvy), 8 (verdikt Oracle) a 9 (dashboard
// projektu); žádná síť, žádné ukládání — report i jména rozsahů dostává hotové ten, kdo dílek skládá.
import type { SyncCheck, SyncReport, SyncSignal, SyncVerdict } from "@/shared/desktop-state/logic/types";

/** Jeden řádek dashboardu: rozsah (oblast, sektor, nebo uzel) a jeho verdikt v jedné větě dat. */
export type ScopeRow = {
  id: string;
  kind: "area" | "sector" | "node";
  name: string;
  state: "draft" | "waiting" | "green" | "closed";
  canCommit: boolean;
  canMerge: boolean;
  failed: string[];
  nextStep: string | null;
};

/** Celkový pohled: řádky, jejich součty, echo podle závažnosti a pět nejčastějších typů echa. */
export type DashboardView = {
  rows: ScopeRow[];
  totals: { green: number; waiting: number; draft: number; closed: number };
  bySeverity: { high: number; medium: number; low: number };
  topSignals: { type: string; count: number }[];
  observedAt: string | null;
  gitHead: string | null;
};

// Pořadí, ve kterém dashboard ukazuje rozsahy: nejdřív co čeká na rozhodnutí, potom rozpracované,
// pak zelené, uzavřené úplně dole — uzavřená karta se nehýbe a nikoho nezajímá jako první.
const STATE_ORDER: Record<ScopeRow["state"], number> = { waiting: 0, draft: 1, green: 2, closed: 3 };

function scopeRow(verdict: SyncVerdict, names: Record<string, string>): ScopeRow {
  const id = verdict.scope.id;
  return {
    id,
    kind: verdict.scope.kind,
    name: names[id] ?? id,
    state: verdict.state,
    canCommit: verdict.canCommit,
    canMerge: verdict.canMerge,
    failed: verdict.checks.filter((check: SyncCheck) => !check.passed).map((check) => check.name),
    nextStep: verdict.nextSteps[0] ?? null,
  };
}

function countStates(rows: ScopeRow[]): DashboardView["totals"] {
  const totals = { green: 0, waiting: 0, draft: 0, closed: 0 };
  for (const row of rows) totals[row.state] += 1;
  return totals;
}

function countSeverities(signals: SyncSignal[]): DashboardView["bySeverity"] {
  const counts = { high: 0, medium: 0, low: 0 };
  for (const signal of signals) counts[signal.severity] += 1;
  return counts;
}

/** Pět nejčastějších typů echa, sestupně podle počtu; při shodě rozhoduje název typu znak po znaku
 * (ne `localeCompare` — typy echa jsou technické slug řetězce, jazyková kolace by je řadila jinak,
 * než by čekal, kdo si je čte znak po znaku). */
function topSignalTypes(signals: SyncSignal[]): { type: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const signal of signals) counts.set(signal.type, (counts.get(signal.type) ?? 0) + 1);
  return [...counts.entries()]
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count || (a.type < b.type ? -1 : a.type > b.type ? 1 : 0))
    .slice(0, 5);
}

/** Celkový pohled na proces z hotového reportu; `null`, když report ještě nedorazil. */
export function dashboardView(report: SyncReport | null, names: Record<string, string>): DashboardView | null {
  if (!report) return null;
  const rows = report.verdicts
    .map((verdict) => scopeRow(verdict, names))
    .sort((a, b) => STATE_ORDER[a.state] - STATE_ORDER[b.state] || a.name.localeCompare(b.name));
  return {
    rows,
    totals: countStates(rows),
    bySeverity: countSeverities(report.signals),
    topSignals: topSignalTypes(report.signals),
    observedAt: report.observedAt || null,
    gitHead: report.gitHead ?? null,
  };
}
