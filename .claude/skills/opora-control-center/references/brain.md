# Brain: registr dovedností a jejich verze

Kdy mě číst: potřebuješ vědět, jaké dovednosti (skilly) OPORA drží, která verze je aktivní a s jakým pinem běží
srdce. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4, kód `backend/brain/`, router
`brain_registry_routes.py` ve složce brain v backend/api. Obojí jen čte; verze se zatím mění jen seedem při startu.

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
