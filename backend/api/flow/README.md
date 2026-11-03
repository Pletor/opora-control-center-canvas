Router engine toků (`backend/flow/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1). Router je tenký: jen validuje tělo a volá modul pod `registry_lock`. Chyby se mapují takto: 404 neznámé ID, 409 nedovolený přechod, 422 neplatný graf nebo požadavek.

| Metoda a cesta | Co dělá |
|---|---|
| `GET /api/flow/node-types` | registr typů uzlů s porty (`name`, `direction`, `kind`, `cardinality`, `schema`) pro editor toků |
| `GET /api/flow/workflows?project=` | sdílená workflow a workflow projektu, u každého aktivní verze |
| `POST /api/flow/workflows` `{kind, name, project_id?}` | nové workflow |
| `GET /api/flow/workflows/{id}/versions` | verze podle `n` |
| `POST /api/flow/workflows/{id}/versions` `{graph, parent_version_id?}` | nový draft (graf se validuje) |
| `POST /api/flow/versions/{id}/candidate` `{eval_run_id?}` | draft → candidate |
| `POST /api/flow/versions/{id}/activate` | candidate nebo retired → active |
| `POST /api/flow/workflows/{id}/rollback` | návrat na předchozí verzi |
| `POST /api/flow/versions/{id}/runs` `{payload?, node_id?}` | ruční spuštění |
| `GET /api/flow/runs?workflow=&limit=` | seznam běhů |
| `GET /api/flow/runs/{id}` | detail běhu s `node_runs` |
| `GET /api/flow/runs/{id}/log?seq=&limit=` | události logu po `seq` |
| `POST /api/flow/runs/{id}/advance` | navázání přerušeného běhu a pokračování větví timeout po deadline |
| `POST /api/flow/node-runs/{id}/decision` `{decision, actor?}` | rozhodnutí schvalovacího uzlu (`approved` / `rejected`) |
| `GET /api/flow/stalls` | prostoje s důvodem |

Zápisy procházejí middlewarem aplikace: musí mít stejný Origin a `Content-Type: application/json`. U zápisu bez těla stačí poslat `{}`.
