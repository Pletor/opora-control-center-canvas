# Nový základ OPORY: engine toků, plátno srdce, Brain a ticket

Stav: návrh ke schválení (2026-11-03). Navazuje na vizi čtyř pláten (artefakt „Cesta OPORY“) a nahrazuje napevno zadrátovaný běh srdce a dvojí kanál práce.

## 1. Proč bourat

Dnešní základ unese jen „druhé patro“:

- **Srdce je skript.** Plánovač dávek je napevno v kódu (`heart/supervisor.py` 504 ř., okno 20 s, 6 dávek za hodinu). Stejně tak mapování událostí (`heart/inputs.py`) a jeden monolitický nástroj se 25 podpříkazy (`heart/opora_heart.py` 1271 ř.). Proces nejde vidět, měřit po uzlech ani měnit bez přepsání kódu.
- **Práce teče dvěma kanály.** Fronta `heart_tasks` (`/api/brain/tasks`) a karty přes executions. Mezi nimi přepíná heuristika `delivery.py`. Kancelář bránu vůbec nepoužívá a karty si sama bere z `frontier` (`agent-office/src/server/opora/bridge.ts`).
- **Ticket není jednotka práce.** `gate_tickets` zná jen stavy `queued` a `answered`, slouží pro otázky, ne pro zadání.
- **Logy jsou ad hoc JSONL** (`brain_files.py`). Prostoj dvě hodiny nikde nevidíš.
- **Srdce nemá knihovnu dovedností.** `prompt.md`, `skills/vyslech.md` a evaly v `.claude/hillclimb/` jsou rozházené, bez verzí a bez povýšení přes eval.

## 2. Rozhodnutí z rešerše

- **Vlastní tenký engine v Python backendu.** n8n se vložit nesmí: Sustainable Use License zakazuje, aby uživatelé stavěli workflow v cizím produktu, a to je přesně naše plátno. Převezmeme jen principy: typované porty agenta (`ai_languageModel`, `ai_memory`, `ai_tool`), záznam běhu po uzlech a připnutá data.
- **Pozorovatelnost a návrat z Temporal a LangGraph:**
  - append-only log událostí jako zdroj pravdy,
  - běh vázaný na neměnnou verzi workflow,
  - navázání přerušeného běhu znovuspuštěním uzlu s idempotency key.
- **Schválení jako větev s časovým limitem** (vzor Dify Human Input).
- **Brain jako lokální marketplace pluginů.** Skill má formát `SKILL.md`, verze je SHA a relace dostane konkrétní pin. Povýšení projde jen přes eval proti aktivní verzi na zmrazené sadě a vždy se mění jedna věc (lekce m11).
- **Zdroje:** licence n8n `github.com/n8n-io/n8n/LICENSE.md` a FAQ licence; `docs.langchain.com/oss/python/langgraph/durable-execution`; `docs.temporal.io/workflows`; `code.claude.com/docs/en/plugins-reference`; `code.claude.com/docs/en/plugin-evals.md`.

## 3. Moduly

### 3.1 Engine toků (`backend/flow/`, API `backend/api/flow/`)

Jeden engine pro plátno 1 (spouští se) a plátno 2 (zadání, které se nespouští). Druh plátna se pozná podle `kind`, dílek nikdy nečte druh projektu.

| Entita | Pole | Pozn. |
|---|---|---|
| `workflow` | id, kind (`heart`, `page_intent`, `brain_workflow`), project_id (null = sdílené), name | |
| `workflow_version` | id, workflow_id, n, graph (JSON), hash, parent_version_id, status (`draft`, `candidate`, `active`, `retired`), eval_run_id | neměnná; návrat = přepnutí `active` |
| uzel v `graph` | stálé id, type, type_version, params, position, pinned_output | |
| `node_type` / port | type, port, direction, kind (`main`, `model`, `memory`, `tool`, `subagent`, `approval`), cardinality, schema | registr v kódu |
| hrana v `graph` | id, source_node, source_port, target_node, target_port, kind, label | |
| `run` | id, workflow_version_id, trigger, status (`queued`, `running`, `waiting`, `succeeded`, `failed`, `cancelled`), parent_run_id, cost_usd, tokens | projekce logu |
| `node_run` | run_id, node_id, attempt, status, idempotency_key, input_ref, output_ref, error, provider, model, tokens_in, tokens_out, cost_usd, started_at, ended_at, last_heartbeat_at, waiting_for, deadline | prostoj = chybí heartbeat nebo vypršel deadline |
| `log_event` | seq, run_id, node_run_id, ts, type, payload, canvas (1–4) | append-only, přijímá i chyby z pláten 2–4 |

