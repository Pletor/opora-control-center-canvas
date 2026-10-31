# Brána mozku: práce pracovníka přes frontu úkolů

Kdy mě číst: projekt má zapnutou bránu mozku (`GET /api/brain/gate-setting?project=P` → `enabled: true`) a ty jsi
pracovník (např. z agent-office). Do takového projektu nezapisuješ přímo: zápis mimo bránu dostane 403
`gate_required`, kromě pruhu práce na kartě (`executions`, review, `agent-output`; orchestrátor karet viz
[srdce.md](srdce.md)). Úkol si vezmeš z fronty, uděláš ho ve svém repu, spustíš kontroly a nahlásíš sha. Kontrakt:
`docs/brain-gate.md` §3, §4 a §6 (H1b).

## Klient `opora_gate.py` (jen standardní knihovna)

```bash
python "<SKILL_DIR>/scripts/opora_gate.py" session --project P --workspace W --name office-dev-1
python "<SKILL_DIR>/scripts/opora_gate.py" next
python "<SKILL_DIR>/scripts/opora_gate.py" ask "Smím upravit sdílený modul X?"
python "<SKILL_DIR>/scripts/opora_gate.py" change "Rozděl kartu X na dvě." --reason "…" [--task ht_…]
python "<SKILL_DIR>/scripts/opora_gate.py" report --task ht_… --sha "$(git rev-parse HEAD)" --summary "…" \
  --check "npm test=green" --check "uv run pytest backend/x=green"
python "<SKILL_DIR>/scripts/opora_gate.py" release --task ht_… --reason "Úkol potřebuje soubor z dontTouch."
python "<SKILL_DIR>/scripts/opora_gate.py" inbox --wait 20
python "<SKILL_DIR>/scripts/opora_gate.py" tell "Záměr člověka doslova"
```

- `tell` předá srdci záměr člověka (relé, [srdce.md](srdce.md)); zpráva nese `via` = jméno relace a budí srdce hned.
- Adresa z `OPORA_BASE_URL` (výchozí `http://127.0.0.1:8740`); brána je jen loopback, tunelem nejde.
- Token relace leží v `<cwd>/.opora/gate.json` (`.opora/` se připíše do `.gitignore`), platí 8 h. Nevypisuj ho.
- Výstup je jeden JSON. Kód 0 ok, 1 chyba klienta (chybí relace, server neběží), 2 server odmítl: řiď se `code` a `hint`.

## Smyčka pracovníka

Postup dělníka krok za krokem (smyčka, sprinty, cílené čtení, kdy se ptát) je ve skillu
[opora-gate-worker](../../opora-gate-worker/SKILL.md). Tady jen tvar odpovědí a chyb.
Sprinty: úkol z `next` nese `checkpoint` a `sprint`; mimo kontrolní bod se build a testy nespouští a hlásí jako
`--check "npm run build=deferred" --check "npm test=deferred"`, kontrolní bod hlásí skutečné výsledky
(`deferred` → 422 `checkpoint_needs_checks`).

1. `next` → `answer.task = {id, title, nodeId, status, attempts, body}`; `body` má pevný tvar
   `{why, do, files[], doneWhen[], dontTouch[{path, heldBy}], context{intent?, rules[]?, pattern?}, commit}`.
   Opakované `next` vrátí tentýž držený úkol. Prázdná fronta: `{task: null, plan: [{id, name, stage}]}` (nejvýš 20
   otevřených karet); úkol si nevymýšlej, zeptej se (`ask`) nebo čekej.
2. Pracuj jen na `files`, nesahej na `dontTouch`. Kontroly spusť sám; nevymýšlej sha ani výsledky.
3. Commitni práci a `report` s `sha` z `git rev-parse HEAD` (7–40 hex) a aspoň jednou kontrolou. Všechny zelené =
   `done`, ale jen když sha ve zdrojovém repu prostoru existuje (jinak 422 `sha_unknown`; bez git zdroje se
   neověřuje). Červená = úkol se vrátí do `ready`
   (`attempts + 1`) a `next` ho dá znovu; druhá červená = `failed`. Kontroly se zapíší do `check_runs` u sha.
