import { render } from "@coldtea/pr-lens-renderer";
import { formatIssues, safeParseGraphDoc, type GraphDoc } from "@coldtea/pr-lens-schema";
import type { Atlas, Stage } from "./walkthrough";

// Jediné místo, které sahá na renderer a schéma PR Lens. Importuje ho jen líně načtené plátno,
// takže knihovny (a zod) jsou v samostatném chunku a hlavní bundle nerostou. Spec je nedůvěryhodný:
// nejdřív ho celý ověří schéma (struktura, verze, odkazy), teprve potom se kreslí.
export type Drawn = { svg: string; width: number; height: number; atlas: Atlas };
export type Theme = "light" | "dark";

export function parseSpec(spec: unknown): { doc: GraphDoc; error: "" } | { doc: null; error: string } {
  const parsed = safeParseGraphDoc(spec);
  if (parsed.ok) return { doc: parsed.value, error: "" };
  const issues = parsed.error.issues.slice(0, 5);
  return { doc: null, error: issues.length ? formatIssues(issues) : parsed.error.message };
}

/** Jedno plátno v jednom motivu. Tok bez vlastního pohledu se kreslí z kopie dokumentu jen s tím tokem. */
export function renderStage(doc: GraphDoc, stage: Stage, theme: Theme): Drawn | { error: string } {
  try {
    const source = stage.flow ? { ...doc, flows: doc.flows.filter(flow => flow.id === stage.flow), views: [] } : doc;
    const drawn = render(source, { lens: stage.lens, theme, view: stage.flow ? undefined : stage.view });
    return { svg: drawn.svg, width: drawn.width, height: drawn.height, atlas: drawn.atlas };
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Plátno nejde vykreslit." };
  }
}
