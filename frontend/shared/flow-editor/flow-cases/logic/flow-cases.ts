// Případy plátna procesů (kontrakt `docs/navrhy/2026-11-04-platno-procesu.md` §3) jako čisté funkce nad grafem:
// přidat, upravit, smazat, převést formulář na případ (JSON pole se kontrolují, než se cokoli uloží) a stav značky.
import type { FlowCase, FlowGraph } from "../../logic/flow-types";

/** Značka případu: zelená = shoda s `expect`, červená = neshoda, šedá = nespuštěno nebo bez `expect`. */
export type CaseMark = "ok" | "fail" | "idle";
export type CaseResult = { fingerprint: string; ok: boolean | null };

/** Otisk toho, co výsledek ovlivňuje (uzly, hrany, případ); po úpravě se starý výsledek přestane ukazovat. */
export const caseFingerprint = (graph: FlowGraph, flowCase: FlowCase): string => JSON.stringify([graph.nodes, graph.edges, flowCase]);

export function caseMark(result: CaseResult | undefined, fingerprint: string): CaseMark {
  if (!result || result.fingerprint !== fingerprint || result.ok === null) return "idle";
  return result.ok ? "ok" : "fail";
}

export const casesOf = (graph: FlowGraph): FlowCase[] => graph.cases ?? [];

export function addCase(graph: FlowGraph): { graph: FlowGraph; added: FlowCase } {
  const cases = casesOf(graph);
  let n = cases.length + 1;
  while (cases.some((item) => item.id === `case-${n}`)) n++;
  const added: FlowCase = { id: `case-${n}`, name: `Případ ${n}`, start: graph.nodes[0]?.id ?? "", input: {} };
  return { graph: { ...graph, cases: [...cases, added] }, added };
}

export const setCase = (graph: FlowGraph, flowCase: FlowCase): FlowGraph =>
  ({ ...graph, cases: casesOf(graph).map((item) => item.id === flowCase.id ? flowCase : item) });

export const removeCase = (graph: FlowGraph, id: string): FlowGraph => ({ ...graph, cases: casesOf(graph).filter((item) => item.id !== id) });

/** Textová podoba případu ve formuláři: JSON pole jako text, prázdné prostředí a očekávání jako prázdný řetězec. */
export type CaseDraft = { name: string; description: string; start: string; input: string; env: string; expect: string };

const pretty = (value: unknown) => JSON.stringify(value, null, 2);
export const draftOf = (flowCase: FlowCase): CaseDraft => ({
  name: flowCase.name, description: flowCase.description ?? "", start: flowCase.start, input: pretty(flowCase.input ?? {}),
  env: flowCase.env ? pretty(flowCase.env) : "", expect: flowCase.expect ? pretty(flowCase.expect) : "",
});

function json(text: string, label: string, object: boolean): { value?: unknown; error?: string } {
  if (!text.trim()) return { value: undefined };
  try {
    const value = JSON.parse(text);
    if (object && (typeof value !== "object" || value === null || Array.isArray(value))) return { error: `${label}: čekám objekt { … }.` };
    return { value };
  } catch (error) { return { error: `${label}: neplatný JSON (${error instanceof Error ? error.message : String(error)}).` }; }
}

/** Formulář → případ. Neplatný JSON nebo chybějící jméno vrací chybu a nic se neuloží. */
export function caseFromDraft(id: string, draft: CaseDraft): { case: FlowCase } | { error: string } {
  if (!draft.name.trim()) return { error: "Případ potřebuje jméno." };
  if (!draft.start) return { error: "Vyberte start (uzel, kde případ začíná)." };
  const input = json(draft.input, "Vstup", false), env = json(draft.env, "Prostředí", true), expect = json(draft.expect, "Očekávání", true);
  const error = input.error ?? env.error ?? expect.error;
  if (error) return { error };
  const description = draft.description.trim();
  return { case: { id, name: draft.name.trim(), ...(description ? { description } : {}), start: draft.start, input: input.value ?? {},
    ...(env.value ? { env: env.value as FlowCase["env"] } : {}), ...(expect.value ? { expect: expect.value as FlowCase["expect"] } : {}) } };
}
