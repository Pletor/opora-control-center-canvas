# Brain: registr dovedností a jejich verze

Kdy mě číst: potřebuješ vědět, jaké dovednosti (skilly) OPORA drží, která verze je aktivní a s jakým pinem běží
srdce. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4, kód `backend/brain/`, router
`brain_registry_routes.py` ve složce brain v backend/api. Seed při startu založí první verze; další verze jdou přes
eval gate (`backend/brain/evaluate.py`): kandidát → eval proti baseline → aktivace.

- **Artefakt** má ID `opora:brain:<kind>:<name>` (`kind` ∈ `skill`, `tool`, `workflow`, `subagent`, `connector`)
  a patří pluginu Brainu (`opora-heart`, `ponytail`).
- **Verze** je SHA commitu v gitu Brainu (`<datový kořen>/brain/`, lokální marketplace `opora-brain`), `content_ref`
  je cesta souboru v pluginu (`skills/heart/SKILL.md`). Stav `candidate` / `active` / `retired`, aktivní je právě jedna.
- **Pin** je `opora:brain:<kind>:<name>@<sha12>`. Dávka srdce zapisuje své piny do `brainPins` v záznamu dávky
  (`batches.jsonl`) a do výstupu uzlu `agent.claude` v běhu toku.

| Cesta | Co |
|---|---|
| `/api/brain-registry/artifacts` | `GET` → `{artifacts}`: `id`, `kind`, `plugin`, `name`, `project_types`, `active` (aktivní verze s `pin`, nebo `null`) |
| `/api/brain-registry/artifacts/{artifact_id}` | `GET` artefakt a `versions` (nejnovější první, každá s `pin`, `status`, `eval_score`, `baseline_version_id` a `links` na `log_event` / `eval_run` / `canvas_node`); neznámé ID 404 |
| `/api/brain-registry/artifacts/{artifact_id}/candidates` | `POST {files: {relpath: text}, message}` (člověk v UI nebo token srdce `X-Opora-Gate-Token`) zapíše soubory pluginu do gitu Brainu a vrátí verzi `candidate` s `baseline_version_id` = aktivní verze; změna `evals/` 422 `evals_frozen`, beze změny 422 `no_change`, bez dokladu 401 |
| `/api/brain-registry/versions/{version_id}/evaluate` | `POST` (člověk nebo srdce) založí běh evalu `running` (202) a v pozadí pustí `claude plugin eval` na kandidáta i baseline se stejnou zmrazenou sadou `evals/`; jen kandidát s baseline (409 `not_candidate` / `baseline_missing`), strop ceny `OPORA_BRAIN_EVAL_MAX_USD` (1.0) |
| `/api/brain-registry/eval-runs/{run_id}` | `GET` běh evalu: `status` (`running` / `ok` / `error` / `forced`), `score`, `baseline_score`, `cost_usd`, `passed`, `report` (souhrn obou běhů nebo `error`) |
| `/api/brain-registry/versions/{version_id}/activate` | `POST` (člověk nebo srdce) aktivuje verzi, jen když poslední běh evalu prošel (`ok` a `score` ≥ `baseline_score`), jinak 409 `eval_required`; `{"force": true}` smí jen člověk v UI (jinak 403 `human_required`) a zapíše běh `forced` |
| `/api/brain-registry/artifacts/{artifact_id}/rollback` | `POST` (člověk nebo srdce) vrátí aktivní na předchozí aktivní verzi bez evalu; není-li kam, 409 `no_previous_version` |

Sada evalu skillu je `<plugin>/evals/<případ>/prompt.md` + `graders/*.md` (formát `claude plugin eval`). Kandidát ji
nemění; chybějící `evals/` u pluginu doplní seed commitem bez nové verze. Uzel enginu `brain_eval` (`flow.md`) pouští
stejný eval z workflow.
