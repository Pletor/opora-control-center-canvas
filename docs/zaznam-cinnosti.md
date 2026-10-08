# Záznam činnosti: co udělal člověk a co agent

Každý zápis do aplikace je dohledatelný: kdo (člověk, nebo který agent), kdy, kam (cesta,
projekt, pracovní prostor, karty) a s jakým výsledkem (HTTP status). Záznamy člověka
a agentů se čtou odděleně.

## Kdo je kdo

- **Agent** posílá u každého zápisu hlavičku `X-Opora-Actor: agent; name=<jméno>`
  (skripty skillu `opora_write.py` a `opora_save.py` ji posílají vždy; jméno z `OPORA_AGENT_NAME`,
  výchozí `agent`). Jméno: písmena, číslice, mezera, `._:-()`, nejvýš 80 znaků.
- **Člověk** je jen zápis s relačním dokladem UI: HttpOnly cookie `opora_ui`, kterou vydá
  `GET /api/access/ui-session` výhradně fetchi z prohlížeče (`Sec-Fetch-Site: same-origin`).
  UI si doklad vyzvedne před prvním zápisem a po restartu serveru (428) ho obnoví
  (`backend/app/human_session.py`, upgrade-opora #29).
- **Neznámý** (`unknown`) je zápis bez hlavičky agenta i bez dokladu (curl, cizí skript).
- Lidské akce (potvrzení a otevření uzavření, autonomie, hromadné potvrzení, obnova verze,
  brána/kontroly/vazby sektorů, mazání sektorů a uzavřených karet, pravidla člověka) server
  agentovi vrátí 403 a neznámému 428 (`HumanRequired`).
- Mez: lokální proces se stejným uživatelem OS umí prohlížeč napodobit. Doklad brání opomenutí
  a výchozímu „člověk“, ne úmyslnému padělku hlaviček; ten je vidět jako vědomé obcházení.
- Záznam drží posledních 50 000 řádků (retence, upgrade-opora #41).

## Co se zapisuje

Tabulka `activity_log` v `registry.sqlite` (vlastník `backend/canvas/activity_log.py`).
Jeden řádek na každý požadavek jiný než GET/HEAD na `/api/*`, i když skončil chybou:

| Pole | Obsah |
|---|---|
| `id` | rostoucí číslo |
| `at` | čas ISO 8601 (UTC) |
| `actor` | `human` \| `agent` \| `unknown` |
| `agent` | jméno agenta, u člověka prázdné |
| `method`, `path` | HTTP metoda a cesta |
| `project_id`, `workspace_id` | z těla (`project`, `workspace`) nebo z query; jinak prázdné |
| `node_ids` | JSON pole ID karet z těla (`nodeId`, `node`, `sectorId`) |
| `status` | HTTP status odpovědi |
| `summary` | krátký popis: klíče těla, druh operace (`op.kind`), návrh uzavření (`done.proposed`) |

Obsah textů (zadání, texty karet) se do záznamu nekopíruje; ten má vlastní revize. Selhání
zápisu do záznamu nikdy neshodí samotný požadavek.

## Čtení

`GET /api/activity-log?project=&workspace=&actor=human|agent&nodeId=&limit=&before=` vrátí
`{entries: [...], nextBefore}`, nejnovější první, `limit` 1–500 (výchozí 100), `before` = `id`
pro další stránku. Bez `actor` vrací obojí. V UI: panel „Záznam činnosti“ se záložkami
**Já** a **Agenti**.
