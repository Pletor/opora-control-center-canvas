// Štíhlé odpovědi zápisů (karta P3): POST /api/desktop-v3/rule, /decision a /pipeline nevrací celý
// stav (~700 kB), jen novou revizi a změněnou položku. Klient ji vloží do stavu, ze kterého zápis
// vyšel, přesně jako server; kdyby mezitím zapsal někdo jiný (revize poskočila o víc než 1) nebo
// zápis změnil graf, stav se znovu načte celý. Úprava jedné karty jde přes POST /api/desktop-v3/node
// (oprava 8 v docs/navrhy/2026-10-14-vykon-platna.md): tělo i odpověď nesou jen ten jeden uzel.
import type { CardPipeline } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import type { Decision, DesktopState, NodeWorkflowState, Rule } from "@/shared/desktop-state/logic/types";

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

/** Odpověď POST /api/desktop-v3/node (oprava 8): nová revize a uzel, jak ho server uložil (`null` = stav karty odebrán). */
export type NodeWriteResponse = { revision: number; readOnly: boolean; nodeId: string; node: NodeWorkflowState | null; graphChanged?: boolean };

const same = (a: unknown, b: unknown): boolean => a === b || JSON.stringify(a) === JSON.stringify(b);

/** Co mutace stavu změnila: nic, právě jednu kartu (štíhlý zápis uzlu), nebo něco dalšího (celý stav). */
export type StateChange = { kind: "none" } | { kind: "node"; nodeId: string; node: NodeWorkflowState | null } | { kind: "full" };

/**
 * Změnila mutace stavu právě jednu kartu a nic jiného? Pak stačí štíhlý zápis jednoho uzlu místo
 * celého stavu (na velkém plátně megabajty a 413). Porovnává se nejdřív reference, shodný obsah
 * pod novou referencí se za změnu nepočítá. Víc karet, pravidla, zprávy na vazbách a podobně dají
 * `full` a uloží se celý stav jako dřív; mutace bez jakékoli změny nemusí na server vůbec.
 */
export function stateChange(before: DesktopState, after: DesktopState): StateChange {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]) as Set<keyof DesktopState>;
  for (const key of keys) if (key !== "nodes" && !same(before[key], after[key])) return { kind: "full" };
  if (before.nodes === after.nodes) return { kind: "none" };
  let change: StateChange = { kind: "none" };
  for (const id of new Set([...Object.keys(before.nodes), ...Object.keys(after.nodes)])) {
    const old = before.nodes[id];
    const next = after.nodes[id];
    if (old === next || (old !== undefined && next !== undefined && same(old, next))) continue;
    if (change.kind === "node") return { kind: "full" };
    change = { kind: "node", nodeId: id, node: next ?? null };
  }
  return change;
}

/** Stav po štíhlém zápisu uzlu stejně jako na serveru: uzel nahradí, `null` ho odebere; ostatní karty si drží referenci. */
export function withNode(state: DesktopState, nodeId: string, node: NodeWorkflowState | null): DesktopState {
  const nodes = { ...state.nodes };
  if (node === null) delete nodes[nodeId];
  else nodes[nodeId] = node;
  return { ...state, nodes };
}
