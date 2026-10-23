// Zbytek zrušených kol karty (rozhodnutí vlastníka 23. 10.): server kola neotevírá ani nezamrazuje,
// historii pokusů nese `resultHistory` v node-brief. Číslo kola ještě čte model karty
// (`editor/canvas/node-card/logic/card-model.ts`); po jeho úpravě tento soubor zmizí.

/** Dřívější stav uzlu `round` (chybí = kolo 1); server ho už nepřijímá. */
export type CardRound = { number: number; openedAt: string; by: string; reason: string };

export function roundNumber(round: CardRound | undefined | null): number {
  return round?.number ?? 1;
}
