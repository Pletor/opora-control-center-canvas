# Brána mozku: práce pracovníka přes tickety

Kdy mě číst: projekt má zapnutou bránu mozku (`GET /api/brain/gate-setting?project=P` → `enabled: true`) a ty jsi
pracovník (např. z agent-office). Do takového projektu nezapisuješ přímo: zápis mimo bránu dostane 403
`gate_required`, kromě pruhu práce na kartě (`executions`, review, `agent-output`; orchestrátor karet viz
[srdce.md](srdce.md)). Práci ti vydává srdce jako **ticket** (`docs/navrhy/2026-11-03-novy-zaklad.md` §3.3): vezmeš
si ho, pracuješ, hlásíš zpětnou vazbu a odevzdáš. Kontrakt brány: `docs/brain-gate.md` §3 a §4.

## Klient `opora_gate.py` (jen standardní knihovna)

```bash
python "<SKILL_DIR>/scripts/opora_gate.py" session --project P --workspace W --name office-dev-1
python "<SKILL_DIR>/scripts/opora_gate.py" request
python "<SKILL_DIR>/scripts/opora_gate.py" claim --ticket tk_… [--execution ex_…]
python "<SKILL_DIR>/scripts/opora_gate.py" feedback --ticket tk_… --kind question "Smím změnit sdílený styl?"
python "<SKILL_DIR>/scripts/opora_gate.py" deliver --ticket tk_… --summary "…" --sha "$(git rev-parse HEAD)"
python "<SKILL_DIR>/scripts/opora_gate.py" release --ticket tk_…
python "<SKILL_DIR>/scripts/opora_gate.py" ask "Smím upravit sdílený modul X?"
python "<SKILL_DIR>/scripts/opora_gate.py" change "Rozděl kartu X na dvě." --reason "…"
python "<SKILL_DIR>/scripts/opora_gate.py" inbox --wait 20
python "<SKILL_DIR>/scripts/opora_gate.py" tell "Záměr člověka doslova"
```

- `tell` předá srdci záměr člověka (relé, [srdce.md](srdce.md)); zpráva nese `via` = jméno relace a budí srdce hned.
- Adresa z `OPORA_BASE_URL` (výchozí `http://127.0.0.1:8740`); brána je jen loopback, tunelem nejde.
- Token relace leží v `<cwd>/.opora/gate.json` (`.opora/` se připíše do `.gitignore`), platí 8 h. Nevypisuj ho.
- Výstup je jeden JSON. Kód 0 ok, 1 chyba klienta (chybí relace, server neběží), 2 server odmítl: řiď se `code` a `hint`.

## Smyčka pracovníka

1. `request` → `answer = {ticket, held}`: ticket, který držíš, jinak nejstarší vydaný (`issued`) v prostoru; nic =
   `ticket: null`, práci si nevymýšlej. Ticket je `{ticketId, status, body, machine, feedback}`; `body` je
   `{essence, build, openPaths[], cautions[], skills[], doneCriteria[]}`, `machine` `{cardId, executionId, cardVersion,
   department, profile}`; `department` / `profile` (oddělení a profil kanceláře, slug nebo null) určuje srdce
   v `ticket.issue`.
2. `claim` ticket vezme (`issued` → `claimed`); s `--execution` ho naváže na běžící exekuci karty, stav pak posouvá
   i exekuce (ověřeno, sloučeno = `verified` → `closed`, zrušená exekuce = `failed`, srdce se o tom dozví).
   Převzetí po restartu nebo vypršení relace: `claim` na rozpracovaný ticket jiné relace projde, když pošleš
   `--execution` shodné s `machine.executionId`, nebo když relace držitele vypršela; stav zůstane, ticket držíš ty
   (událost `ticket.resumed`). `request` cizí ticket sám nenabídne, převzetí je jen výslovné přes `claim`.
3. Pracuj podle `build` a `doneCriteria`, dbej `cautions`. Zpětná vazba (`bug`, `idea`, `improvement`, `question`)
   jde přes `feedback`; otázka přepne ticket na `needs_answer` a odpověď srdce uvidíš v `request` (`feedback[].answer`).
