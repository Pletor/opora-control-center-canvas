# Brain: registr dovedností a jejich verze

Kdy mě číst: potřebuješ vědět, jaké dovednosti (skilly) OPORA drží, která verze je aktivní a s jakým pinem běží
srdce. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4, kód `backend/brain/`, router
`brain_registry_routes.py` ve složce brain v backend/api. Obojí jen čte; verze se zatím mění jen seedem při startu.
Dělník tu stahuje zip pinu ze svého ticketu.

- **Artefakt** má ID `opora:brain:<kind>:<name>` (`kind` ∈ `skill`, `tool`, `workflow`, `subagent`, `connector`)
  a patří pluginu Brainu (`opora-heart`, `ponytail`).
- **Verze** je SHA commitu v gitu Brainu (`<datový kořen>/brain/`, lokální marketplace `opora-brain`), `content_ref`
  je cesta souboru v pluginu (`skills/heart/SKILL.md`). Stav `candidate` / `active` / `retired`, aktivní je právě jedna.
- **Pin** je `opora:brain:<kind>:<name>@<sha12>`. Dávka srdce zapisuje své piny do `brainPins` v záznamu dávky
  (`batches.jsonl`) a do výstupu uzlu `agent.claude` v běhu toku.
- **Piny v ticketu** (`machine.pins`, kód `backend/brain/pins.py`): seznam `{pin, plugin, version (plné SHA), zip}`
  po pluginech. Jeden plugin = jeden zip, i když ticket chce víc jeho skillů. Při `ticket.issue` server sám doplní
  výchozí pin pluginu `ponytail` (aktivní verze `opora:brain:skill:ponytail`), když v Brainu je. Srdce přidá další
  polem `pins` v těle `ticket.issue` (CLI `opora_heart.py task|ticket-issue --pin`): ID artefaktu bez verze = aktivní
  pin, `…@<sha12>` = ta verze, pokud ji registr zná. Neznámé ID nebo dvě verze téhož pluginu je 422 `invalid_payload`.
- **Dělník** stáhne `zip` (`/api/brain-registry/pins/<plugin>@<sha12>.zip`) a předá ho `claude --plugin-dir <zip>`
  (jeden `--plugin-dir` na plugin). Kořen zipu je kořen pluginu (`.claude-plugin/plugin.json`, `skills/<skill>/SKILL.md`).

| Cesta | Co |
|---|---|
| `/api/brain-registry/artifacts` | `GET` → `{artifacts}`: `id`, `kind`, `plugin`, `name`, `project_types`, `active` (aktivní verze s `pin`, nebo `null`) |
| `/api/brain-registry/artifacts/{artifact_id}` | `GET` artefakt a `versions` (nejnovější první, každá s `pin`, `status`, `eval_score`, `baseline_version_id` a `links` na `log_event` / `eval_run` / `canvas_node`); neznámé ID 404 |
| `/api/brain-registry/pins/{plugin}@{sha12}.zip` | `GET` zip verze pluginu (`application/zip`), při prvním stažení ho vytvoří `Store.export` v `<datový kořen>/brain-pins/`; verze, kterou registr nezná, 404. Loopback volně, přes veřejný tunel jen s přístupovým tokenem |
