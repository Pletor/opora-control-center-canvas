Router engine toků (`backend/flow/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1). Router je tenký: jen validuje tělo a volá modul pod `registry_lock`. Chyby se mapují takto: 404 neznámé ID, 409 nedovolený přechod, 422 neplatný graf nebo požadavek.

| Metoda a cesta | Co dělá |
|---|---|
| `GET /api/flow/node-types?kind=` | registr typů uzlů s `params` a porty (`name`, `direction`, `kind`, `cardinality`, `schema`) pro editor toků; `kind=page_intent` vrátí katalog záměru stránky |
| `GET /api/flow/workflows?project=&kind=&owner_ref=` | sdílená workflow a workflow projektu, u každého aktivní verze |
| `POST /api/flow/workflows` `{kind, name, project_id?, owner_ref?}` | nové workflow; `page_intent` chce `project_id` a `owner_ref` `opora:page:<nodeId>`, duplicita 409 `owner_taken` |
| `GET /api/flow/workflows/{id}/versions` | verze podle `n` |
| `POST /api/flow/workflows/{id}/versions` `{graph, parent_version_id?}` | nový draft (graf se validuje) |
| `POST /api/flow/versions/{id}/candidate` `{eval_run_id?}` | draft → candidate |
| `POST /api/flow/versions/{id}/activate` | candidate nebo retired → active; `page_intent` 409 `approval_required` |
| `POST /api/flow/versions/{id}/approve` | jen člověk: kandidát záměru stránky → active, log `version.approved` (canvas 2) |
| `POST /api/flow/versions/{id}/reject` `{reason}` | jen člověk: kandidát záměru stránky → retired, log `version.rejected` s důvodem (canvas 2) |
| `POST /api/flow/workflows/{id}/rollback` | návrat na předchozí verzi |
| `POST /api/flow/versions/{id}/runs` `{payload?, node_id?}` | ruční spuštění; `page_intent` 409 `not_runnable` |
| `GET /api/flow/runs?workflow=&limit=` | seznam běhů |
| `GET /api/flow/runs/{id}` | detail běhu s `node_runs` |
| `GET /api/flow/runs/{id}/log?seq=&limit=` | události logu po `seq` |
| `POST /api/flow/runs/{id}/advance` | navázání přerušeného běhu a pokračování větví timeout po deadline |
| `POST /api/flow/node-runs/{id}/decision` `{decision, actor?}` | rozhodnutí schvalovacího uzlu (`approved` / `rejected`) |
| `GET /api/flow/stalls` | prostoje s důvodem |

409 se strojovým důvodem vrací `{error, code}`, ostatní 409 `{detail}`. Člověka pozná router podle `request.state.actor == "human"` (relační doklad UI, `backend/app/human_session.py`) jako ostatní akce „jen člověk“ (`require_human`): token srdce nebo dělníka dostane 403, požadavek bez dokladu 428.

Zápisy procházejí middlewarem aplikace: musí mít stejný Origin a `Content-Type: application/json`. U zápisu bez těla stačí poslat `{}`.
