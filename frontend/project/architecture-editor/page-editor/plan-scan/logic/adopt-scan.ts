// Převzetí návrhu skenu po částech (docs/navrhy/2026-11-10-platno-2.md, Verze 6): Layout, Design (výřezy boxů jako
// inspirace, tokeny do Design systému) a Logika a tok dat (prvky jedním plánem, každému s `flow` plátno logiky s první
// verzí). Každá část běží zvlášť: selhání jedné nezahodí ostatní a výsledek řekne, co se převzalo a co ne. Zápisy dělá
// rodič (`ArchitectureEditor`) přes `AdoptDeps`; tady je jen pořadí a věty. Bez Reactu, test vedle.
import type { FlowGraph } from "@/shared/flow-editor/logic/flow-types";
import { logicFlowTitle } from "@/project/project-flows/logic/project-flows";
import { addInspirationFiles } from "../../../box-detail/logic/box-detail";
import type { PageSection } from "@/shared/types/logic/types";
import type { LayoutSection } from "../../layout-canvas/logic/layout-grid";
import { czechCount } from "../../layout-canvas/logic/czech-count";
import { layoutOfProposal, type ScanLogic, type ScanProposal } from "./page-scan";
import { scanFlowGraph } from "./scan-flow";

export type AdoptParts = { layout: boolean; design: boolean; logic: boolean };
export type AdoptPart = "layout" | "inspiration" | "page" | "tokens" | "logic" | "flows";
export type AdoptResult = { part: AdoptPart; ok: boolean; text: string };
export const ADOPT_LABELS: Record<AdoptPart, string> = { layout: "Layout", inspiration: "Design · výřezy boxů", page: "Design · snímek stránky",
  tokens: "Design · tokeny webu", logic: "Logika", flows: "Tok dat" };

export type AdoptDeps = {
  /** Zámek obsahu (Git main, kompletní stránka): výřezy jako inspirace a logika se nepřevezmou. */
  contentLock: string | null;
  /** Layout návrhu (`POST /api/page-plan` se `scanId`); bez výřezů, jinak by server boxu zapsal `source: "human"`. */
  saveLayout: (sections: LayoutSection[]) => Promise<void>;
  /** Výřezy do současných boxů stránky samostatným zápisem (po layoutu); vrátí, kolik boxů obrázek dostalo. */
  saveInspirations: (files: ReadonlyMap<string, string>) => Promise<number>;
  /** Stáhne snímek skenu a nahraje ho jako obrázek kresby (stejně jako ruční inspirace); vrátí `fileId`. */
  uploadCapture: (name: string) => Promise<string>;
  /** Tokeny návrhu do Design systému projektu; vrátí počet změn a poznámky serveru. */
  saveTokens: (design: Record<string, unknown>) => Promise<{ changes: number; notes: string[] }>;
  /** Prvky logiky jedním plánem; vrátí id uzlu ke každému prvku (podle pořadí), `null` = nenašel se. */
  insertLogic: (logic: ScanLogic[]) => Promise<(string | null)[]>;
  /** Plátno logiky prvku s první verzí; `false` = plátno už verzi mělo a nic se nepřepsalo. */
  createFlow: (nodeId: string, title: string, graph: FlowGraph) => Promise<boolean>;
};

const message = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** Výřez boxu jako první další obrázek jeho inspirace (bez duplicit, nejvýš do limitu). */
export function withCaptureInspiration<T extends PageSection>(sections: readonly T[], files: ReadonlyMap<string, string>): T[] {
  return sections.map((section) => {
    const file = files.get(section.id);
    return file ? { ...section, inspiration: addInspirationFiles(section.inspiration, [file]) } : section;
  });
}

export async function adoptScan(proposal: ScanProposal, parts: AdoptParts, deps: AdoptDeps): Promise<AdoptResult[]> {
  const results: AdoptResult[] = [];
  const done = (part: AdoptPart, text: string) => results.push({ part, ok: true, text });
  const failed = (part: AdoptPart, text: string) => results.push({ part, ok: false, text });
  const crops = Object.entries(proposal.captures?.sections ?? {});
  const shots = new Map<string, string>();
  if (parts.design && crops.length) {
    if (deps.contentLock) failed("inspiration", `Výřezy boxů se nepřevzaly: ${deps.contentLock}`);
    else {
      const lost: string[] = [];
      for (const [id, name] of crops) { try { shots.set(id, await deps.uploadCapture(name)); } catch (cause) { lost.push(message(cause)); } }
      if (lost.length) failed("inspiration", `${czechCount(lost.length, ["výřez se nenahrál", "výřezy se nenahrály", "výřezů se nenahrálo"])}: ${lost[0]}`);
    }
  }
  let layout = false;
  if (parts.layout) {
    try { await deps.saveLayout(layoutOfProposal(proposal.sections)); layout = true;
      done("layout", `Layout převzat: ${czechCount(proposal.sections.length, ["box", "boxy", "boxů"])} jako Návrh.`); }
    catch (cause) { failed("layout", `Layout se nepřevzal: ${message(cause)}`); }
  }
  if (shots.size) {
    try { const count = await deps.saveInspirations(shots);
      done("inspiration", `Výřez ze skenu je inspirací ${czechCount(count, ["boxu", "boxů", "boxů"])}${layout ? "" : " současného layoutu"}.`); }
    catch (cause) { failed("inspiration", `Výřezy boxů se neuložily: ${message(cause)}`); }
  }
  if (parts.design && proposal.captures?.page) failed("page", "Snímek celé stránky zůstává jen v návrhu: stránka zatím nemá vlastní inspiraci.");
  if (parts.design && proposal.design) {
    try { const saved = await deps.saveTokens(proposal.design);
      done("tokens", (saved.changes ? `Design systém: ${czechCount(saved.changes, ["změna", "změny", "změn"])} tokenů.` : "Design systém už tokeny návrhu má.")
        + (saved.notes.length ? ` Server zahodil: ${saved.notes.join("; ")}` : "")); }
    catch (cause) { failed("tokens", `Tokeny se nezapsaly: ${message(cause)}`); }
  }
  if (parts.logic && proposal.logic.length) {
    if (deps.contentLock) failed("logic", `Logika a tok dat se nepřevzaly: ${deps.contentLock}`);
    else await adoptLogic(proposal.logic, deps, done, failed);
  }
  return results;
}

async function adoptLogic(logic: ScanLogic[], deps: AdoptDeps, done: (part: AdoptPart, text: string) => void, failed: (part: AdoptPart, text: string) => void) {
  let ids: (string | null)[];
  try { ids = await deps.insertLogic(logic); done("logic", `Vloženo ${czechCount(logic.length, ["prvek", "prvky", "prvků"])} logiky.`); }
  catch (cause) { failed("logic", `Prvky logiky se nevložily: ${message(cause)}`); return; }
  const flows = logic.flatMap((item, index) => (item.flow && ids[index] ? [{ id: ids[index]!, item, flow: item.flow }] : []));
  if (!flows.length) return;
  let made = 0;
  const lost: string[] = [];
  for (const { id, item, flow } of flows) {
    try { if (await deps.createFlow(id, logicFlowTitle(item.name), scanFlowGraph(flow))) made += 1; }
    catch (cause) { lost.push(`${item.name}: ${message(cause)}`); }
  }
  const text = `Plátno logiky s tokem dat má ${czechCount(made, ["prvek", "prvky", "prvků"])}.`;
  if (lost.length) failed("flows", `${text} Nezaložilo se ${lost.length}: ${lost[0]}`); else done("flows", text);
}
