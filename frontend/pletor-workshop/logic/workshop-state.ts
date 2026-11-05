import type { Measure } from "./workshop-api";

/** Čistý stav dvou editorů Dílny: co je otevřené, co je rozepsané (draft ≠ saved), poslední měření
 *  a přechod čekající na „Zahodit“, když člověk chce jinam a má neuloženou změnu. */

export type SkillDoc = { name: string; path: string; saved: string; draft: string };
export type ToolDoc = { name: string; savedCode: string; code: string; savedCases: string; cases: string };
export type Target = { kind: "skill"; name: string; path: string } | { kind: "tool"; name: string };
export type WorkshopState = { skill: SkillDoc | null; tool: ToolDoc | null; measure: Measure | null; pending: Target | null };

export const EMPTY: WorkshopState = { skill: null, tool: null, measure: null, pending: null };
export const NAME_RE = /^[a-z][a-z0-9-]*$/;

export const skillDirty = (s: WorkshopState) => Boolean(s.skill && s.skill.draft !== s.skill.saved);
export const toolDirty = (s: WorkshopState) => Boolean(s.tool && (s.tool.code !== s.tool.savedCode || s.tool.cases !== s.tool.savedCases));

/** Chce jinam: s neuloženou změnou v tom editoru se přechod jen odloží (`pending`), jinak `go`. */
export function askSwitch(state: WorkshopState, target: Target): { state: WorkshopState; go: boolean } {
  const dirty = target.kind === "skill" ? skillDirty(state) : toolDirty(state);
  return dirty ? { state: { ...state, pending: target }, go: false } : { state: { ...state, pending: null }, go: true };
}

/** „Zahodit“: rozepsané se vrátí na uložené a odložený přechod se vydá k provedení. */
export function discard(state: WorkshopState): { state: WorkshopState; target: Target | null } {
  const { skill, tool, pending } = state;
  const next = {
    ...state, pending: null,
    skill: skill && pending?.kind === "skill" ? { ...skill, draft: skill.saved } : skill,
    tool: tool && pending?.kind === "tool" ? { ...tool, code: tool.savedCode, cases: tool.savedCases } : tool,
  };
  return { state: next, target: pending };
}

export const keep = (state: WorkshopState): WorkshopState => ({ ...state, pending: null });

export const loadedSkill = (state: WorkshopState, name: string, path: string, content: string): WorkshopState =>
  ({ ...state, skill: { name, path, saved: content, draft: content } });
export const editSkill = (state: WorkshopState, draft: string): WorkshopState =>
  (state.skill ? { ...state, skill: { ...state.skill, draft } } : state);
export const savedSkill = (state: WorkshopState, content: string): WorkshopState =>
  (state.skill ? { ...state, skill: { ...state.skill, saved: content } } : state);

export const loadedTool = (state: WorkshopState, name: string, code: string, cases: string): WorkshopState =>
  ({ ...state, measure: null, tool: { name, savedCode: code, code, savedCases: cases, cases } });
export const editTool = (state: WorkshopState, patch: Partial<Pick<ToolDoc, "code" | "cases">>): WorkshopState =>
  (state.tool ? { ...state, tool: { ...state.tool, ...patch } } : state);
export const savedTool = (state: WorkshopState, code: string, cases: string): WorkshopState =>
  (state.tool ? { ...state, tool: { ...state.tool, savedCode: code, savedCases: cases } } : state);
export const measured = (state: WorkshopState, measure: Measure): WorkshopState => ({ ...state, measure });

/** Výchozí soubor skillu: SKILL.md, jinak první ze seznamu. */
export const defaultFile = (files: string[]) => (files.includes("SKILL.md") ? "SKILL.md" : files[0] ?? "SKILL.md");

/** Řádek výsledku měření „3/4 prošlo · 12 ms“; determinismus nese zvlášť štítek. */
export const measureLine = (m: Measure) => `${m.passed}/${m.total} prošlo · ${Math.round(m.durationMs)} ms`;

/** Hodnota z měření jako krátký JSON pro výpis selhání. */
export const asJson = (value: unknown) => (value === undefined ? "—" : JSON.stringify(value));
