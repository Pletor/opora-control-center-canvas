Router engine toků (`backend/flow/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1). Router je tenký: jen validuje tělo a volá modul pod `registry_lock`. Chyby se mapují takto: 404 neznámé ID, 409 nedovolený přechod, 422 neplatný graf nebo požadavek.

| Metoda a cesta | Co dělá |
|---|---|
| `GET /api/flow/node-types?kind=` | registr typů uzlů s `params` a porty (`name`, `direction`, `kind`, `cardinality`, `schema`) pro editor toků; `kind=page_intent` vrátí katalog záměru stránky |
| `POST /api/flow/node-ports` `{kind, type, params, onError?}` | porty uzlu pro konkrétní `params` (`dynamicPorts`, `onError: errorOutput` = výstup `error`) → `{type, ports}`; editor je volá po změně parametru |
| `POST /api/flow/graph-check` `{kind, graph}` | ověření grafu bez zápisu podle katalogu druhu → `{ok, errors}` (srdce `intent propose --dry-run`) |
| `GET /api/flow/page-intents?project=` | `{pages: [{pageId, state, workflowId?, activeN?, candidateN?, doneCount}]}` pro každou stránku přijatého grafu projektu (`site.kind = page`), `state` ∈ `none` / `pending` / `approved` / `stale` (`backend/flow/page_intents.py`); neznámý projekt 404 |
| `GET /api/flow/workflows?project=&kind=&owner_ref=` | sdílená workflow a workflow projektu, u každého aktivní verze |
| `POST /api/flow/workflows` `{kind, name, project_id?, owner_ref?}` | nové workflow; `page_intent` chce `project_id` a `owner_ref` `opora:page:<nodeId>`, duplicita 409 `owner_taken` |
| `GET /api/flow/workflows/{id}/versions` | verze podle `n` |
| `POST /api/flow/workflows/{id}/versions` `{graph, parent_version_id?}` | nový draft (graf se validuje) |
| `POST /api/flow/versions/{id}/candidate` `{eval_run_id?}` | draft → candidate |
| `POST /api/flow/versions/{id}/activate` | candidate nebo retired → active; `page_intent` 409 `approval_required` |
| `POST /api/flow/versions/{id}/approve` | jen člověk: kandidát záměru stránky → active, log `version.approved` (canvas 2) s `pageDigest` stránky v přijatém grafu |
| `POST /api/flow/versions/{id}/reject` `{reason}` | jen člověk: kandidát záměru stránky → retired, log `version.rejected` s důvodem (canvas 2) |
| `POST /api/flow/workflows/{id}/rollback` | návrat na předchozí verzi |
| `POST /api/flow/versions/{id}/runs` `{payload?, node_id?}` | ruční spuštění; `page_intent` 409 `not_runnable` |
| `GET /api/flow/runs?workflow=&limit=` | seznam běhů |
| `GET /api/flow/runs/{id}` | detail běhu s `node_runs` |
| `GET /api/flow/runs/{id}/log?seq=&limit=` | události logu po `seq` |
| `POST /api/flow/runs/{id}/advance` | navázání přerušeného běhu a pokračování větví timeout po deadline |
| `POST /api/flow/node-runs/{id}/decision` `{decision}` | rozhodnutí schvalovacího uzlu (`approved` / `rejected`), jen člověk v UI |
| `POST /api/flow/log` `{project, canvas: 2\|3\|4, kind, payload}` | vstup logu pláten 2–4 (`backend/flow/canvas_log.py`); `kind` končící `.failed` probudí srdce; člověk, srdce projektu nebo relace brány téhož projektu (`X-Opora-Gate-Token`), jinak 401/403 jako brána |
| `GET /api/flow/stalls` | prostoje s důvodem |

Knihovna pláten toku (`library_routes.py`, `backend/flow/library.py`, kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §3): `GET /api/library?owner=human|agent`, `POST /api/library/folders`, `PATCH`/`DELETE /api/library/folders/{id}`, `POST /api/library/flows {folder, slug, title}`, `GET /api/library/flows/{id}`, `POST …/adopt {project, nodeId?}`, `…/contribute {folder, slug, title}`, `…/promote {folder?}`. Do části `human` píše jen člověk (`require_human`), do části `agent` člověk nebo relace brány (`X-Opora-Gate-Token`, `worker` / `heart`); `promote` jen člověk, `adopt` jde přes zeď brány projektu. Stejné pravidlo části knihovny hlídá `walled` u zápisů verzí plátna knihovny v `/api/flow/*`; `POST /api/flow/workflows` plátno knihovny bez projektu nezaloží (422). Výjimka K3 (§5, `heart_proposal`): draft do části `human` smí jako návrh uložit i srdce (token role `heart` kteréhokoli projektu), verze nese `meta.proposedBy`; `note` a `learnedFrom` z těla draftu jdou do `meta` verze; draft plátna toku zamítá člověk `POST /api/flow/versions/{id}/reject`.

409 se strojovým důvodem vrací `{error, code}`, ostatní 409 `{detail}`. Člověka pozná router podle `request.state.actor == "human"` (relační doklad UI, `backend/app/human_session.py`) jako ostatní akce „jen člověk“ (`require_human`): token srdce nebo dělníka dostane 403, požadavek bez dokladu 428.

Zápisy procházejí middlewarem aplikace: musí mít stejný Origin a `Content-Type: application/json`. U zápisu bez těla stačí poslat `{}`.
