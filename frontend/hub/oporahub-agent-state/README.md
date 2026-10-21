# Stav pro agenty ve frontendu

Jediný zdroj přehledu OporaHubu: `GET /api/oporahub/agent-state` (kontrakt `docs/oporahub-agent-state.md`).

- `logic/agent-state.ts` — drátové typy, přísný parser (jiný scope, chybějící etapa nebo neznámé zdraví se odmítnou), podmíněné čtení s `If-None-Match` (304 = beze změny) a `mirrorJson` pro zrcadlo `script#oh-agent-state`.
- `logic/agent-state-reader.ts` — jeden životní cyklus čtení přes sdílený `createPoller` (10 s po dokončení, jen ve viditelném okně, bez překryvu); hook `use-agent-state.ts` ho jen napojí na React.
- `logic/loop-model.ts`, `strip-model.ts`, `actions-model.ts` — čisté mapování dokumentu na view-model tří pohledů (smyčka, horní pás, fronta akcí). Neznámý strojový důvod se ukáže doslova.
- `logic/review-gate-labels.ts` — české znění důvodů pravidel brány merge (bezpečnostní review, vlastní kontroly, fronta merge, šablona PR) a sloves `review.self_checks` / `pr.update_branch`; test `review-gate-labels.test.ts`.
- `logic/fixtures.ts` — pevný dokument pro testy; `view-model.test.ts` pokrývá mapování, parser, 304 a escapování zrcadla.

Rozhraní popisuje `docs/oporahub-ui.md`.