4. Úkol nedokončíš (chybí podklad, potřebuješ soubor z `dontTouch`, končíš relaci): `release --task … --reason "…"`
   ho hned vrátí do `ready` (`attempts` beze změny, důvod uvidí srdce). Jinak ho držíš až 8 h do vypršení tokenu.
5. Chyby: `task_not_assigned` (409, úkol nedržíš), `invalid_sha`, `sha_unknown`, `checks_required`, `invalid_payload` (422),
   `task_not_found` (404), `gate_token_invalid` (401, nová `session`), `gate_scope` (403, jiný projekt).

## Cesty

| Cesta | Kdo | Co |
|---|---|---|
| `/api/gate/sessions` | kdokoli na loopbacku | `POST {project, workspace, worker: {name, office?, floor?}}` → `201 {sessionId, token, expiresAt}` |
| `/api/gate/requests` | token pracovníka | `POST {kind: next \| ask \| report \| release \| change, body}` → `201 {ticketId, seq, kind, status, answer?}`; `next`, `report` a `release` odpoví hned |
| `/api/gate/kinds` | kdokoli na loopbacku | `GET` → druhy lístků pro roli volajícího (bez tokenu a s tokenem pracovníka druhy pracovníka) |
| `/api/gate/inbox` | token pracovníka | `GET ?after=<answeredSeq>&wait=0..30` → `{tickets, last}` (long-poll) |
| `/api/gate/tickets/{ticket_id}` | token (vlastní lístek) nebo člověk s `?project=` | `GET` lístek |
| `/api/brain/heart/messages` | člověk nebo token pracovníka téhož projektu | `POST {project, workspace, text}` → `{queued, pending}` (relé `tell`; 401 neplatný token, 403 `gate_scope`, 409 `gate_off`) |
| `/api/gate/tickets/{ticket_id}/answer` | jen člověk | `POST {answer}` na čekající `ask` / `change` |
| `/api/brain/gate-setting` | čtení kdokoli, zápis jen člověk | `GET ?project=`, `POST {project, enabled}` |
| `/api/brain/tasks` | čtení kdokoli, zápis jen člověk | `GET ?project&workspace&status?` → `{tasks}`; `POST {project, workspace, nodeId?, title, body}` → `201` úkol |
| `/api/brain/tasks/{task_id}/cancel` | jen člověk | `POST ?project=` (tělo `{}`) → zrušený úkol; uzavřený = 409 `task_closed` |

## MCP místo `opora_gate.py` (H1d)

Když tě spustili s MCP serverem `opora` (`backend/api/brain_opora/mcp/opora_mcp.py`, kontrakt
`docs/brain-control-api.md` §3), nepouštěj `opora_gate.py` ani Bash: každý druh brány je nástroj
`mcp__opora__opora_<druh>` (`opora_next`, `opora_ask`, `opora_report`, `opora_change`, `opora_state`,
`opora_inbox`, `opora_release`; srdce navíc `opora_task_create`, `opora_task_cancel`, `opora_ticket_answer`, `opora_escalate`).
Vstup je přesně `inputSchema` nástroje, nic předem nečti.

- Relaci zakládá server sám při prvním volání (z `OPORA_WORKER_NAME`); token nevidíš a nikam se neukládá.
- Výsledek je JSON brány `{ticketId, seq, kind, status, answer?}`; u `next` je úkol v `answer.task`.
- `opora_ask` s `"wait": true` počká až 30 s a vrátí rovnou `answer` (`answered: false` = zatím nic, později
  `opora_inbox` s `after` = poslední `last`).
- Chyba má `isError` a v textu `{code, hint, status}`; řiď se `hint`. `server_unreachable` = OPORA neběží.
