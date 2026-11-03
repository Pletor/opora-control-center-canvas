# Engine toků

Tenký engine workflow pro plátno 1 (spouští se) a plátno 2 (záměr stránky, nespouští se). Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §2, §3.1 a §5 bod 1. Tento PR obsahuje jen engine. Katalog uzlů srdce přijde v PR 2.

- `node_types.py`: registr typů uzlů v kódu. Každý typ má porty (`direction`, `kind` ∈ main / model / memory / tool / subagent / approval, `cardinality`, `schema`) a funkci, která uzel vykoná. Typy v tomto PR:
  - `trigger.manual`;
  - `debug.echo` (vrátí vstup);
  - `approval.human` (čeká na člověka do `params.timeout_seconds`, výchozí 24 h; výstupní porty `approved` / `rejected` / `timeout`).
- `graph_check.py`: validace grafu. Uzly musí mít známý typ, hrany musí vést mezi existujícími porty, kind hrany musí sedět s kindem obou portů a port s `cardinality: one` nese nejvýš jednu hranu.
- `workflows.py`: workflow (`kind` heart / page_intent / brain_workflow, `project_id` null = sdílené) a jeho verze.
  - Verze je neměnná: hlídají to triggery, mění se jen `status` a `eval_run_id`.
  - Přechody jsou draft → candidate → active. Dosavadní aktivní verze jde do `retired`. Na jedno workflow je vždy nejvýš jedna `active` (unikátní index).
  - `rollback` přepne `active` na nejnovější vyřazenou verzi s nižším `n`.
- `run_log.py`: append-only log `flow_log_events` (`canvas` 1–4) je zdroj pravdy. `append` zapíše událost a ve stejné transakci ji promítne do `flow_runs` / `flow_node_runs`. Tyto tabulky jsou projekce logu. Typy událostí jsou `run.created`, `run.status`, `node.queued`, `node.started`, `node.waiting`, `node.succeeded` a `node.failed`.
- `interpreter.py`: deterministický plánovač.
  - `start_run` vytvoří běh z verze a spouštěče. `advance` vykonává frontu po hranách `main` v pořadí zařazení.
  - Sub-porty (hrany jiné než `main`) se nevykonávají jako kroky. Uzel je dostane v `ctx["config"]`.
  - `idempotency_key` = hash (běh, příčina aktivace, uzel). Opakovaný pokus má stejný klíč a vyšší `attempt`. Stejná aktivace se nezařadí dvakrát.
  - `waiting` nese `waiting_for` a `deadline`. Po deadline pokračuje `advance` portem `timeout`. `decide` uzavře schválení portem `approved` / `rejected`; stejné rozhodnutí podruhé nic nezmění, jiné vrátí 409.
  - Navázání: uzel ve stavu `running` na začátku `advance` je přerušený pokus. Dostane `node.failed` a spustí se znovu jako `attempt + 1`.
  - `pinned_output` uzlu přeskočí jeho funkci a pošle dál připnutá data.
  - Chyba uzlu ukončí běh jako `failed`.
- `stalls.py`: `stall_reason` je čistá funkce nad řádkem `node_run`. Prostoj je uzel, který běží bez heartbeatu nebo s heartbeatem starším než 5 min, nebo uzel, který čeká a jeho deadline vypršel. `list_stalls` ji použije na otevřené uzly.

## Úložiště: registry.sqlite

Tabulky `flow_*` jsou v `database/schema/flow_schema.py` a připojují se k `REGISTRY_SCHEMA`. Důvody:

- Workflow může být sdílené (`project_id` null). Takové workflow žádnému `project.sqlite` nepatří.
- Srdce i Brain pracují napříč projekty a log přijímá chyby ze všech čtyř pláten.
- Projekt workflow se ověřuje proti `projects` ve stejné databázi.

Zápisy drží `CanvasService.registry_lock`, router ho bere kolem každého volání.

Uzly v tomto PR jsou okamžité. Dlouhé uzly z PR 2 (`claude -p`) musí běžet mimo zámek a posílat heartbeat. Teprve potom může `running` znamenat „běží jinde“, a ne „přerušeno“.

## Vynecháno

- Katalog srdce a uzel `agent` (PR 2).
- Plánovač na pozadí: timeouty a navázání dnes posouvá `POST /api/flow/runs/{id}/advance`.
- Zápis chyb z pláten 2–4 přes API: tabulka i `append` je unesou, endpoint zatím chybí.
- `input_ref` / `output_ref` drží JSON přímo v řádku, ne odkaz na úložiště.

Router: `backend/api/flow/flow_routes.py`. Testy: `uv run pytest backend/flow backend/api/flow`.
