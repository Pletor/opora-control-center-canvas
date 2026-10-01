# Live Run: telemetrie sessions a tickety

Live Run pouze **sleduje** skutečné externí sessions (Hermes, Claude lane) a
tickety. Aplikace z něj žádný model nespouští ani nezastavuje.

## Skutečné sessions na konkrétním uzlu

- V detailu uzlu zvol **Sledovat v Live Run ↗**. Výchozí samostatný layout
  **Práce na uzlu** ukazuje orchestrátora, pracovní sessions a bezpečnou aktivitu.
- Čte `GET /api/node-sessions?project=ID&workspace=ID&nodeId=ID`; pro celý prostor
  vynech `nodeId`. Výpis má limit 100 a příznak `truncated`.
- Hermes session se ověřuje přes existující lokální Hermes API, Claude přes
  konkrétní lane artefakty. `running` je ověřený proces, `recent_activity` jen
  nedávná uložená událost. Otevřená konverzace není důkaz běžícího modelu.
- Připojení k uzlu není spuštění modelu. Před prací na výslovně zadaném uzlu
  ověř skutečné session ID a přesný scope, potom zavolej API (stejný Origin, JSON):
  ```bash
  curl -s -X POST http://127.0.0.1:8740/api/node-sessions/bind -H "Content-Type: application/json" -H "Origin: http://127.0.0.1:8740" \
    -d '{"project":"PROJECT_ID","workspace":"WORKSPACE_ID","nodeId":"NODE_ID","source":"hermes","sessionId":"REAL_SESSION_ID","runId":null,"role":"orchestrator","title":"Konkrétní úkol","parentSessionId":null,"confirmed":true}'
  ```
  Payload musí mít přesně těchto deset klíčů; chybějící i navíc = 409. Pro Claude použij
  `"source":"claude"`, `"runId":"LANE_SLUG"` (název lane, povinný), `"role":"worker"` a
  `"parentSessionId":"REAL_HERMES_ID"`. Hermes má vždy `"runId":null`. `parentSessionId`
  je `null` nebo ID jiné session; prázdný řetězec se odmítne. Zápis vždy ověř GETem `/api/node-sessions`.
- Server používá `OPORA_HERMES_API_URL`, server-side `OPORA_HERMES_API_KEY` a
  `OPORA_NODE_SESSION_LANES_ROOT`. Tajemství nepatří do frontendu ani exportů.
- Vazba se přes API neuzavírá (žádný `close` endpoint). Další úkol může získat
  novou vazbu; nepředstírej, že stará session dál pracuje na tomto uzlu.
- Layout je pouze pro sledování; zprávy a zastavení stále ovládej přes původní
  Telegram/CLI. Nezobrazuje soukromé vstupy/výstupy nástrojů ani uvažování modelu.

## Co nelze tvrdit

- Nedostupný jeden zdroj neznamená selhání ostatních. Zachované položky mohou být staré.
- Chybějící tokeny, USD či využití kontextu nejsou nula. Žádná vymyšlená procenta.
- Zavření stránky ani vazby není zastavení modelu; zastavuj pouze ve zdrojovém
  nástroji (Telegram/CLI) a jen jednoznačně vybranou session na uživatelův pokyn.

## Tickety

Ticket váže problém na skutečný nodeId/sessionId. Priority low/normal/high;
stavy open/doing/done. Nevyplňuj náhodné session ID. Celoprojektový ticket
nemusí mít konkrétní session. Autorství `human` nebo `agent` musí odpovídat
skutečnému původu. Stav done není automaticky ověřená oprava. Ticket externího
agenta viz [external-agent.md](external-agent.md).

Tickety se ukládají ve stavu Desktop v3 (`state.tickets`) a čtou se přes API:
`opora_read.py state --project ID --workspace ID --raw`. Zobrazení ticketů v UI
zatím není implementované.
