# Stav pro agenty ve frontendu

Jediný zdroj přehledu OporaHubu: `GET /api/oporahub/agent-state` (kontrakt `docs/oporahub-agent-state.md`).

- `logic/agent-state.ts` — drátové typy, přísný parser (jiný scope, chybějící etapa nebo neznámé zdraví se odmítnou), podmíněné čtení s `If-None-Match` (304 = beze změny) a `mirrorJson` pro zrcadlo `script#oh-agent-state`.
- `logic/agent-state-reader.ts` — jeden životní cyklus čtení přes sdílený `createPoller` (10 s po dokončení, jen ve viditelném okně, bez překryvu); hook `use-agent-state.ts` ho jen napojí na React.
- `logic/health-labels.ts` (značka a slovo zdraví, české důvody `reason`), `action-target.ts` (cíl akce podle její cesty) a `actions-model.ts` (fronta akcí) — čisté mapování dokumentu pro drawer karty, tvář karty a záložku Pro agenty. Neznámý strojový důvod se ukáže doslova. Smyčka etap a horní pás (`hub/oporahub-loop`) jsou smazané v PR 6 (docs/navrhy/2026-11-03-novy-zaklad.md §4).
- `logic/review-gate-labels.ts` — české znění důvodů pravidel brány merge (bezpečnostní review, vlastní kontroly, fronta merge, šablona PR) a sloves `review.self_checks` / `pr.update_branch`; test `review-gate-labels.test.ts`.
- `logic/fixtures.ts` — pevný dokument pro testy; `view-model.test.ts` pokrývá mapování, parser, 304 a escapování zrcadla.

Rozhraní popisuje `docs/oporahub-ui.md`.
