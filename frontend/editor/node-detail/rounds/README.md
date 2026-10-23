Zbytek zrušených kol karty (rozhodnutí vlastníka 23. 10.; server kola neotevírá ani nezamrazuje, historii pokusů nese `resultHistory` v node-brief).

- `logic/rounds-model.ts` — typ `CardRound` a `roundNumber` (chybí = kolo 1), které ještě čte model karty `editor/canvas/node-card/logic/card-model.ts`; po jeho úpravě složka zmizí.
