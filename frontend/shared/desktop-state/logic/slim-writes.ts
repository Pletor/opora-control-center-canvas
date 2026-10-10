// Štíhlé odpovědi zápisů (karta P3): POST /api/desktop-v3/rule, /decision a /pipeline nevrací celý
// stav (~700 kB), jen novou revizi a změněnou položku. Klient ji vloží do stavu, ze kterého zápis
// vyšel, přesně jako server; kdyby mezitím zapsal někdo jiný (revize poskočila o víc než 1) nebo
// zápis změnil graf, stav se znovu načte celý.
import type { CardPipeline } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import type { Decision, DesktopState, Rule } from "@/shared/desktop-state/logic/types";

/** Odpověď POST /api/desktop-v3/rule a /decision. */
export type ItemWriteResponse = { revision: number; readOnly: boolean; item: Rule | Decision | null; graphChanged?: boolean };
/** Odpověď POST /api/desktop-v3/pipeline. */
export type PipelineWriteResponse = { revision: number; readOnly: boolean; nodeId: string; stages: CardPipeline; graphChanged?: boolean };

/** Smí klient odpověď vložit do svého stavu? Jen když je to právě tento jeden zápis. */
export function appliesTo(baseRevision: number, response: { revision: number; graphChanged?: boolean }): boolean {
  return !response.graphChanged && response.revision === baseRevision + 1;
}

/**
 * Stav po zápisu položky stejně jako `MemoryItems.apply` na serveru: přidání na konec, úprava
 * na místě, odstranění vyřadí položku. `item` je položka, jak ji server uložil (např. `by`).
 */
export function withItem(state: DesktopState, kind: "rule" | "decision", id: string, item: Rule | Decision | null): DesktopState {
  const key = kind === "rule" ? "rules" : "decisions";
  const items = state[key] as Array<Rule | Decision>;
  const index = items.findIndex((x) => x.id === id);
  let next: Array<Rule | Decision>;
  if (item === null) next = items.filter((x) => x.id !== id);
  else if (index < 0) next = [...items, item];
  else next = items.map((x, i) => (i === index ? item : x));
  return { ...state, [key]: next } as DesktopState;
}

/** Stav po směrování pipeline (`PipelineRouting.apply`): uzel dostane nové etapy; chybějící uzel vznikne jako na serveru. */
export function withStages(state: DesktopState, nodeId: string, stages: CardPipeline): DesktopState {
  const node = state.nodes[nodeId] ?? { phase: "discover", criteria: [], steps: [] };
  return { ...state, nodes: { ...state.nodes, [nodeId]: { ...node, stages } } };
}
