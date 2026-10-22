# Živý proces (`opora.process-event/1`)

Cíl: vidět, jak skutečná práce běží, bez zpoždění (push, ne polling), v 3D kanceláři
(agent-office) i v Opoře. Žádná demo data: když zdroj nic nehlásí, pohled to řekne
(„bez dat“, „odpojeno“, stáří zdroje), nikdy nevymýšlí. Tento dokument popisuje backend
Opory; podoba pohledu přijde v samostatném kroku.

**Jeden tok.** Živý proces je rozšíření [toku událostí OporaHubu](oporahub-events.md): události
kanceláře se zapisují do stejného outboxu `opora_events` jako změny Opory, mají stejný kurzor
(`id`), stejnou retenci a čtou se stejným `GET /api/oporahub/events` a SSE
`GET /api/oporahub/events/stream`. Samostatné `/process-events` (GET) ani `/process-stream`
nejsou: dřívější návrh s vlastní tabulkou a dvojitým kurzorem byl nahrazen tímto.

Kód: příjem `backend/canvas/process_ingest.py`, tvar `process_event_validation.py`, mapování druhů
`opora_event_process.py`, most ze záznamu činnosti `process_activity_bridge.py`, probuzení proudu
`process_signal.py`; router `backend/api/editor/oporahub_process_event_routes.py`; sloupce
`database/schema/opora_event_schema.py` (`ensure_process_columns`).

## 1. Fáze toku (`phase`)

| phase    | česky    | co sem patří |
|----------|----------|--------------|
| intake   | Zadání   | karta, úkol ve frontě kanceláře, přidělení, rozhodnutí člověka |
| plan     | Plán     | návrh a přijetí plánu, commit zadání, etapy plánu |
| work     | Práce    | běh (claim/heartbeat/výsledek), kroky, stav pracovníka, volání nástrojů |
| checks   | Kontroly | testy/build, self-checky, formální ověření, etapa `evidence` |
| review   | Revize   | PR, kola a nálezy review, brána merge |
| merge    | Sloučení | merge PR, zápis zpět do plánu, auto-rebase (upkeep) |
| memory   | Paměť    | OpenViking recall/remember, potvrzené dokončení karty |

## 2. Událost v toku

Každá událost `/api/oporahub/events` nese původní pole outboxu (beze změny pořadí, zpětně
kompatibilní) a za nimi pole živého procesu:

```json
{"id": 418, "at": "2026-10-22T10:14:03.180Z", "kind": "tool.use",
 "projectId": "opora", "workspaceId": "main", "nodeId": "n-42", "executionId": "ex-9",
 "stepId": null, "prNumber": null, "stage": null, "health": null,
 "actor": {"kind": "agent", "name": "Ada"},
 "data": {"actor": {"kind": "worker", "id": "w-3", "name": "Ada"}, "seq": 77, "sourceAt": "2026-10-22T10:14:03.120Z"},
 "source": "office", "phase": "work", "state": "progress", "title": "Upravuje soubor", "detail": null,
 "refs": {"project": "opora", "workspace": "main", "cardId": "n-42", "executionId": "ex-9", "workerId": "w-3"},
 "tool": {"name": "Edit", "action": "edit", "target": "backend/canvas/process_ingest.py"},
 "externalId": "office:floor-2:77", "schema": "opora.process-event/1", "eventId": "office:floor-2:77"}
```

Událost Opory (sloupce živého procesu jsou NULL, čtení je dopočítá z `kind`):

```json
{"id": 419, "at": "…", "kind": "merge.done", "projectId": "opora", "workspaceId": "main", "nodeId": "n-42",
 "executionId": "ex-9", "stepId": null, "prNumber": 31, "stage": null, "health": null,
 "actor": {"kind": "system", "name": "opora"}, "data": {"repository": "…", "mergeSha": "…", "mergedAt": "…"},
 "source": "opora", "phase": "merge", "state": "ok", "title": "PR sloučen", "detail": null,
 "refs": {"project": "opora", "workspace": "main", "cardId": "n-42", "executionId": "ex-9", "pr": 31},
 "tool": null, "externalId": null, "schema": "opora.process-event/1", "eventId": "opora:419"}
```

