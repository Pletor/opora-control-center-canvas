// Poloha tečky na trase v čase (0–1). Sdílí ji Studio i přehrávání případů na plátně toku; čistá logika bez DOM.

/** Poloha (0–1) tečky `dot` z `dots` v nekonečném cyklu: tečky jsou rovnoměrně rozložené po trase, pohyb lineární. */
export function loopProgress(time: number, cycle: number, dot: number, dots: number): number {
  return ((((time % cycle) + cycle) % cycle) / cycle + dot / dots) % 1;
}

/** Poloha jednorázové tečky; null = ještě nevyjela nebo už dojela (není vidět). */
export function onceProgress(time: number, start: number, delay: number, duration: number): number | null {
  const elapsed = time - start - delay;
  return elapsed < 0 || elapsed > duration ? null : elapsed / duration;
}
