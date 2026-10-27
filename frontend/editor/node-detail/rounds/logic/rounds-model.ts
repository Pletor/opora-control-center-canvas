// Zbytek zrušených kol karty (rozhodnutí vlastníka 23. 10.): server kola neotevírá ani nezamrazuje,
// historii pokusů nese `resultHistory` v node-brief. Zbývá jen tvar starého pole `round` ve stavu uzlu
// (`shared/desktop-state/logic/types.ts`); číslo kola už nikdo nečte.

/** Dřívější stav uzlu `round` (chybí = kolo 1); server ho už nepřijímá. */
export type CardRound = { number: number; openedAt: string; by: string; reason: string };
