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
  agentovi vrátí 403 a neznámému 428 (`HumanRequired`). Výjimka: v projektu se zapnutou plnou
  autonomií agentů je agent smí také; původce zůstává agent (docs/plna-autonomie-agenta.md).
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
| `node_ids` | JSON pole ID dotčených karet (nejvýš 200): z těla (`nodeId`, `node`, `sectorId`) a u zápisů, které mění karty, i ze stopy karty (níže) |
| `status` | HTTP status odpovědi |
| `summary` | krátký popis: na začátku čitelný popisek a ` \| ` (jen u zápisů se stopou karty), pak klíče těla, druh operace (`op.kind`), návrh uzavření (`done.proposed`); na konci `autonomy=full`, když akce prošla díky plné autonomii |

## Stopa karty

Zápisy, které mění karty, nesou `nodeIds` dotčených uzlů a čitelný popisek (nejvýš 120 znaků, česky,
`backend/canvas/activity_labels.py`, docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md B):

| Zápis | `nodeIds` | Popisek (příklad) |
|---|---|---|
| `POST /api/oporahub/graph-proposals` | `updateNodes`, `removeNodes`, `nodes` s ID, konce vazeb `@id`, nové uzly z odpovědi | „Pořadí 12 karet“, „Členství v oblasti u 3 karet“, „Návrh grafu: +3 karty, −1 vazba“ |
| `POST …/graph-proposals/{id}/accept`, `POST /api/oporahub/changesets/{id}/accept` | uzly z uloženého návrhu | „Přijetí: Pořadí 12 karet“ |
| `POST /api/oporahub/changesets` (`steps`) | `changes[].nodeId` | „Kroky karty: 4 kroky“, „Návrh zadání: 2 karty“ |
| `POST /api/project-architecture` | uzly změněné proti uložené revizi | „Architektura: pořadí 12 stránek“ |
| `POST /api/canvas-plan` | nové uzly (`refs`), bez `dryRun` | „Plán: Přidá 1 sektor, 2 karty …“ |
| `POST /api/brain/tasks` | `nodeId` | „Úkol do fronty: <název>“ |

Co je známo až při zápisu (ID nových uzlů, obsah přijatého návrhu, rozdíl architektury), doplní routa
přes `note` / `note_from`; middleware to přidá k tomu, co dá tělo. Selhání stopy nikdy neshodí zápis.
Jediný převzatý text je název úkolu; ` | ` se v něm i v klíčích těla nahradí `/`, popisek tak nejde podvrhnout.

Obsah textů (zadání, texty karet) se do záznamu nekopíruje; ten má vlastní revize. Selhání
zápisu do záznamu nikdy neshodí samotný požadavek.

## Čtení

`GET /api/activity-log?project=&workspace=&actor=human|agent&nodeId=&agent=&since=&until=&limit=&before=` vrátí
`{entries: [...], nextBefore}`, nejnovější první, `limit` 1–500 (výchozí 100), `before` = `id`
pro další stránku. Bez `actor` vrací obojí. Každý záznam nese i `label` (popisek před ` | `, jinak technický popis). `agent` = přesné jméno agenta (`heart`), `since` / `until` = čas
ISO 8601 (i se `Z`), rozsah včetně krajů; kanál srdce tak čte kroky jedné dávky. Každý záznam nese `autonomy: "full" | null`. V UI: panel „Záznam činnosti“ se záložkami
**Já** a **Agenti**.

`GET /api/activity-log/latest-by-node?project=&workspace=` vrátí `{nodeId: {at, actor, agent, label, path}}`:
poslední úspěšný (2xx) zápis každé karty jedním dotazem pro celé plátno. Prochází nejvýš 2000 nejnovějších
zápisů projektu (a prostoru, je-li zadán) s neprázdnými `nodeIds`; jen čtení, bez změny schématu. Bez `project` 422.