4. `deliver` se shrnutím (a sha z `git rev-parse HEAD`) → `delivered`. S otevřenou otázkou nejde.
5. Nedostal jsi místo ani exekuci: `release` vrátí vzatý ticket do fronty (`claimed` → `issued`). Rozpracovaný vrátit nejde.
6. Chyby: `ticket_not_held` (409, ticket nedržíš nebo ho drží jiná živá relace s jinou exekucí), `ticket_state` (409, nepovolený přechod; hint vypíše povolené),
   `ticket_execution` (409), `ticket_not_found` (404), `invalid_payload` (422), `gate_token_invalid` (401, nová
   `session`), `gate_scope` (403, jiný projekt).

## Cesty

| Cesta | Kdo | Co |
|---|---|---|
| `/api/gate/sessions` | kdokoli na loopbacku | `POST {project, workspace, worker: {name, office?, floor?}}` → `201 {sessionId, token, expiresAt}` |
| `/api/gate/requests` | token pracovníka | `POST {kind: ticket.request \| ticket.claim \| ticket.feedback \| ticket.deliver \| ticket.release \| ask \| change \| state \| inbox, body}` → `201 {ticketId, seq, kind, status, answer?}`; `ticket.*` a `state` odpoví hned |
| `/api/gate/kinds` | kdokoli na loopbacku | `GET` → druhy lístků pro roli volajícího (bez tokenu a s tokenem pracovníka druhy pracovníka) |
| `/api/gate/inbox` | token pracovníka | `GET ?after=<answeredSeq>&wait=0..30` → `{tickets, last}` (long-poll) |
| `/api/gate/tickets/{ticket_id}` | token (vlastní lístek) nebo člověk s `?project=` | `GET` lístek |
| `/api/brain/tickets` | čtení kdokoli | `GET ?project&workspace&status?` → `{tickets}` (tickety práce prostoru); `/api/brain/tickets/{ticket_id}?project=` jeden (404 neznámý) |
| `/api/brain/heart/messages` | člověk nebo token pracovníka téhož projektu | `POST {project, workspace, text}` → `{queued, pending}` (relé `tell`; 401 neplatný token, 403 `gate_scope`, 409 `gate_off`) |
| `/api/gate/tickets/{ticket_id}/answer` | jen člověk | `POST {answer}` na čekající `ask` / `change` |
| `/api/brain/intake-setting` | čtení kdokoli, zápis jen člověk | `GET ?project=`, `POST` povolení a denní strop Jevu vstupní brány (agent jen čte) |
| `/api/brain/brief-setting` | čtení kdokoli, zápis člověk nebo agent při plné autonomii | `GET ?project=`, `POST` výslech srdce zapnutý a strop rešerše na požadavek |
| `/api/brain/gate-setting` | čtení kdokoli, zápis jen člověk | `GET ?project=`, `POST {project, enabled}` |

## MCP místo `opora_gate.py` (H1d)

Když tě spustili s MCP serverem `opora` (`backend/api/brain_opora/mcp/opora_mcp.py`, kontrakt
`docs/brain-control-api.md` §3), nepouštěj `opora_gate.py` ani Bash: každý druh brány je nástroj
`mcp__opora__opora_<druh>` s tečkou nahrazenou `_` (`opora_ticket_request`, `opora_ticket_claim`,
`opora_ticket_feedback`, `opora_ticket_deliver`, `opora_ticket_release`, `opora_ask`, `opora_change`, `opora_state`,
`opora_inbox`; srdce navíc `opora_ticket_issue`, `opora_ticket_cancel`, `opora_ticket_answer`, `opora_escalate`).
Vstup je přesně `inputSchema` nástroje, nic předem nečti.

- Relaci zakládá server sám při prvním volání (z `OPORA_WORKER_NAME`); token nevidíš a nikam se neukládá.
- Výsledek je JSON brány `{ticketId, seq, kind, status, answer?}`; u `ticket.request` je ticket v `answer.ticket`.
- `opora_ask` s `"wait": true` počká až 30 s a vrátí rovnou `answer` (`answered: false` = zatím nic, později
  `opora_inbox` s `after` = poslední `last`).
- Chyba má `isError` a v textu `{code, hint, status}`; řiď se `hint`. `server_unreachable` = OPORA neběží.