Interpret je deterministický plánovač nad grafem. Uzel typu `agent` spouští `claude -p` stávajícím exekutorem (`heart/batch.py`, `command.py`, `session.py`, `process.py`).

### 3.2 Katalog uzlů srdce (`backend/flow/catalogs/heart/`)

Většina dnešní logiky se nebourá, jen se převede na uzly:

- **Spouštěče:**
  - události z `determinism/triggers.py`, `idle.py` a `milestones.py`,
  - zpráva člověka,
  - `ticket.request` od orchestrátora,
  - plán (`schedule`) a webhook (nové).
- **Agent:** porty `model` (Anthropic pod předplatným, OpenAI přes `codex exec` jako kritik), `memory` (OpenViking), `tool` a `subagent`.
- **Nástroje:** `opora_heart.py` se rozdělí na registrované nástroje.

  | Oblast | Nástroje |
  |---|---|
  | Plátno | `canvas.decompose`, `canvas.contract` (bloky, porty a vazby toku; zákaz bloků padá), `canvas.impact` (následníci a otevřené cesty) |
  | Schránka | `vault.research`, `vault.duel`, `vault.plan` (`/api/brief-vault/*`) |
  | Ticket | `ticket.issue`, `ticket.answer` |
  | Ostatní | `decision.jev` (choice, score), `context.snapshot` (`snapshot.collect`) |
- **Schválení:** `approval.human` s časovým limitem. Používá se jen pro záměr stránky (plátno 2).

**Srdce v1** je workflow, které věrně opakuje dnešní chování supervisoru. Teprve až projde eval parity (sonda `heart-flow`), smí se supervisor smazat.

### 3.3 Ticket a tunel (rozšíření brány)

Jádro brány zůstává: `gate.py`, `kinds.py`, `kind_schemas.py`, `tokens.py`, `wall.py` a `api/brain_opora/mcp/opora_mcp.py` jako transport. Tabulka `gate_tickets` se přestaví na `ticket`:

- **Stavy:** `draft` → `issued` → `claimed` → `in_progress` ↔ `needs_answer` → `delivered` → `verified` → `closed` (nebo `failed`, `cancelled`).
- **Tělo pro dělníka (bez ID):**
  - podstata (proč a k čemu),
  - co postavit,
  - otevřené cesty pro následníky,
  - na co si dát pozor,
  - skills s pinem (`/x@verze`),
  - kritérium hotovo.
- **Strojová vrstva:** `card_id`, `execution_id`, `card_version`. Propisuje se do větve, commitu a traileru.
- **Zpětná vazba:** položky `bug`, `idea`, `improvement`, `question`, každá s vlastním ID a odpovědí srdce. Nápady a vylepšení se zároveň sčítají do záložek projektu s body za duplicitu.
- **Nové druhy brány:** `ticket.request` (orchestrátor žádá práci), `ticket.claim`, `ticket.feedback`, `ticket.deliver`, `ticket.answer`.
- **Executions zůstávají** jako vnitřní mechanika: lease, kroky, výsledky, PR. Claim spouští ticket, ne `frontier`.

### 3.4 Brain (`backend/brain/`)

