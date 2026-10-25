// Rozdíl přijatého a pracovního zadání karty pro záložku Zadání: cíl a ne-cíle jako celé texty,
// akceptace karty po řádcích a kroky plánu po jednotlivých ID (stejně jako je slučuje auto-rebase).
// Kroky (`fields.steps`, docs/oporahub-plan-steps.md) jsou volitelné: starší server je nenese a rozdíl
// kroků je pak `null`, ne „beze změny“.
export type PlanStep = { id: string; order: number; title: string; acceptance: string[]; dependsOn: string[]; kind: string | null; files: string[] };
import { harnessChanged } from '@/shared/harness-kit/logic/harness-kit';
export type SpecDoc = { goal: string; non_goals: string; acceptance: string; steps?: unknown; harness?: unknown };
export type TextDiff = { state: "same" | "changed"; before: string; after: string };
export type LineDiff = { kind: "same" | "added" | "removed"; text: string };
export type StepDiff = { id: string; kind: "same" | "added" | "removed" | "changed"; before: PlanStep | null; after: PlanStep | null; changed: string[] };
export type SpecDiffView = { goal: TextDiff; nonGoals: TextDiff; acceptance: LineDiff[]; steps: StepDiff[] | null; changes: number;
  harness?: { before: SpecDoc; after: SpecDoc } };

const texts = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

/** Kroky ze zadání, seřazené podle `order`; `null`, když pole `steps` chybí nebo nemá tvar seznamu. */
export function readSteps(fields: SpecDoc | null | undefined): PlanStep[] | null {
  if (!fields || !Array.isArray(fields.steps)) return null;
  return fields.steps.filter((raw): raw is Record<string, unknown> => !!raw && typeof raw === "object" && typeof (raw as { id?: unknown }).id === "string")
    .map(raw => ({ id: raw.id as string, order: Number.isFinite(raw.order) ? Number(raw.order) : 0, title: typeof raw.title === "string" ? raw.title : "",
      acceptance: texts(raw.acceptance), dependsOn: texts(raw.dependsOn), kind: typeof raw.kind === "string" ? raw.kind : null, files: texts(raw.files) }))
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}

/** Řádky akceptace: bez prázdných řádků a bez odrážek, aby přeformátování nebylo změnou. */
export function acceptanceLines(text: string): string[] {
  return text.split(/\r?\n/).map(line => line.trim().replace(/^([-*•]|\d+[.)])\s+/, "").trim()).filter(Boolean);
}

/** Řádkový rozdíl přes nejdelší společnou podposloupnost; pořadí zachová přijatou verzi. */
export function lineDiff(before: string[], after: string[]): LineDiff[] {
  const n = before.length, m = after.length;
  const table = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    table[i][j] = before[i] === after[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
  const out: LineDiff[] = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (before[i] === after[j]) { out.push({ kind: "same", text: before[i] }); i++; j++; }
    else if (table[i + 1][j] >= table[i][j + 1]) out.push({ kind: "removed", text: before[i++] });
    else out.push({ kind: "added", text: after[j++] });
  }
  while (i < n) out.push({ kind: "removed", text: before[i++] });
  while (j < m) out.push({ kind: "added", text: after[j++] });
  return out;
}

const STEP_FIELDS: (keyof PlanStep)[] = ["title", "order", "acceptance", "dependsOn", "kind", "files"];
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** Kroky po ID: přidaný, odebraný, změněný (s výčtem polí) nebo stejný; pořadí podle pracovní verze. */
export function stepsDiff(accepted: PlanStep[], working: PlanStep[]): StepDiff[] {
  const before = new Map(accepted.map(step => [step.id, step]));
  const rows: StepDiff[] = working.map(step => {
    const old = before.get(step.id) ?? null;
    if (!old) return { id: step.id, kind: "added", before: null, after: step, changed: [] };
    const changed = STEP_FIELDS.filter(key => !same(old[key], step[key])) as string[];
    return { id: step.id, kind: changed.length ? "changed" : "same", before: old, after: step, changed };
  });
  const kept = new Set(working.map(step => step.id));
  for (const step of accepted) if (!kept.has(step.id)) rows.push({ id: step.id, kind: "removed", before: step, after: null, changed: [] });
  return rows;
}

const textDiff = (before: string, after: string): TextDiff => ({ state: before.trim() === after.trim() ? "same" : "changed", before, after });

/** Celý rozdíl; bez přijaté verze je všechno „přidané“ (nová karta), bez pracovní platí přijatá. */
export function specDiff(accepted: SpecDoc | null, working: SpecDoc | null): SpecDiffView {
  const base = accepted ?? { goal: "", non_goals: "", acceptance: "" }, next = working ?? base;
  const goal = textDiff(base.goal, next.goal), nonGoals = textDiff(base.non_goals, next.non_goals);
  const acceptance = lineDiff(acceptanceLines(base.acceptance), acceptanceLines(next.acceptance));
  const acceptedSteps = readSteps(base), workingSteps = readSteps(next);
  const steps = acceptedSteps || workingSteps ? stepsDiff(acceptedSteps ?? [], workingSteps ?? []) : null;
  const changes = Number(goal.state === "changed") + Number(nonGoals.state === "changed")
    + acceptance.filter(line => line.kind !== "same").length + (steps ?? []).filter(row => row.kind !== "same").length
    + Number(harnessChanged(base, next));
  return { goal, nonGoals, acceptance, steps, changes, harness: { before: base, after: next } };
}