| Pole | Význam |
|---|---|
| `id`, `at` | kurzor a čas zápisu v outboxu (čas u zdroje kanceláře je `data.sourceAt`) |
| `source` | `office` \| `github` \| `opora` (NULL ve sloupci = `opora`) |
| `phase`, `state` | fáze toku a stav: `start`, `progress`, `ok`, `fail`, `wait`, `blocked`, `info` |
| `title` ≤ 120, `detail` ≤ 240 | lidský popis (delší text zdroje se zkrátí s „…“) |
| `refs` | `project`, `workspace`, `cardId`, `executionId`, `workerId`, `floor`, `branch`, `pr`, `sha`, `url` |
| `tool` | `{name, action?: read\|edit\|test\|web\|command\|failing, target? ≤ 80}` nebo `null` |
| `eventId` | `id` producenta (`${source}:${producerId}:${seq}`, klíč dedupe), u Opory `opora:<id>` |

Druhy kanceláře zůstávají, jak je poslala (`worker.status`, `tool.use`, `turn.start`, `turn.end`,
`needs.input`, `run.claim`, `run.release`, `run.result`, `queue.task`, `pr.opened`, `pr.checks`,
`pr.review`, `pr.merged`, `check.self`, `upkeep`, `guard`, `security.review` …).

Pravidla: zdroj nikdy neposílá token, lease token, heslo, absolutní cesty k datům ani obsah
promptu. „Hotovo“ je jen to, co zdroj potvrdil (dokončený tah ≠ prošlé testy ≠ review ≠ merge).

## 3. Příjem z kanceláře: `POST /api/oporahub/process-events`

Tělo `{events: ProcessEvent[]}`, 1–50 událostí ve tvaru kontraktu
(`schema`, `id`, `seq`, `at`, `source`, `kind`, `phase`, `state`, `title`, `detail?`, `actor?`, `refs`, `tool?`).
Kancelář posílá fire-and-forget do 250 ms od vzniku, s opakováním; práce na odpověď nečeká.

- **Autorizace** jako u ostatních agentních zápisů (např. `executions`): stejný `Origin` jako
  Opora, `Content-Type: application/json` (hranice ve `factory.py`) a hlavička
  `X-Opora-Actor: agent; name=<jméno>`. Bez hlavičky `428 identity_required`, člověk z UI
  `403 agent_required`. UI člověka k příjmu není potřeba.
- **Kontrola:** `schema` = `opora.process-event/1`, výčty `phase`/`state`, `source` jen `office`
  nebo `github` (`opora` vzniká uvnitř), `kind` je krátký identifikátor, `seq` ≥ 0, `at` ISO 8601,
  `refs.project` a `refs.workspace` povinné a musí v Opoře existovat (`main`, `draft` nebo
  pracovní prostor projektu). Neznámé klíče (i v `refs`, `actor`, `tool`) se zahodí.
- **Zápis:** jedna transakce na projekt přes `emit_event(..., process={...})`; `nodeId` =
  `refs.cardId`, `executionId` = `refs.executionId`, `prNumber` = `refs.pr`, `actor` = pracovník
  jako agent (jméno, jinak id, jinak jméno z hlavičky). Události kanceláře **nikdy nepřepočítávají
  etapu karty** (nevzniká z nich `stage.changed`).
- **Dedupe** podle `id` producenta (`external_id`, unikátní v projektu); opakování je `duplicates`.
- **Odpověď** `200 {accepted, duplicates, rejected: [{index, id?, error}]}`; když neprošla žádná
  událost, `422` se stejným tělem; špatný tvar těla `422 invalid_batch`.
- Retence je retence outboxu (14 dní, 50 000 řádků; `OPORA_EVENTS_*`).
- Příjem se **nezapisuje do `activity_log`** (vynechán v middleware), jinak by záznam zahltil.

```ts
await fetch(`${OPORA}/api/oporahub/process-events`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Origin: new URL(OPORA).origin,
             'X-Opora-Actor': 'agent; name=office-process' },
  body: JSON.stringify({ events }),
});
```

