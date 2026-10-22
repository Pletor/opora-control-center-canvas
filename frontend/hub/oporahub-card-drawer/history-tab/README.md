# Záložka Historie

Časová osa událostí karty z `GET /api/oporahub/events` (API nemá filtr karty, proto stránkování kurzorem a výběr karty na klientovi, strop 10 stránek) s filtrem Vše/Zadání/Běh/Review/Lidé a exportem JSON; pod ní historie přijatých revizí a blame (`hub/oporahub-card-history`). Logika: `logic/card-events.ts` (test vedle).
