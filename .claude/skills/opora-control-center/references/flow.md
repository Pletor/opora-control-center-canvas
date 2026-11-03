# Engine toků: workflow, verze a běhy

Kdy mě číst: potřebuješ vytvořit, spustit nebo sledovat tok (`kind` `heart`, `page_intent`, `brain_workflow`) nebo
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

| Cesta | Co |
|---|---|
| `/api/flow/node-types` | `GET ?kind=` → `{node_types}` registr typů uzlů: `type`, `version`, `trigger`, `params`, porty (`name`, `direction`, `kind`, `cardinality`, `schema`); `kind=page_intent` vrátí katalog záměru |
| `/api/flow/workflows` | `GET ?project=&kind=&owner_ref=` seznam; `POST {kind, name, project_id?, owner_ref?}` založí tok |
| `/api/flow/workflows/{workflow_id}/versions` | `GET` verze toku; `POST {graph, parent_version_id?}` nový draft (graf se ověřuje, 422) |
| `/api/flow/versions/{version_id}/candidate` | `POST {eval_run_id?}` draft → candidate |
| `/api/flow/versions/{version_id}/activate` | `POST` zpřístupní verzi jako aktivní (`page_intent` → 409 `approval_required`) |
| `/api/flow/versions/{version_id}/approve` | `POST` jen člověk: schválí kandidáta záměru stránky jako aktivní verzi (log `version.approved`, plátno 2) |
| `/api/flow/versions/{version_id}/reject` | `POST {reason}` jen člověk: kandidát záměru → `retired`, důvod do logu `version.rejected` (plátno 2) |
| `/api/flow/workflows/{workflow_id}/rollback` | `POST` vrátí předchozí aktivní verzi |
| `/api/flow/versions/{version_id}/runs` | `POST {payload?, node_id?}` ruční spuštění běhu |
| `/api/flow/runs` | `GET ?workflow=&limit=` seznam běhů |
| `/api/flow/runs/{run_id}` | `GET` detail běhu a jeho uzlů |
| `/api/flow/runs/{run_id}/log` | `GET ?seq=&limit=` → `{events}` záznam běhu od pořadí `seq` |
| `/api/flow/runs/{run_id}/advance` | `POST` navázání: vypršelé čekání pokračuje větví `timeout`, přerušený uzel se spustí znovu |
| `/api/flow/node-runs/{node_run_id}/decision` | `POST {decision: approved\|rejected, actor?}` rozhodnutí schvalovacího uzlu |
| `/api/flow/stalls` | `GET` → `{stalls}` zaseklé běhy |
