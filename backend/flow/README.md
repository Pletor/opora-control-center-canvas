# Engine toků

Tenký engine workflow pro plátno 1 (spouští se) a plátno 2 (záměr stránky, nespouští se). Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §2, §3.1 a §5 bod 1–3; záměr stránky `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §2–§3. Katalog uzlů srdce, Srdce v1 a stav srdce (vstupy, stropy, hlídač gitu) jsou v `catalogs/heart/` (vlastní README). Engine je jediná cesta dávek srdce.

- `node_types.py`: registr typů uzlů v kódu (tvar `Port` / `NodeType` je v `node_spec.py`, aby ho katalogy mohly použít bez kruhového importu). Každý typ má porty (`direction`, `kind` ∈ main / model / memory / tool / subagent / approval, `cardinality`, `schema`) a funkci, která uzel vykoná. Typy v tomto PR:
  - `trigger.manual`;
  - `debug.echo` (vrátí vstup);
  - `approval.human` (čeká na člověka do `params.timeout_seconds`, výchozí 24 h; výstupní porty `approved` / `rejected` / `timeout`);
  - `critic` (`critic.py`): ChatGPT kritik přes `codex exec` pod předplatným. Vstup `{subject, criteria, context?}`, výstup `{verdict: ok|concerns|reject, findings: [{severity, text}], raw?}`. Je `detached` (`runtime.detached` katalogu srdce), codex běží `read-only` s posuzovaným obsahem v promptu (sandbox na Windows soubory nečte), limit `OPORA_CRITIC_TIMEOUT` (300 s). Chyba kritika uzel neshodí, dá `verdict: concerns`. Srdce v1 ho nemá, do pipeline srdce jde až přes eval;
  - `brain_eval` (`backend/brain/evaluate.py`): eval gate Brainu. Vstup `{versionId}`, výstup `{score, baselineScore, passed}`, `detached` stejně jako `critic` (`claude plugin eval` na kandidáta a baseline, cena jako `cost_usd`);
  - typy katalogu srdce (`catalogs/heart/nodes.py`).

  `catalog(kind)` vrátí katalog druhu workflow: `library_flow` má katalog toků dat `catalogs/data_flow.py` (typy podle n8n, kroky FE/BE/DB/Infra v `process_layers.py`, `layer` / `use` / `avoid` / `intents` v `guidance.py`, `category` palety, porty s `required` a `label`, porty podle `params` přes `NodeType.dynamic` / `ports_for`, bez funkce), `page_intent` má vlastní `catalogs/page_intent.py` (`intent.entry`, `intent.view`, `intent.action`, `intent.reaction`, `intent.data`, `intent.done`, `intent.error`; porty `main` a `data`, popis parametrů v `params`, bez funkce, protože se nespouští), ostatní druhy tento registr.
- `graph_check.py`: validace grafu. U `library_flow` navíc povinné porty, pole uzlu (`notes`, `notesInFlow`, `inputSchema`, `outputSchema`, `example`, `mode`, `onError`, `retry`), výstup `error` při `onError: errorOutput`, `notes[]`, `groups[]` (pravidla n8n Canvas Groups) a odkazy `$('<id uzlu>')`. Uzly musí mít známý typ, hrany musí vést mezi existujícími porty, kind hrany musí sedět s kindem obou portů a port s `cardinality: one` nese nejvýš jednu hranu. U `page_intent` tak `main` vede jen mezi porty `main`, `data` jen mezi porty `data`, a graf musí mít aspoň jeden `intent.entry` a jeden `intent.done`.
- `workflows.py`: workflow (`kind` heart / page_intent / library_flow, `project_id` null = sdílené) a jeho verze.
  - Verze je neměnná: hlídají to triggery, mění se jen `status` a `eval_run_id`.
  - Přechody jsou draft → candidate → active. Dosavadní aktivní verze jde do `retired`. Na jedno workflow je vždy nejvýš jedna `active` (unikátní index).
  - `rollback` přepne `active` na nejnovější vyřazenou verzi s nižším `n`; zamítnutého kandidáta přeskočí.
  - `owner_ref` je vlastník workflow: `page_intent` ho má povinně (`opora:page:<nodeId>`, s `project_id`), `heart` nikdy. Na `(project_id, kind, owner_ref)` je nejvýš jedno workflow (unikátní index, starší registr ho dostane přes `ensure_flow_owner_ref`). `list_workflows` filtruje podle projektu, druhu a vlastníka.
  - Záměr stránky schvaluje člověk: `activate` vrátí `FlowConflict` s kódem `approval_required`, `approve` udělá z kandidáta aktivní verzi a `reject` ho vyřadí do `retired`. Obojí zapíše do `flow_log_events` událost `version.approved` / `version.rejected` s `canvas = 2`, autorem a u zamítnutí důvodem; schválení nese `pageDigest` (otisk stránky, který spočítá router). Kdo je člověk, hlídá router.
- `library.py`: knihovna pláten toku napříč projekty (`docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1, §3). Složky `flow_library_folders` v části `human` / `agent` (výchozí složky člověka `seed_folders`, jen když část člověka žádnou nemá), plátno = `library_flow` s `owner_ref = opora:library:<část>:<složka>/<slug>`. `adopt` (kopie do projektu, `opora:project-flow:<nodeId|slug>`) a `contribute` (nový prvek v knihovně) založí workflow s aktivní v1, jejíž `derived_from` ukazuje na zdrojovou verzi; `flow_detail` vrací `derivedFrom`, `derived` a `projects`; `promote` přesune plátno agenta ke člověku. Karta plátna nese i `derivedFrom` a `learnedFrom` aktivní verze (neměnné `meta` verze, K3). Kdo smí psát, hlídá router.
- `page_intents.py`: stav záměru stránky (plátno 2 §4–§5), jediné místo, které ho počítá. `status(db, project_id, pages)`
  vrátí pro stránky `[{id, site}]` `{pageId, state, workflowId?, activeN?, candidateN?, doneCount}`, `state` ∈ `none`
  (bez workflow, aktivní verze i kandidáta) / `pending` (kandidát čeká na člověka) / `approved` / `stale` (stránka se
  změnila po schválení). `approve` zapíše do `version.approved` `pageDigest`: sha256 kanonického JSON `site` polí
  `path`, `goal`, `feel`, `sections` (`page_digest`); `stale` = otisk stránky teď ≠ otisk schválení. `doneCount` počítá
  uzly `intent.done` aktivní verze, bez ní kandidáta. `intent_claims` dá rozkladu (`ticket.issue` s `machine.intent`)
  `claim` uzlů `intent.done` aktivní verze projektu, jinak `FlowInvalid`. Čte ho snímek srdce (`ZÁMĚRY STRÁNEK`),
  `map_check` (`page.no-intent`, `page.intent-stale`) a `GET /api/flow/page-intents`.
