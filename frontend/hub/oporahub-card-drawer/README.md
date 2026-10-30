# Detail karty (jednotný drawer)

Jediný detail karty v aplikaci: drawer zprava se záložkami Zadání · Kroky · Lens · Běh · Review & PR · Historie, nad snímkem `GET /api/oporahub/agent-state` (`cards[]`, `actions[]`) a jednorázovými čteními detailů při otevření. Nahradil inspektor `editor/node-detail` (NodePanel se záložkami) i starý drawer `hub/oporahub-card`.

- Vstup: `open.ts` → `openCardDrawer(nodeId, tab?)`; volá ho odznak etapy na plátně, dvojklik na kartu, Velín, OporaHub i inspektor. Stav drží `logic/card-drawer-store.ts` a zrcadlí ho do URL `?ohCard=<id>&ohTab=spec|steps|lens|run|review|history`.
- `components/CardDrawerHost.tsx` připojí App jednou nad všemi prostředími; `components/CardDrawer.tsx` skládá hlavičku (stavový řádek, sedm dílků definice hotovo v dílku `components/DodBars.tsx`, který s `tiles` jako dlaždice používá i záložka Práce v Detailu prvku), záložky a patičku s jedinou další akcí (`cards[].nextActionId` → `actions[]`).
- `logic/card-dod.ts` — definice hotovo: zdrojem je `cards[].dod` z agent-state (boolean na požadavek + druh brány; dílek **Cesta ověřena** = brána cesty zákazníka, `docs/brana-cesty.md` §5, v popisku jmenuje blokující cesty z `dod.blockingJourneys` přes `blockingJourneysText`); výpočet na klientovi jen pro starší server bez `dod` (starší `dod` bez `journeys` = splněno). `logic/card-header.ts` — stavový řádek a další akce. `logic/use-card-data.ts` — data detailu.
- Nad patičkou dílek `close-card/`: po sloučení PR akce `close_card` → tlačítko **Uzavřít kartu** (zápis `done` dělá App přes `editor.onCloseCard`), nebo česky, co do uzavření chybí.
- Záložky jsou dílky `spec-tab/`, `steps-tab/`, `lens-tab/` (obal prostoru `hub/review-lens`, PR Lens), `run-tab/`, `review-tab/`, `history-tab/`.
- Každý prvek nese `data-oh-*`; celý stav hlavičky je v zrcadle `script#oh-card-drawer`. Kontrakt: `docs/oporahub-ui.md`.
- ✕ vpravo nahoře i Escape detail zavřou a vrátí fokus tam, odkud byl otevřen.
