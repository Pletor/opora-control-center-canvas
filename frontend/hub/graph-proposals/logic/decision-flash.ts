// Jednorázový záblesk na řádku historie po rozhodnutí o návrhu: přijatý návrh jednou zeleně pulzne,
// odmítnuté přijetí (server přijetí zamítl) se jednou zatřese. Čistý stav bez Reactu; rodič ho drží
// v useState a po konci animace (nebo dalším výběru/obnově) ho smaže.

export type DecisionOutcome = "accepted" | "refused";
export type DecisionFlash = { id: string; outcome: DecisionOutcome } | null;

/** Nový záblesk pro návrh; bez ID návrhu se nic nezvýrazní. */
export function flashFor(id: string, outcome: DecisionOutcome): DecisionFlash {
  return id ? { id, outcome } : null;
}

/** BEM modifikátor řádku historie, nebo prázdný řetězec, když se řádku záblesk netýká. */
export function flashModifier(flash: DecisionFlash, id: string): string {
  if (!flash || flash.id !== id) return "";
  return flash.outcome === "accepted" ? "graph-proposals__entry--accepted" : "graph-proposals__entry--refused";
}

/** Konec animace na řádku smaže jen jeho vlastní záblesk; cizí řádek stav nemění. */
export function flashEnded(flash: DecisionFlash, id: string): DecisionFlash {
  return flash && flash.id === id ? null : flash;
}
