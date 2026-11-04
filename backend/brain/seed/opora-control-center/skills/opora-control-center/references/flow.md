# Engine toků: workflow, verze a běhy

Kdy mě číst: potřebuješ vytvořit, spustit nebo sledovat tok (`kind` `heart`, `page_intent`, `library_flow`) nebo
rozhodnout schválení uzlu. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1, kód `backend/flow/`,
router `flow_routes.py` ve složce flow v backend/api. Chyby: 404 neznámé ID, 409 nedovolený přechod, 422 neplatný graf.

Typ uzlu `critic` (ChatGPT kritik přes `codex exec` pod předplatným, `backend/flow/critic.py`): vstup
`{subject, criteria: [str], context?}` (chybějící klíče doplní `params` uzlu), výstup portem `main`
`{verdict: ok|concerns|reject, findings: [{severity: high|medium|low, text}], raw?}`. Běží mimo zámek (`detached`),
codex `read-only` s obsahem v promptu, limit `OPORA_CRITIC_TIMEOUT` (300 s). Chybějící codex, chyba nebo výstup bez
JSON dají `verdict: concerns`, uzel neselže. Srdce v1 ho nepoužívá; do pipeline srdce jde až přes eval.

Typ uzlu `brain_eval` (eval gate Brainu, `backend/brain/evaluate.py`, viz `brain.md`): vstup `{versionId}` (nebo
`params.versionId`), výstup portem `main` `{score, baselineScore, passed}`. Běží mimo zámek (`detached`), pustí
`claude plugin eval` na kandidáta i baseline a zapíše běh evalu; cenu hlásí jako `cost_usd` uzlu. Neúspěšný eval (chybí
claude, strop ceny) vrátí `passed: false`; verze, která není kandidát, uzel ukončí jako `failed`.

Verze toku jde `draft` → `candidate` → `active`; vrátit se dá `rollback`em na předchozí aktivní.

