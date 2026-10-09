Kola karty (záložka Historie kol v detailu uzlu, přepínač kol v hlavičce): uzavřená v1 se zamrazí do historie jen ke čtení, v2 začíná načisto podle nového zadání. Server: `backend/editor/agent_memory/card_rounds.py`, kontrakt `docs/karta-pro-agenty.md` → Kola karty.

- `logic/rounds-model.ts` — typy `CardRound` (stav uzlu `round`) a `RoundRecord` (`opora.card-round/1`), přepínač `roundChips` (v1 ✓ · v2 ●), nabídka `roundOffer` (výrazná při ⚠ změně fragmentu) výtah kola `roundDigest` a `roundDecisions` (volby portů, splněná kritéria a rozhodnutí kola; další kolo je nepřebírá); původ rozhodnutí karty `decisionRounds` + `fromRoundLabel` („z v1“).
- `logic/use-decision-rounds.ts` — mapa id rozhodnutí → kolo vzniku pro štítek „z vN“ v Paměti projektu (`ProjectMemoryPanel`); čte kola jen karet v kole ≥ 2.
- `components/RoundsPanel.tsx` — `RoundSwitch`, `OpenRoundOffer` (jen člověk; zapisuje rodič App přes `POST /api/desktop-v3/card-round`), `RoundRecordView` (kolo jen ke čtení) a záložka `RoundsPanel` (čte `GET /api/desktop-v3/card-rounds`).
- Styl `styles/rounds.css` v BEM.
