# live-strip

Spodní pás Editoru „Živý proces“: sbalený ukazuje poslední události jedním řádkem, rozbalená Časová osa
kreslí dráhy karet vrstvy (pořadí `topoIndex`) se značkami událostí, pásy pronájmu a heartbeatem a vpravo
seznam posledních událostí. Data: jeden sdílený klient toku `logic/events-client.ts` (`GET /api/oporahub/events`
pro `head` a posledních 200, pak SSE `/events/stream` od kurzoru; po chybě dočtení `/events?since=` a nové
připojení, po opakovaném selhání polling; `gap` → nové čtení agent-state) a snímek agent-state. Nové události
po 400 ms obnoví agent-state (`logic/use-live-events.ts`), takže tváře karet i Velín drží snímek + deltu.
Model drah `logic/live-model.ts` (test vedle). Klik na značku otevře detail karty na patřičné záložce.