## 4. Události Opory

Opora vydává události v místě změny ([tok událostí](oporahub-events.md)); živý proces k nim jen
dopočítá `phase`/`state`/`title` (`opora_event_process.derive`, čistá funkce):

| kind | phase | state |
|---|---|---|
| `lease.claimed` / `lease.heartbeat` / `lease.expired` | work | start / progress / fail |
| `result.reported` | work | ok |
| `step.started` / `step.done` / `step.failed` | work | start / ok / fail |
| `pr.linked`, `review.round`, `review.finding` | review | info / progress / info (`open` nález = wait) |
| `gate.changed` | review | `ready` ok, `pending` wait, `blocked` blocked |
| `formal.result` | checks | proved/passed ok, failed/counterexample fail, jinak info |
| `decision.created` / `decision.resolved` | podle `data.decision` (accept → plan, close_card → merge, verification_* → checks, review_round_cap → review, jinak intake) | wait / ok |
| `changeset.proposed` / `changeset.accepted` | plan | info / ok |
| `autorebase.done` / `autorebase.conflict` | merge | ok / blocked |
| `merge.done`, `writeback.done` | merge | ok |
| `card.closed` | memory | ok |
| `stage.changed` | podle `stage` (plan/proposal/acceptance → plan, claim → intake, work, evidence → checks, review/pull_request → review, merge/plan_writeback → merge) | podle `health` (ok → progress, waiting → wait, blocking → blocked) |
| `memory.recall` / `memory.write` / `plan.commit` | memory / memory / plan | info / ok / info |

**Ze záznamu činnosti se nepřebírá nic, co outbox už vydává** (žádné dvojí události). Jen
úspěšné `POST /api/memory/recall` a `/lend` (`memory.recall`), `/api/memory/remember`
(`memory.write`) a starý commit zadání `/api/opora-commit` (`plan.commit`) nemají vlastní
událost; po zápisu je do outboxu přidá most `process_activity_bridge.py` (volaný ze záznamu
činnosti ve `factory.py`). Tyto druhy etapu karty nepřepočítávají.

## 5. Čtení a doručení

- `GET /api/oporahub/events?project&workspace&since&limit` a SSE `GET /api/oporahub/events/stream`
  podle [toku událostí](oporahub-events.md); kurzor je `id` outboxu, obnova přes `Last-Event-ID`.
  Filtr podle karty (`nodeId`) přidává samostatná větev stavu pro agenty; do té doby filtruje klient
  podle `nodeId` / `refs.cardId`.
- **Okamžité doručení:** `emit_event` i příjem kanceláře zvednou `PROCESS_SIGNAL`
  (`process_signal.py`); otevřený SSE proud čeká na signál místo pevného spánku. Poll
  (`poll_seconds`, 0,5 s) zůstává pojistkou pro zápisy, které se potvrdí až po probuzení.

## 6. Zdraví: `GET /api/oporahub/process-health?project&workspace`

```json
{"schema":"opora.process-health/1","project":"opora","workspace":"main","now":"…",
 "sources":{"office":{"lastAt":"…","ageSeconds":3.2},"opora":{"lastAt":"…","ageSeconds":41.0},
            "github":{"lastAt":null,"ageSeconds":null}},
 "officeFreshMinutes":10,"officeConnected":true,
 "memory":{"status":"configured","reason":"…","url":"…"},"listeners":1}
```

`lastAt` = čas zápisu poslední události zdroje v rozsahu. `officeConnected` = kancelář poslala
něco za posledních 10 minut. `memory` = výsledek `GET /api/memory/status` (OpenViking: disabled /
unavailable / needs_provisioning / configured). `listeners` = počet SSE proudů čekajících na signál.
Neznámý projekt `404`.

## 7. Ověření

`uv run pytest backend/canvas/test_process_event_validation.py backend/canvas/test_opora_event_process.py
backend/canvas/test_process_ingest.py backend/canvas/test_process_signal.py
backend/api/editor/test_oporahub_process_event_routes.py backend/canvas/test_opora_events.py`
