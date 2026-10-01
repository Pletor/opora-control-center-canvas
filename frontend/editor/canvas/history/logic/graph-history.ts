// Historie plátna: krok zpět a krok vpřed nad snímky grafu. Čistý model bez Reactu, bez API a bez
// DOM — App drží jednu historii na scope (projekt + pracovní prostor), před každým uložením do ní
// odloží graf, který na plátně do té chvíle platil, a krok zpět je pak jen obyčejné uložení staršího
// snímku. Server o historii neví nic: rozhodčím zůstává digest, takže cizí změna krok zpět odmítne
// stejně jako každou jinou kolizi.
import type { Graph } from "@/shared/types/logic/types";

/** Kolik kroků zpět si plátno pamatuje. Nejstarší snímek vypadává zespodu, aby paměť nerostla. */
export const HISTORY_LIMIT = 100;

/**
 * `past` jsou snímky před aktuálním grafem (poslední je ten nejbližší, ten se vrátí prvním Ctrl+Z),
 * `future` jsou snímky, které krok zpět odložil stranou a krok vpřed je vrací zpátky.
 */
export type GraphHistory = { past: Graph[]; future: Graph[] };

/** Prázdná historie: nové plátno, jiný projekt i jiný prostor začínají bez kroků. */
export function emptyHistory(): GraphHistory {
  return { past: [], future: [] };
}

/**
 * Jsou to strukturálně tytéž grafy? Levné porovnání tvaru (JSON), nic chytřejšího tu není potřeba:
 * slouží jen k tomu, aby uložení, které nic nezměnilo, nezaložilo prázdný krok zpět.
 */
export function sameGraph(a: Graph, b: Graph): boolean {
  return a === b || JSON.stringify(a) === JSON.stringify(b);
}

/**
 * Odloží `previous` (graf platný před chystanou změnou) na vrchol `past` a zahodí `future` — jakmile
 * uživatel po kroku zpět udělá vlastní změnu, větev dopředu už neplatí. Když je na vrcholu `past`
 * strukturálně tentýž graf, historie se nemění: dvě uložení bez rozdílu nedělají dva kroky.
 */
export function record(history: GraphHistory, previous: Graph): GraphHistory {
  const top = history.past[history.past.length - 1];
  if (top && sameGraph(top, previous)) return history.future.length ? { past: history.past, future: [] } : history;
  const past = [...history.past, previous].slice(-HISTORY_LIMIT);
  return { past, future: [] };
}

/**
 * Krok zpět: vrátí poslední odložený snímek jako `graph` k uložení a historii, ve které `current`
 * (graf na plátně teď) čeká ve `future` na krok vpřed. Prázdná historie vrací `null` — volající pak
 * neukládá vůbec nic.
 */
export function undo(history: GraphHistory, current: Graph): { history: GraphHistory; graph: Graph } | null {
  const graph = history.past[history.past.length - 1];
  if (!graph) return null;
  return {
    graph,
    history: { past: history.past.slice(0, -1), future: [...history.future, current].slice(-HISTORY_LIMIT) },
  };
}

/** Krok vpřed: zrcadlo kroku zpět — poslední snímek z `future` se ukládá, `current` jde do `past`. */
export function redo(history: GraphHistory, current: Graph): { history: GraphHistory; graph: Graph } | null {
  const graph = history.future[history.future.length - 1];
  if (!graph) return null;
  return {
    graph,
    history: { past: [...history.past, current].slice(-HISTORY_LIMIT), future: history.future.slice(0, -1) },
  };
}
