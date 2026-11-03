# Katalog uzlů srdce

Uzly, kterými engine toků (`backend/flow/`) spouští srdce mozku OPORY. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.2 a §5 bod 2. Uzly logiku srdce nepřepisují, jen obalují dnešní kód z `backend/brain_opora/`. Nahrazený je jen napevno zadrátovaný plánovač dávek v `heart/supervisor.py`.

## Uzly (`nodes.py`)

| Typ | Co obaluje | Porty |
|---|---|---|
| `trigger.heart_event` | Vstupy supervisoru z outboxu, gitu, karet, milníků, prázdné fronty a výslechu (`heart/inputs.py`, `determinism/triggers.py`, `idle.py`, `milestones.py`). Uzel je pustí přes `inputs.resolve`. | out `main`, `empty` |
| `trigger.human_message` | Totéž, když dávka nese zprávu člověka. Strop dávek za hodinu se na ni nevztahuje, stejně jako dnes. | out `main`, `empty` |
| `trigger.schedule` | Rozvrh `interval_seconds` (výchozí 600) místo 10min pojistky karet (`CARD_POLL`). Příští čtení outboxu projde karty všech prostorů. | out `main` |
| `decision.jev` | `decision/intake.classify_pending`: zařazení vstupů brány `pending` přes Jev. Je na cestě každé dávky. | in/out `main` |
| `context.snapshot` | Posun prostoru za `main`, pak `determinism/snapshot.snapshot` (`collect` + `render`, parametr `limit`). | in/out `main` |
| `agent.claude` | Dávka `claude -p` stávajícím exekutorem (`heart/batch.run`, `command.py`, `session.py`, `process.py`). Parametry `per_hour` (6), `per_project` (1) a `rate_sleep_seconds` (900). | in/out `main`; in `model` (jedna), `tool` (víc), `memory` (jedna, zatím nic nedělá) |
| `model.claude` | Model a poradce dávky (`model`: `haiku`, `advisor`: `opus`). | out `model` |
| `tool.opora_heart` | Nástroj `opora_heart.py`. `subcommands`: seznam povolených podpříkazů, nebo `null` = všechny (dnešní stav). Dávka bez nástroje dostane jen Read, Grep a Glob. | out `tool` |
| `tool.ticket_issue`, `tool.ticket_answer` | Registrované nástroje ticketu (§3.2 „Ticket“): povolí agentovi jen podpříkaz `opora_heart.py ticket-issue` / `ticket-answer` (druhy brány `ticket.issue` / `ticket.answer`). Do Srdce v1 zatím nejsou zapojené. | out `tool` |

Kroky dávky (`trigger.heart_event`, `trigger.human_message`, `decision.jev`, `context.snapshot` a `agent.claude`) jsou `detached`, protože čtou projekt pod jeho zámkem, Jev jde po síti a `claude -p` běží minuty. Proto běží ve vlastním vlákně mimo `registry_lock` (`runtime.detached`). Každých 60 s pošlou `node.heartbeat` a skončí `interpreter.finish` nebo `fail`. Uzel bez heartbeatu delší než 5 min je prostoj a plánovač ho naváže pokusem `attempt + 1`.

## Srdce v1 (`seed.py`)

`trigger.heart_event` a `trigger.human_message` → `decision.jev` → `context.snapshot` → `agent.claude`. K agentovi vede `model.claude` (Haiku, poradce Opus) a `tool.opora_heart` (všechny podpříkazy). Vedle stojí `trigger.schedule` po 600 s. Graf opakuje pořadí kroků v `HeartSupervisor._batch`.

**Sdílené workflow** (`project_id` NULL, jméno „Srdce v1“). Důvod: supervisor má jedno chování pro všechny projekty se zapnutou bránou a pravidlo „jedno rozhraní pro všechny projekty“ platí i pro proces srdce. Workflow pro konkrétní projekt by zavedlo rozdíl, který dnes nikdo nepotřebuje. Seed vznikne při startu v režimu `on` idempotentně: aktivní verzi, i upravenou přes API, nechá být.

## Řízení (`driver.py`) a přepínač

`OPORA_FLOW_HEART` v prostředí procesu:

- `off` (výchozí): plánovač enginu běží jen pro obecné posouvání běhů (deadline, navázání). Srdce řídí supervisor jako dnes.
- `on`: vlákno supervisoru se nespustí a `HeartDriver` je háček plánovače (`backend/flow/scheduler.py`). Platí jen spolu s podmínkami `supervisor.enabled()` (loopback, `OPORA_HEART` není `off`). Oba plánovače tak nikdy nepoběží zároveň, protože srdce je jediný zapisovatel.

Supervisor zůstává zdrojem vstupů a stavu:

- `collect` čte outbox a git,
- `message` přijímá zprávu člověka a budí plánovač,
- `take_due` drží okno 20 s, jeden prostor na dávku a spánek po limitu,
- `status` dál slouží pro `GET /api/brain/heart/status` a sondu.

Driver v každém průchodu:

1. Vyhodnotí `trigger.schedule`.
2. Zavolá `collect`.
3. Uvolní hotové běhy. Projekt vypadne z `running`, chyba uzlu jde do `errors`.
4. Splatné vstupy pustí jako běh aktivní verze. Stropy bere z parametrů `agent.claude`.

Po restartu převezme otevřené běhy srdce, aby projekt nedostal druhou dávku, a engine je naváže.

API zůstává `/api/flow` beze změny. Zprávy člověka jdou dál přes `POST /api/brain/heart/messages`.

## Vynecháno

- Ruční běh workflow srdce přes `POST /api/flow/versions/{id}/runs` obchází stropy driveru. Je to nástroj na ladění, ne cesta srdce.
- `per_project` větší než 1 engine unese, ale srdce sdílí relaci a `brain/` projektu, takže to bezpečné není. Seed nechává 1.
- Port `memory` (OpenViking), `subagent`, `ticket.request` a webhook přijdou v dalších PR.
- Supervisor a jeho routy se smažou až v PR 3, po evalu parity.

Testy: `uv run pytest backend/flow`.
