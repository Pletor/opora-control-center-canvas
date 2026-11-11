// Postup plánu stránky na plátně 2 (docs/navrhy/2026-11-10-platno-2.md): milníky prvku, další přípustný krok a kompletní
// stránka. Vše se odvozuje ze skutečného stavu karty (`card-state`, StudioState), nic se nově neukládá. Bez Reactu, test vedle.
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { StudioState } from "@/project/studio/logic/studio-status";

export type Milestone = { label: "Návrh" | "Realizace" | "Ověření"; step: "done" | "now" | "wait" };

const LABELS = ["Návrh", "Realizace", "Ověření"] as const;
/** Kolik milníků je hotových: plán a díra jsou v Návrhu, stavba v Realizaci, hotovo čeká na Ověření. */
export const DONE_COUNT: Record<StudioState, number> = { plan: 0, hole: 0, building: 1, done: 2, verified: 3 };

/** Návrh → Realizace → Ověření podle tabulky kontraktu; neznámý stav = plán. */
export function elementMilestones(state: StudioState | undefined): Milestone[] {
  const done = DONE_COUNT[state ?? "plan"];
  return LABELS.map((label, index) => ({ label, step: index < done ? "done" : index === done ? "now" : "wait" }));
}

/** Prvky logiky stránky: přímé uzly s druhem `element` pod stránkou, bez podstránek. Starší sektory a komponenty se nepočítají. */
export function pageElements(graph: Graph, pageId: string): CanvasNode[] {
  return graph.nodes.filter((node) => node.parentId === pageId && node.kind === "node" && !!node.element && node.site?.kind !== "page");
}

const stateOf = (states: ReadonlyMap<string, { state: StudioState }>, id: string): StudioState => states.get(id)?.state ?? "plan";
const ready = (state: StudioState) => state === "done" || state === "verified";

/** Stránka je kompletní, když má aspoň jeden prvek a všechny jsou ověřené. */
export function pageComplete(graph: Graph, pageId: string, states: ReadonlyMap<string, { state: StudioState }>): boolean {
  const elements = pageElements(graph, pageId);
  return elements.length > 0 && elements.every((node) => stateOf(states, node.id) === "verified");
}

export type NextStep =
  | { kind: "step"; node: CanvasNode }
  | { kind: "verified" }
  | { kind: "empty" }
  /** Nic není přípustné: `node` = první neověřený prvek, `inputs` = názvy jeho nehotových vstupů. */
  | { kind: "waiting"; node: CanvasNode; inputs: string[] };

/** První neověřený prvek stránky (v pořadí grafu), jehož všechny vstupy `requires` jsou aspoň hotové.
 * Vazba `requires` znamená „zdroj vyžaduje cíl“: vstupy prvku jsou cíle jeho odchozích `requires`. */
export function nextAdmissible(graph: Graph, pageId: string, states: ReadonlyMap<string, { state: StudioState }>): NextStep {
  const elements = pageElements(graph, pageId);
  if (!elements.length) return { kind: "empty" };
  const open = elements.filter((node) => stateOf(states, node.id) !== "verified");
  if (!open.length) return { kind: "verified" };
  const missing = (node: CanvasNode) => graph.edges
    .filter((edge) => edge.relation === "requires" && edge.source === node.id && !ready(stateOf(states, edge.target)))
    .map((edge) => graph.nodes.find((item) => item.id === edge.target)?.name || edge.target);
  const admissible = open.find((node) => !missing(node).length);
  return admissible ? { kind: "step", node: admissible } : { kind: "waiting", node: open[0], inputs: missing(open[0]) };
}
