# Plátno záměru stránky (plátno 2)

`projectView=intent&page=<nodeId>` na stránce Projekt (kontrakt `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §5). `IntentCanvas` najde workflow `kind=page_intent` stránky (`owner_ref = opora:page:<nodeId>`, `GET /api/flow/workflows?project=&kind=page_intent&owner_ref=`) a ukáže jeho graf ve sdíleném editoru `shared/flow-editor` s katalogem `GET /api/flow/node-types?kind=page_intent`.

- **Úprava** je lokální, dokud ji člověk neuloží jako **nový draft**. Když workflow ještě neexistuje, první uložení ho založí (`POST /api/flow/workflows`). Draft jde **navrhnout ke schválení** (`candidate`).
- **Kandidáta** člověk **schválí** (`POST /api/flow/versions/{id}/approve`, stane se aktivním) nebo **zamítne** s povinným důvodem (`/reject {reason}`). Doklad člověka (cookie `opora_ui`) obstará `api` u každého zápisu sám, jako u ostatních akcí `require_human`.
- `logic/intent-api.ts` (+ test): adresy, výběr workflow podle `kind` a `owner_ref`, založení workflow při prvním uložení, schválení a zamítnutí. `use-intent-data.ts`: workflow, verze a katalog (bez pollování, záměr se nespouští).
- `intent-versions/`: lišta verzí (aktivní, kandidát, rozpracovaný draft), rozdíl zobrazené verze proti aktivní v uzlech (přidané, odebrané, změněné) a akce.
- `intent-entry/`: vstup z karty stránky (`PageCard`) a z formuláře stránky (`PageIntentFields`): tlačítko „Záměr“ s odznakem stavu z `GET /api/flow/page-intents?project=` (`{pages: [{pageId, state, workflowId?, activeN?, candidateN?, doneCount}]}`). Když endpoint chybí (404) nebo selže, odznak se neukáže, tlačítko ano.

Jedno rozhraní pro všechny projekty: plátno nečte druh projektu; druh plátna pozná jen z `kind` workflow.
