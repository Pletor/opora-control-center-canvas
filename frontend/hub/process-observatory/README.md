# process-observatory — záložka „Živý proces“ v OporaHubu

Ukazuje, jak skutečná práce právě běží: kancelář (agent-office), Opora a GitHub v jednom toku
([docs/zivy-proces.md](../../../docs/zivy-proces.md)). Návrh: Claude Design „Opora Hub — Živý proces“.
Žádná ukázková data; když nic nepřišlo, pohled to řekne („Zatím žádná událost — kancelář ani Opora nic nehlásí“).

Skládání (rodič `components/ProcessObservatory.tsx`, mountuje ho `oporahub-workspace` jen s otevřenou záložkou):

| Dílek | Co ukazuje |
|---|---|
| `components/SourceHealth.tsx` | čipy Zdroje z `GET /api/oporahub/process-health` (po 15 s přes sdílený poller) a způsob doručení (SSE / polling) |
| `components/BlockersStrip.tsx` | pás blokací: needs.input, CI selhalo, požadované změny, guard, selhání nástroje, blokující zdraví karty |
| `flow-map/` | mapa toku: řádek = karta, 7 fází, značka pracovníka, stopa minulých fází, poslední událost |
| `event-stream/` | proud událostí s filtrem karty a pracovníka a „Pozastavit čtení“ s počítadlem |
| `card-inspector/` | vybraná karta: kdo je na tahu, běh, větev, PR, commit, patro, kontroly, časová osa, „Otevřít detail karty“ (`openCardDrawer`) |

Data: snímek `agent-state` (karty, `lastEventAt`) + sdílený klient toku `editor/live-strip/logic/events-client.ts`
(stejné spojení jako živý pás Editoru; obnova od kurzoru, `gap` → nové čtení agent-state, polling jako pojistka).
Logika bez Reactu: `logic/process-event.ts` (drátový tvar → plochá událost, dedupe podle `eventId`),
`logic/lanes.ts` (řádky, stopa fází, blokace, pořadí), `logic/stream-buffer.ts` (pozastavení, filtr),
`logic/source-health.ts`, `flow-map/logic/marker-motion.ts`, `card-inspector/logic/inspector-model.ts`; testy vedle.

Pohyb: značka se přesune jen při změně fáze (450 ms), `tool.use` jednou pulzuje, `fail` se jednou zatřese;
`prefers-reduced-motion` = skok, statický kroužek, bez třesení. Během hoveru nad mapou se řádky nepřeřazují.
