# Live Run a skutečné výsledky

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
  curl -s -X POST http://127.0.0.1:8780/api/node-sessions/bind -H "Content-Type: application/json" -H "Origin: http://127.0.0.1:8780" \
    -d '{"project":"PROJECT_ID","workspace":"WORKSPACE_ID","nodeId":"NODE_ID","source":"hermes","sessionId":"REAL_SESSION_ID","role":"orchestrator","title":"Konkrétní úkol"}'
  ```
  Pro Claude použij `"source":"claude"`, `"runId":"LANE_SLUG"`, `"role":"worker"` a
  `"parentSessionId":"REAL_HERMES_ID"`. Zápis vždy ověř GETem `/api/node-sessions`.
- Server používá `OPORA_HERMES_API_URL`, server-side `OPORA_HERMES_API_KEY` a
  `OPORA_NODE_SESSION_LANES_ROOT`. Tajemství nepatří do frontendu ani exportů.
- Po dokončení nebo před přechodem na jiné zadání uzavři **vazbu**, nikoli model:
  `POST /api/node-sessions/BINDING_ID/close` s přesným JSON
  `{ "project": "PROJECT_ID", "workspace": "WORKSPACE_ID", "nodeId": "NODE_ID", "confirmed": true }`.
  Použij stejný Origin a Content-Type application/json; následný GET musí obsahovat
  stejné ID a nenulové `closedAt`. Uzavření uchová bezpečný snímek a další činnost
  session už tomuto uzlu nepřipisuje. Další úkol může získat novou vazbu.
- Layout je pouze pro sledování; zprávy a zastavení stále ovládej přes původní
  Telegram/CLI. Nezobrazuje soukromé vstupy/výstupy nástrojů ani uvažování modelu.

## Dokumentační a návrhové běhy

V Live Run přepni na **Dokumentační běhy**; následující ovládání patří tomuto pohledu.

1. Zachovej project/workspace; otevři **Live Run**.
2. Použij stavový filtr, hledání `Hledat v bězích a ticketech` či `Jen vybraný uzel`.
3. Vyber session podle ID a typu. Návrhový běh a dokumentační handoff nejsou
   zaměnitelné ani když mají podobný název.
4. Karty detailu poskytují události, výsledek/důkazy, náklady, paměť/přesný kontext,
   ovládání, tickety a kontextovou osu. Názvy ověř v aktuálním UI.
5. U výsledku rozliš: text návrhu, dokumentační výstup, backendové ověření,
   skutečně uložený soubor. Stažení výstupu není nasazení.
6. **Načíst přesné předané zadání** použij u konkrétního handoffu; porovnej scope/digest.

## Co nelze tvrdit

- Seznam má limit nejvýše 20 návrhových a 20 handoff běhů v tomto API;
  prázdný filtrovaný seznam není důkaz prázdného archivu.
- Nedostupný jeden zdroj neznamená selhání ostatních. Zachované položky mohou být staré.
- Chybějící tokeny, USD či využití kontextu nejsou nula. Žádná vymyšlená procenta.
- V doloženém UI jsou **Upravit pokyn**, **Pokračovat**, **Compact nyní** a boční
  `/btw` neaktivní kvůli chybějícímu transportu. Neobcházej disabled tlačítka
  a nepiš, že byl pokyn odeslán.
- **Dohled běhů** je pokročilý přehled; návrat do hlavního Live Run není restart session.

## Zastavení

Jen na konkrétní uživatelův požadavek vyber správný aktivní run, **Zastavit tento běh**
a **Potvrdit zastavení**. Stav `stopping` znamená vyžádáno, ne ukončeno.
Načti opět stejné ID a ověř terminální stav. Nezastavuj celý server ani všechny agenty.

## Tickety

Ticket váže problém na skutečný nodeId/sessionId. Priority low/normal/high;
stavy open/doing/done. Nevyplňuj náhodné session ID. Celoprojektový ticket
nemusí mít konkrétní session. Autorství `human` nebo `agent` musí odpovídat
skutečnému původu. Stav done není automaticky ověřená oprava.