Záměr stránky (`kind` `page_intent`, plátno 2, kontrakt `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §2–§3):
workflow patří stránce, `POST /api/flow/workflows` potřebuje `project_id` a `owner_ref` `opora:page:<nodeId>` (jedno
na projekt, druh a vlastníka, jinak 409 `owner_taken`); dohledá se `GET ?project=&kind=page_intent&owner_ref=`.
Katalog uzlů `GET /api/flow/node-types?kind=page_intent` (`intent.entry`, `intent.view`, `intent.action`,
`intent.reaction`, `intent.data`, `intent.done`, `intent.error`; porty `main` a `data`, `params` s popisem). Graf
potřebuje aspoň jeden `intent.entry` a jeden `intent.done`, vazba `main` vede jen mezi porty `main` a `data` jen mezi
porty `data`. Záměr se nespouští (`runs` → 409 `not_runnable`). Srdce uloží draft a navrhne kandidáta, `activate`
vrátí 409 `approval_required`: kandidáta schválí nebo zamítne jen člověk v UI (`approve` / `reject`, jinak 403/428).
Běžící aplikaci proti aktivní verzi ověří `tools/journey_run.py --intent <nodeId>` (plán `intent-plan`, doklad
`intent-runs`, [api.md](api.md)); neprošlý uzel jde do logu `intent.failed` přes stejný vstup jako `POST /api/flow/log`.
Stav záměru každé stránky vrací `GET /api/flow/page-intents?project=`: `none` (bez záměru), `pending` (kandidát čeká),
`approved`, `stale` (stránka, tedy `site.path`, `goal`, `feel` nebo `sections`, se změnila po schválení; otisk
`pageDigest` zapíše schválení do logu). Kontrola mapy to hlásí jako `page.no-intent` a `page.intent-stale`.
Ticket práce smí v `ticket.issue` nést `intent: {workflowVersionId, nodeIds}` (kritéria `intent.done` aktivní verze):
server ověří verzi a uzly a jejich `claim` doplní do `doneCriteria`.

Plátno toku v knihovně (`kind` `library_flow`, kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1–§3,
kód `backend/flow/library.py`, router `library_routes.py`): rozkreslená metoda, funkce nebo princip napříč projekty.
Knihovna má část `human` (píše jen člověk v UI, jinak 403/428) a `agent` (píše srdce i dělník s `X-Opora-Gate-Token`,
bez tokenu 401 `gate_token_invalid`, a člověk). Složka je jedna úroveň, plátno má `owner_ref`
`opora:library:<human|agent>:<slug složky>/<slug>`; verze a graf mění `/api/flow/workflows/{workflow_id}/versions`
(stejná pravidla části knihovny), `activate` bez schválení, plátno se nespouští (`runs` → 409 `not_runnable`).
Katalog `GET /api/flow/node-types?kind=library_flow` (toky dat podle n8n, `category` pro paletu, porty s `required`
a `label`, `dynamicPorts` = porty podle `params`: `ai.vectorStore` `mode` insert/load/retrieve/retrieveAsTool,
`ai.agent` `hasOutputParser`, `flow.switch` `rules`, `flow.merge` `numberInputs`, `ai.chain` `chainType`). Po `main`
teče `Item[] = {json, binary?, pairedItem?}`; sub-uzel (`ai.model`, `ai.memory`, `ai.tool`, `ai.embedding` …) má jen
výstup svého kindu a hrana vede vždy ze sub-uzlu do kořene (`source_port` = `target_port` = `kind`, např. `model`).
Typ nese `layer` (`fe` / `be` / `db` / `infra` / `ai` / `neutral`), `use` („použij, když…“), `avoid` a `intents`
(štítky `input`, `validate`, `compute`, `store`, `call-service`, `show`, `decide`, `repeat`, `trigger`, `notify`, `ai`);
čti je z `node-types`, než typ zvolíš. Kroky procesu (`docs/navrhy/2026-11-04-platno-procesu.md` §1): FE `fe.click`,
`fe.form` (spouštěče), `fe.navigate`, `fe.state`, `fe.show`, `fe.notify`; BE `be.endpoint` (method, path, body,
response), `be.validate` (výstupy `true` / `false`), `be.function`, `be.middleware`, `be.auth`; DB `db.read`,
`db.write`, `db.transaction` (table, columns, where); Infra `infra.api`, `infra.cache`, `infra.queue`, `infra.storage`,
`infra.email`. `action.http` / `action.db` / `action.file` už neexistují. Uzel smí mít `layer` (přepíše vrstvu typu).
Hrana smí mít `via` (`http` / `sql` / `event` / `call` / `render`) a `data` (`{kind: text | number | json | table |
document | vector | file | event, schema?, example?}`); `via` musí sedět na dvojici vrstev (fe→be `http` / `event`,
be→fe `http` / `event` / `render`, be↔db `sql` / `call`, be↔infra `http` / `call` / `event`, fe→infra `http`, stejná
vrstva a `ai` / `neutral` libovolné); hrana fe↔db přímo je chyba, vlož krok BE.
Uzel nese navíc `notes`, `notesInFlow`, `inputSchema`, `outputSchema`, `example`, `mode` (`perItem` / `once`),
`onError` (`stop` / `continue` / `errorOutput` = výstup `error`) a `retry {maxTries, waitMs}`; graf má `notes[]`
(`{id, content, x, y, width, height, color}` rámec za uzly) a `groups[]` (`{id, name, description ≤ 145, nodeIds,
inputSchema?, outputSchema?}`: souvislý řetězec, vstup jen do prvního a výstup jen z posledního uzlu, sub-uzly se svým
kořenem, bez spouštěče). `graph-check` hlásí i nepřipojený povinný port a `$('<id uzlu>')` na neexistující uzel.
Převzetí do projektu (`adopt`) a vylepšení (`contribute`) založí nové plátno s aktivní v1, jejíž `derived_from` je
`{workflowId, versionId}` zdroje; detail ukáže `derivedFrom`, `derived` a `projects`.
Verze plátna toku nese neměnné `meta` (K3, §5): `POST …/versions {graph, parent_version_id?, note?, learnedFrom?}`
zapíše `note` a `learnedFrom {project, card?, result}` (odkud se ho agent naučil; karta knihovny ho ukazuje
z aktivní verze, `result: "verified"` u plátna agenta = navrženo k povýšení). Výjimka z pravidla části: draft do části
`human` smí uložit i srdce (token role `heart` kteréhokoli projektu) jako návrh, verze dostane
`proposedBy {role: "heart", project}`. Kandidáta, aktivaci, návrat i zamítnutí (`POST /api/flow/versions/{id}/reject
{reason}`, draft do `retired`, návrat ho přeskočí) v části člověka dělá jen člověk. Srdce to ovládá nástrojem
`opora_heart.py library show|get|save|propose|nodes` ([srdce.md](srdce.md), kreslení procesu: [proces-na-platne.md](proces-na-platne.md)).

| Cesta | Co |
|---|---|
| `/api/library` | `GET ?owner=human\|agent` → `{owner, folders: [{id, owner, slug, title, description, order, flows: [{id, slug, title, description, activeVersionId, activeN, derivedCount, derivedFrom, learnedFrom}]}]}` |
| `/api/library/folders` | `POST {owner, slug, title, description?, order?}` složka (409 `folder_taken`) |
| `/api/library/folders/{folder_id}` | `PATCH {title?, description?, order?}` (slug se nemění); `DELETE` jen prázdnou (409 `folder_not_empty`) |
| `/api/library/flows` | `POST {folder, slug, title, description?}` založí plátno `library_flow` (409 `owner_taken`) |
| `/api/library/flows/{workflow_id}` | `GET` detail: verze, `derivedFrom`, `derived`, `projects` |
| `/api/library/flows/{workflow_id}/adopt` | `POST {project, nodeId?}` odvozená kopie v projektu (`opora:project-flow:<nodeId\|slug>`, zeď brány projektu; 409 `empty_flow` bez verze) |
| `/api/library/flows/{workflow_id}/contribute` | `POST {folder, slug, title}` kopii (z projektu) uloží do složky jako nový prvek |
| `/api/library/flows/{workflow_id}/promote` | `POST {folder?}` jen člověk: z knihovny agenta do složky člověka (výchozí se stejným slugem) |

| Cesta | Co |
|---|---|
| `/api/flow/node-types` | `GET ?kind=` → `{node_types}` registr typů uzlů: `type`, `version`, `trigger`, `params`, porty (`name`, `direction`, `kind`, `cardinality`, `schema`, `required`, `label`), `category`, `dynamicPorts`; `kind=page_intent` vrátí katalog záměru, `kind=library_flow` toky dat |
| `/api/flow/node-ports` | `POST {kind, type, params, onError?}` → `{type, ports}` porty uzlu pro konkrétní `params` (dynamické typy: režim vektorového úložiště, `hasOutputParser`, větve Switch, vstupy Merge; `onError: errorOutput` přidá výstup `error`); neznámý typ 404 |
| `/api/flow/graph-check` | `POST {kind, graph}` → `{ok, errors}` ověří graf podle katalogu druhu, nic nezapíše |
| `/api/flow/page-intents` | `GET ?project=` → `{pages: [{pageId, state, workflowId?, activeN?, candidateN?, doneCount}]}` stav záměru každé stránky |
| `/api/flow/workflows` | `GET ?project=&kind=&owner_ref=` seznam; `POST {kind, name, project_id?, owner_ref?}` založí tok |
| `/api/flow/workflows/{workflow_id}/versions` | `GET` verze toku; `POST {graph, parent_version_id?, note?, learnedFrom?}` nový draft (graf se ověřuje, 422; `note` a `learnedFrom` jdou do `meta` verze) |
| `/api/flow/versions/{version_id}/candidate` | `POST {eval_run_id?}` draft → candidate |
| `/api/flow/versions/{version_id}/activate` | `POST` zpřístupní verzi jako aktivní (`page_intent` → 409 `approval_required`) |
| `/api/flow/versions/{version_id}/approve` | `POST` jen člověk: schválí kandidáta záměru stránky jako aktivní verzi (log `version.approved`, plátno 2) |
| `/api/flow/versions/{version_id}/reject` | `POST {reason}` jen člověk: kandidát záměru nebo draft plátna toku (návrh srdce) → `retired`, důvod do logu `version.rejected` (plátno 2) |
| `/api/flow/workflows/{workflow_id}/rollback` | `POST` vrátí předchozí aktivní verzi |
| `/api/flow/versions/{version_id}/runs` | `POST {payload?, node_id?}` ruční spuštění běhu |
| `/api/flow/runs` | `GET ?workflow=&limit=` seznam běhů |
| `/api/flow/runs/{run_id}` | `GET` detail běhu a jeho uzlů |
| `/api/flow/runs/{run_id}/log` | `GET ?seq=&limit=` → `{events}` záznam běhu od pořadí `seq` |
| `/api/flow/runs/{run_id}/advance` | `POST` navázání: vypršelé čekání pokračuje větví `timeout`, přerušený uzel se spustí znovu |
| `/api/flow/node-runs/{node_run_id}/decision` | `POST {decision: approved\|rejected}` rozhodnutí schvalovacího uzlu, jen člověk v UI |
| `/api/flow/log` | `POST {project, canvas: 2\|3\|4, kind, payload}` → `{seq, canvas, kind}` vstup logu pláten 2–4 (`flow_log_events` bez běhu, payload doplní `project` a `author`); `kind` končící `.failed` zapíše do outboxu `canvas.failed` a probudí srdce; píše člověk, srdce projektu nebo relace brány téhož projektu (`X-Opora-Gate-Token`, dělník i srdce), jinak 401/403 jako brána; 404 neznámý projekt, 422 tvar |
| `/api/flow/stalls` | `GET` → `{stalls}` zaseklé běhy |
