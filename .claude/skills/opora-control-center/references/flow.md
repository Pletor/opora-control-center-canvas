# Engine toků: workflow, verze a běhy

Kdy mě číst: potřebuješ vytvořit, spustit nebo sledovat tok (`kind` `heart`, `page_intent`, `brain_workflow`) nebo
rozhodnout schválení uzlu. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1, kód `backend/flow/`,
router `flow_routes.py` ve složce flow v backend/api. Chyby: 404 neznámé ID, 409 nedovolený přechod, 422 neplatný graf.

Typ uzlu `critic` (ChatGPT kritik přes `codex exec` pod předplatným, `backend/flow/critic.py`): vstup
`{subject, criteria: [str], context?}` (chybějící klíče doplní `params` uzlu), výstup portem `main`
`{verdict: ok|concerns|reject, findings: [{severity: high|medium|low, text}], raw?}`. Běží mimo zámek (`detached`),
codex `read-only` s obsahem v promptu, limit `OPORA_CRITIC_TIMEOUT` (300 s). Chybějící codex, chyba nebo výstup bez
JSON dají `verdict: concerns`, uzel neselže. Srdce v1 ho nepoužívá; do pipeline srdce jde až přes eval.

Verze toku jde `draft` → `candidate` → `active`; vrátit se dá `rollback`em na předchozí aktivní.

| Cesta | Co |
|---|---|
| `/api/flow/node-types` | `GET` → `{node_types}` registr typů uzlů: `type`, `version`, `trigger`, porty (`name`, `direction`, `kind`, `cardinality`, `schema`) |
| `/api/flow/workflows` | `GET ?project=` seznam; `POST {kind, name, project_id?}` založí tok |
| `/api/flow/workflows/{workflow_id}/versions` | `GET` verze toku; `POST {graph, parent_version_id?}` nový draft (graf se ověřuje, 422) |
| `/api/flow/versions/{version_id}/candidate` | `POST {eval_run_id?}` draft → candidate |
| `/api/flow/versions/{version_id}/activate` | `POST` zpřístupní verzi jako aktivní |
| `/api/flow/workflows/{workflow_id}/rollback` | `POST` vrátí předchozí aktivní verzi |
| `/api/flow/versions/{version_id}/runs` | `POST {payload?, node_id?}` ruční spuštění běhu |
| `/api/flow/runs` | `GET ?workflow=&limit=` seznam běhů |
| `/api/flow/runs/{run_id}` | `GET` detail běhu a jeho uzlů |
| `/api/flow/runs/{run_id}/log` | `GET ?seq=&limit=` → `{events}` záznam běhu od pořadí `seq` |
| `/api/flow/runs/{run_id}/advance` | `POST` navázání: vypršelé čekání pokračuje větví `timeout`, přerušený uzel se spustí znovu |
| `/api/flow/node-runs/{node_run_id}/decision` | `POST {decision: approved\|rejected, actor?}` rozhodnutí schvalovacího uzlu |
| `/api/flow/stalls` | `GET` → `{stalls}` zaseklé běhy |