- `run_log.py`: append-only log `flow_log_events` (`canvas` 1–4) je zdroj pravdy. `append` zapíše událost a ve stejné transakci ji promítne do `flow_runs` / `flow_node_runs`. Tyto tabulky jsou projekce logu. Typy událostí jsou `run.created`, `run.status`, `node.queued`, `node.started`, `node.heartbeat`, `node.waiting`, `node.succeeded` (volitelně s `provider`, `model`, `cost_usd`) a `node.failed`.
- `interpreter.py`: deterministický plánovač.
  - `start_run` vytvoří běh z verze a spouštěče. Záměr stránky se nespouští (`FlowConflict` s kódem `not_runnable`). `advance` vykonává frontu po hranách `main` v pořadí zařazení.
  - Sub-porty (hrany jiné než `main`) se nevykonávají jako kroky. Uzel je dostane v `ctx["config"]`.
  - `idempotency_key` = hash (běh, příčina aktivace, uzel). Opakovaný pokus má stejný klíč a vyšší `attempt`. Stejná aktivace se nezařadí dvakrát.
  - `waiting` nese `waiting_for` a `deadline`. Po deadline pokračuje `advance` portem `timeout`. `decide` uzavře schválení portem `approved` / `rejected`; stejné rozhodnutí podruhé nic nezmění, jiné vrátí 409.
  - Navázání: uzel ve stavu `running` na začátku `advance` je přerušený pokus. Dostane `node.failed` a spustí se znovu jako `attempt + 1`.
  - `pinned_output` uzlu přeskočí jeho funkci a pošle dál připnutá data.
  - Chyba uzlu ukončí běh jako `failed`.
  - Uzel typu `detached` vrátí `{"detach": true}` a zůstane `running`. Práce běží mimo zámek a hlásí se `heartbeat`, pak `finish` nebo `fail`, které běh posunou. Běh má mezitím stav `running`. `advance` takový uzel nechá být, dokud má čerstvý heartbeat. Bez heartbeatu ho prohlásí za přerušený a spustí znovu. Pozdní hlášení přerušeného pokusu se zahodí.
- `canvas_log.py`: vstup logu pláten 2–4 (`POST /api/flow/log`, záměr stránky §6). `log_canvas` zapíše událost do `flow_log_events` bez běhu (payload nese `project` a `author`). Chyba plátna (`kind` končí `.failed`, např. `intent.failed` z ověření záměru `backend/project/architecture/intent_runs.py`) zapíše do outboxu projektu `canvas.failed`; srdce z něj udělá vstup `canvasFailed` (`catalogs/heart/inputs.wake_input`) a probudí se jako u jiných chyb.
- `stalls.py`: `stall_reason` je čistá funkce nad řádkem `node_run`. Prostoj je uzel, který běží bez heartbeatu nebo s heartbeatem starším než 5 min, nebo uzel, který čeká a jeho deadline vypršel. `list_stalls` ji použije na otevřené uzly.

- `scheduler.py`: plánovač na pozadí (vlákno z lifespan aplikace, průchod každé 2 s nebo po `wakeup`). Zavolá `tick()` háčků (`HeartDriver` srdce, když je srdce povolené, viz `catalogs/heart/README.md`). Pak posune běhy z `due_runs`: prostoj podle `list_stalls` (vypršelý deadline, uzel bez heartbeatu) a zařazený uzel, který nikdo nevykonal. Běhy `page_intent` přeskočí. Ruční `POST /api/flow/runs/{id}/advance` zůstává.

## Úložiště: registry.sqlite

Tabulky `flow_*` jsou v `database/schema/flow_schema.py` a připojují se k `REGISTRY_SCHEMA`. Důvody:

- Workflow může být sdílené (`project_id` null). Takové workflow žádnému `project.sqlite` nepatří.
- Srdce i Brain pracují napříč projekty a log přijímá chyby ze všech čtyř pláten.
- Projekt workflow se ověřuje proti `projects` ve stejné databázi.

Zápisy drží `CanvasService.registry_lock`, router ho bere kolem každého volání.

Okamžité uzly běží pod zámkem. Dlouhé uzly (`claude -p`, síť, zámky projektu) jsou `detached`: běží mimo zámek a posílají heartbeat, takže `running` s čerstvým heartbeatem znamená „běží jinde“, ne „přerušeno“.

## Vynecháno

- `input_ref` / `output_ref` drží JSON přímo v řádku, ne odkaz na úložiště.

Router: `backend/api/flow/flow_routes.py`. Testy: `uv run pytest backend/flow backend/api/flow`.
