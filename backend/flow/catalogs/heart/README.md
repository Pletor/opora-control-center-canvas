# Katalog uzlů srdce

Uzly, kterými engine toků (`backend/flow/`) spouští srdce mozku OPORY. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.2 a §5 body 2–3. Uzly logiku srdce nepřepisují, jen obalují dnešní kód z `backend/brain_opora/`. Engine je jediná cesta dávek srdce: napevno zadrátovaný plánovač (`heart/supervisor.py`) je od PR 3 smazaný a jeho vstupy a stav sem přešly beze změny chování.

## Uzly (`nodes.py`)

| Typ | Co obaluje | Porty |
|---|---|---|
| `trigger.heart_event` | Vstupy srdce z outboxu, gitu, karet, milníků, prázdné fronty a výslechu (`wakes.py`, `git_watch.py`, `inputs.py`, `determinism/triggers.py`, `idle.py`, `milestones.py`). Uzel je pustí přes `inputs.resolve`. | out `main`, `empty` |
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

`trigger.heart_event` a `trigger.human_message` → `decision.jev` → `context.snapshot` → `agent.claude`. K agentovi vede `model.claude` (Haiku, poradce Opus) a `tool.opora_heart` (všechny podpříkazy). Vedle stojí `trigger.schedule` po 600 s. Graf opakuje pořadí kroků dřívější dávky supervisoru.

**Sdílené workflow** (`project_id` NULL, jméno „Srdce v1“). Důvod: srdce má jedno chování pro všechny projekty se zapnutou bránou a pravidlo „jedno rozhraní pro všechny projekty“ platí i pro proces srdce. Workflow pro konkrétní projekt by zavedlo rozdíl, který dnes nikdo nepotřebuje. Seed vznikne při startu idempotentně: aktivní verzi, i upravenou přes API, nechá být.

## Stav a vstupy srdce (`heart.py`)

`Heart` skládá tři moduly do jednoho objektu, se kterým pracují uzly (`runtime.heart`), driver a routy `/api/brain/heart/*`. Vlastní vlákno nemá.

- `state.py` (`HeartState`): fronta `pending` `(prostor, vstup, splatnost)`, `running`, `current` (běžící dávka pro kanál srdce), `errors`, `starts` a `sleeping_until`. `take_due` vybere splatné vstupy jednoho prostoru na projekt. Strop `per_hour` platí jen pro automatické dávky, zpráva člověka ho obchází a prázdná dávka se nepočítá. Dále token srdce (jen v paměti), `brain` a `status`, tedy tvar `GET /api/brain/heart/status`. `enabled()` vrací povolení srdce: `OPORA_HEART` není `off` a server běží na loopbacku.
- `wakes.py` (`Wakes`): zpráva člověka (`message`). Zprávu nejdřív zapíše vstupní brána, pak `brain/messages.jsonl`. Stejná věta (`duplicate`) srdce nebudí. Čtení outboxu (`poll_events`, po signálu nebo jednou za 10 s): lístky `ask` / `change`, `failed` úkol a `merge.done` dostanou okno 20 s. Spouštěče milníku, ruční změny plánu, karet (po události nejvýš jednou za minutu, plný průchod při prvním čtení a po `trigger.schedule`), prázdné fronty (jednou za 2 min, ne během dávky) a výslechu. Dohánění po startu (`inputs.backlog`).
- `git_watch.py` (`GitWatch`): hlídač gitu jednou za 5 min ve vlastním vlákně. U zdroje `git` spustí synchronizaci aplikace a posune čisté prostory za `main`. Pohnutý HEAD přidá vstup `commits`. Před dávkou posune prostor za lokální `main` (uzel `context.snapshot`).
- `inputs.py`: událost → vstup (`wake_input`), čerstvá data vstupu těsně před dávkou (`resolve`) a výpočty spouštěčů.
  Ticket práce budí otázkou dělníka (`workQuestion`: text, `feedbackId`, stav; zodpovězená vypadne) a odevzdáním
  (`workDelivered`: shrnutí, sha), obojí z auditní události `gate.ticket` (`feedbackKind` nese typ zpětné vazby).

## Řízení (`driver.py`)

`HeartDriver` je háček plánovače (`backend/flow/scheduler.py`). Továrna (`backend/app/factory.py`) ho zapojí vždy, když je srdce povolené (`state.enabled()`). Plánovač sdílí `wakeup` srdce, takže zpráva člověka ho probudí hned.

Driver v každém průchodu:

1. Vyhodnotí `trigger.schedule`.
2. Zavolá `collect` (outbox a hlídač gitu).
3. Uvolní hotové běhy. Projekt vypadne z `running`, chyba uzlu jde do `errors`.
4. Splatné vstupy pustí jako běh aktivní verze. Stropy bere z parametrů `agent.claude`.

Po restartu převezme otevřené běhy srdce, aby projekt nedostal druhou dávku, a engine je naváže.

API zůstává `/api/flow` beze změny. Zprávy člověka jdou dál přes `POST /api/brain/heart/messages`, stav přes `GET /api/brain/heart/status` ve stejném tvaru jako dřív.

## Vynecháno

- Ruční běh workflow srdce přes `POST /api/flow/versions/{id}/runs` obchází stropy driveru. Je to nástroj na ladění, ne cesta srdce.
- `per_project` větší než 1 engine unese, ale srdce sdílí relaci a `brain/` projektu, takže to bezpečné není. Seed nechává 1.
- Port `memory` (OpenViking), `subagent`, `ticket.request` a webhook přijdou v dalších PR.
- Deník dávek a zprávy člověka zůstávají v JSONL v `brain/` projektu (`determinism/brain_files.py`), protože je čte snímek a dílna (`ctx journal`, `ctx messages`). Nahrazení logem enginu je další krok.

Testy: `uv run pytest backend/flow`. Společná fixture `make_heart` (`conftest.py`) staví skutečný `Heart` a `HeartDriver`. Uzly v ní běží synchronně a `run_once()` je jeden průchod plánovače i s doběhnutím dávky.
