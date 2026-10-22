# Detail karty (jednotný drawer)

Jediný detail karty v aplikaci: drawer zprava se záložkami Zadání · Kroky · Běh · Review & PR · Historie, nad snímkem `GET /api/oporahub/agent-state` (`cards[]`, `actions[]`) a jednorázovými čteními detailů při otevření. Nahradil inspektor `editor/node-detail` (NodePanel se záložkami) i starý drawer `hub/oporahub-card`.

- Vstup: `open.ts` → `openCardDrawer(nodeId, tab?)`; volá ho odznak etapy na plátně, dvojklik na kartu, Velín, OporaHub i inspektor. Stav drží `logic/card-drawer-store.ts` a zrcadlí ho do URL `?ohCard=<id>&ohTab=spec|steps|run|review|history`.
- `components/CardDrawerHost.tsx` připojí App jednou nad všemi prostředími; `components/CardDrawer.tsx` skládá hlavičku (stavový řádek, šest dílků definice hotovo), záložky a patičku s jedinou další akcí (`cards[].nextActionId` → `actions[]`).
- `logic/card-dod.ts` — definice hotovo: přednost má `cards[].dod`, jinak výpočet na klientovi (TODO přepnout na backend). `logic/card-header.ts` — stavový řádek a další akce. `logic/use-card-data.ts` — data detailu.
- Záložky jsou dílky `spec-tab/`, `steps-tab/`, `run-tab/`, `review-tab/`, `history-tab/`.
- Každý prvek nese `data-oh-*`; celý stav hlavičky je v zrcadle `script#oh-card-drawer`. Kontrakt: `docs/oporahub-ui.md`.
- ✕ vpravo nahoře i Escape detail zavřou a vrátí fokus tam, odkud byl otevřen.