- `artifact` (kind: `skill`, `tool`, `workflow`, `subagent`, `connector`; name; project_type tags) a `artifact_version` (version = SHA, content_ref, status, eval_score, baseline_version_id).
- **Vazby:** artefakt odkazuje na `log_event` (z jaké chyby vznikl), na `eval_run` a na uzly pláten, kde se použil.
- **Úložiště a předání:** obsah je lokální marketplace v datovém kořeni (`P:\opora-data\brain\`, git). Relace dostane pin přes nastavení a `SKILL.md` se v relaci jen čte.
- **Evaly skills a pluginů** pouští nativní `claude plugin eval`: případy, gradery a srovnání s baseline bez pluginu (platforma to umí, nestavíme vlastní). Evaly procesu srdce (`.claude/hillclimb/heart-flow`, `opora-vs-bare`, `research-desk`) se přesunou do `backend/brain/evals/` a spouští je engine uzel.
- **Pravidlo tvorby kódu:** skill `ponytail` (plugin `ponytail@ponytail`, MIT) je výchozí pin v každém ticketu. Dělník projde žebříček: má to existovat → je to už v kódu → standardní knihovna → nainstalovaná závislost → jeden řádek → minimum s testem. Odpověď končí tím, co vynechal nebo neověřil. V Brainu je artefakt `opora:brain:skill:ponytail@5.3.3`.
- **Povýšení:** subagent, který na evalu neporazí hlavního agenta, se převede na skill.
- **Co se přenáší:** mezi projekty jen know-how, nikdy data.

### 3.5 Frontend

- **`frontend/shared/flow-editor/`:** generický editor vytažený ze Studia MODEL. Obsahuje typy portů a pravidla vazeb (`model-types.ts`, `model-rules.ts`, `connection-policy.ts`), paletu, inspektor a animátor běhu. Studio ho pak bude používat také.
- **`frontend/project/heart-canvas/`:** plátno 1 na úrovni projektu. Zobrazuje graf aktivní verze, běhy a prostoje s důvodem, logy pláten 1–4 a rozdíl verzí. Úprava v něm vytvoří kandidáta na eval.
- **Proud logů** vychází z `hub/process-observatory`. Z `layout/heart-channel` zůstává composer a eskalace.

## 4. Co se maže

| Modul | Kdy |
|---|---|
| `heart/supervisor.py`, `heart/inputs.py`, `brain_files.py`, svázané části `heart_routes.py` | po přepnutí na engine (PR 3) |
| `determinism/task_queue.py`, `task_payloads.py`, tabulka `heart_tasks`, `/api/brain/tasks`, `delivery.py` | po zavedení ticketu (PR 5) |
| `bridge.ts`: autopilot, hand-out, `frontier`, `NO_HANDOUT_REASON`, `client.frontier` | PR 5 |
| `hub/oporahub-loop` | PR 6 |
| `library/pipelines.json` a prázdné `library/*` | PR 7 (přesun do Brainu) |
| rozpočty, observers, repin, conformance a lineage v executions | samostatné zjednodušení po PR 5 |

Každé mazání bere s sebou i testy, styly a README.

## 5. Pořadí PR

1. **Engine:** datový model, interpret, log, prostoje. Jen backend, s testy.
2. **Katalog srdce a srdce v1** jako workflow. Běží ve stínu vedle supervisoru a projde evalem parity.
3. **Přepnutí na engine** a smazání supervisoru.
4. **Ticket:** model, nové druhy brány, MCP, nástroje `ticket.issue` a `ticket.answer`.
5. **Kancelář žádá bránu.** Smazání samobraní, `heart_tasks` a `delivery.py`.
6. **Flow editor a plátno srdce v UI.**
7. **Brain:** registr, předání pinů do relací, eval gate. Přesun `prompt.md`, `vyslech.md` a skillu `opora-control-center`.
8. **Hloubka plátna:** nástroje pro bloky, porty a vazby toku, Schránka jako nástroj, následníci v ticketu.
9. **Uzel ChatGPT kritika** přes `codex exec`.

Po každém PR: `uv run pytest` (cílené), `npm test`, `npm run build`. Před PR 3 sonda srdce a eval parity.

## 6. Otevřené otázky pro člověka

1. **Kde je pravda o ticketu?** Návrh: v OPOŘE, protože srdce je jediný zapisovatel. Kartotéka v kanceláři je jejím pohledem a k ticketu ukládá záznamy relací.
2. **Kde žije Brain?** Návrh: `P:\opora-data\brain\` jako samostatný git repozitář.
3. **ChatGPT kritik přes `codex exec`** pod předplatným, ne přes API. Návrh: ano, v souladu s pravidlem „předplatné, ne API“.
