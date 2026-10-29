# Srdce ↔ orchestrátor ↔ git: kontrakt spolupráce (O1–O4)

Stav: kontrakt, rozhodnutí člověka 2026-10-29. Navazuje na `docs/brain-gate.md` (zeď, brána) a `docs/brain-heart.md`
(srdce). Cíl: aplikace se vyvíjí sama v kruhu **záměr → plán na plátně → práce dělníků → git → nový plán**.

## 1. Role

| Kdo | Dělá | Nedělá |
|---|---|---|
| člověk | píše záměr srdci (panel Asistent) nebo orchestrátorovi; odpovídá na eskalace; uzavírá karty | — |
| **srdce** (OPORA, `brain_opora/heart`) | jediné staví plátno: sektory, karty, `spec.steps`, architekturu (`canvas-plan`); vnímá git a podle něj upravuje plán | nepíše kód aplikace |
| **orchestrátor** (Claude v agent-office se skillem `opora-control-center`) | čte tabule (agent-state), bere karty (`executions`), rozesílá zadání dělníkům, odevzdává výsledky a PR | nestaví plátno; změnu plánu žádá u srdce lístkem |
| dělníci (relace orchestrátora) | kód v repu aplikace, commit, PR | nezapisují do OPORY mimo pruh |

Rozhodnutí 2026-10-29: „Srdce plánuje, orchestrátor koná“. Varianta „orchestrátor celý přes bránu“ zamítnuta.

## 2. O1 – Pruh orchestrátora ve zdi (`determinism/wall.py`)

Projekt se zapnutou bránou dnes odmítne každý zápis agenta mimo `/api/gate` (403 `gate_required`). Nově projdou
i zápisy **práce na kartě** (pruh, `LANE`), i bez tokenu brány. Plátno a pravidla dál zapisuje jen srdce a člověk.

| Pruh (projde agentovi) | Zůstává jen srdci a člověku |
|---|---|
| `/api/oporahub/executions/*` (claim, start, context, heartbeat, steps, results, deliver, pull-request, release, local-merge) | `/api/canvas-plan`, `/api/canvas-layout`, `/api/canvas-versions*` |
| `/api/oporahub/process-events`, `/api/oporahub/execution-observers/*` | `/api/oporahub/graph-proposals*`, `/changesets*`, `/content-changes*`, `/proposals` |
| `/api/oporahub/harness-*`, `/api/oporahub/github-evidence` | `/api/desktop-v3/node`, `/state`, `/block`, `/rule*`, `/decision`, `/pipeline`, `/autonomy`, `/confirm-proposals` |
| `/api/oporahub/review-jobs/*`, `/api/oporahub/review-identities/claim`, `/api/oporahub/verifications/*` | `/api/oporahub/repository*`, `/review-policy*`, `/design-mode`, `/execution-budgets*` |
| `/api/desktop-v3/agent-output`, `/agent-messages`, `/agent-message-receipt`, `/agent-workspace`, `/lease` | vše ostatní, co zapisuje |

- `decide(...)`: po větvi „čtení nebo brána“ přidat „cesta v `LANE` → `ALLOW`“. Pruh je seznam předpon v `wall.py`,
  porovnání po celých segmentech (`/api/oporahub/executions` ani `/api/oporahub/executionsX` neprojde omylem).
- Neplatný token (`INVALID`) se v pruhu ignoruje stejně jako bez hlavičky; pruh nepotřebuje token.
- Uzavření karty se nemění: sloučení dál nastaví `awaitingHumanClose`, kartu uzavírá člověk.
- `docs/brain-gate.md` §3 dostane řádek pruhu.

## 3. O2 – Srdce staví karty (`heart/opora_heart.py`, prompt)

- Nový příkaz `plan --file F [--dry-run]`: přečte `F` (JSON `plan` podle `/api/canvas-plan`), vezme čerstvý `digest`
  (`GET /api/view?project&workspace` → `digest`) a pošle `POST /api/canvas-plan {digest, plan, dryRun?}`
  s tokenem srdce. Výstup `{ok, refs, summary, warnings}` nebo `code`/`hint` (409 `stale` → zkus znovu s novým digestem,
  nejvýš jednou).
- Snímek: sekce `PLÁN` ukáže u karet stav práce z executions: `volná`, `běží (agent)`, `odevzdáno`, `PR #n`,
  `sloučeno sha`, `čeká na uzavření`. Bez nové tabulky, čte existující executions a vazby PR.
- Prompt „Plán“: práce pro orchestrátora = **karta na plátně** (`plan`), malá karta se `spec.steps` a ověřením;
  `task` (fronta brány) jen pro dělníka, který pracuje přes bránu. Po sloučení karty srdce plán neopakuje, ale
  navazuje (další karta, oprava, výzkum).

## 4. O3 – Srdce vnímá git (`heart/inputs.py`, `heart/supervisor.py`, `determinism/snapshot.py`)

| Vstup | Zdroj | Budí |
|---|---|---|
| `merged` `{nodeId, executionId, mergeSha, pr?}` | událost `merge.done` (sloučený PR karty nebo lokální sloučení) | po okně 20 s |
| `commits` `{from, to, log[≤ 20 řádků "sha7 titulek"]}` | hlídač gitu (níže): HEAD zdroje se pohnul | po okně 20 s |

- **Hlídač gitu** v supervisoru, každých 300 s, jen projekty se zapnutou bránou:
  - zdroj `git`: spustí existující synchronizaci aplikace (`service.sync(pid)`: fetch + `merge --ff-only`, odmítne
    špinavý nebo cizí upstream). Selhání se zapíše do deníku hlídače a srdce nebudí.
  - zdroj `local`: jen `git rev-parse HEAD` ve zdroji (nic nestahuje).
  - Poslední viděný HEAD drží v paměti; první průchod jen zapamatuje (nebudí). Změna → vstup `commits`
    s `git log --format="%h %s" from..to` (≤ 20).
- Kam vstup `commits` patří: `main` git projektu je jen ke čtení, karty v něm nevzniknou. Jeho posun proto dostanou
  pracovní prostory, ve kterých srdce od startu OPORY pracovalo; bez nich `main` (srdce aspoň odpoví nebo eskaluje).
- Vstupy `merged` a `commits` jdou do stropu 6 dávek za hodinu; víc sloučení v okně = jedna dávka.
- Snímek: nová sekce `GIT` za `POSLEDNÍ KONTROLY`: posledních 10 commitů zdroje (`sha7 titulek`), ≤ 1 200 znaků.
- Srdce dál čte kód zdroje (`--add-dir`), tedy pravdu po sloučení. Do `P:\opora-data` se zapisuje jen existující
  synchronizací aplikace, nic jiného.

## 5. O4 – Orchestrátor zná srdce (skill `opora-control-center`)

Nová reference `references/srdce.md` a řádek v tabulce „Chci X“ v `SKILL.md`:
- poznat zapnuté srdce: `GET /api/brain/gate-setting?project=P` → `enabled`;
- číst plán srdce: agent-state (karty), `GET /api/brain/heart/status` (poslední dávky), `GET /api/brain/heart/snapshot`;
- pracovat v pruhu: `opora_hub.py start/deliver` jako dnes; `canvas-plan` a návrhy v takovém projektu nepoužívat;
- mluvit se srdcem: `opora_gate.py session` + `ask "…"` (otázka) nebo `change "…"` (žádost o změnu plánu, záměr
  člověka předaný orchestrátorem); odpověď v `inbox`;
- po sloučení PR nic nehlásit: srdce to vidí z gitu samo.

## 6. Zapnutí (O5, člověk)

Bránu zapíná jen člověk (`POST /api/brain/gate-setting`, cookie UI): projekty **Tajemstvi-opory** (`41a67765…`) a
**ample** git (`5b0b4471…`), až po nasazení O1 (jinak se orchestrátor zastaví). Srdce na localhostu spí a budí ho jen
vstupy výše; „zapne se, když je potřeba“ je výchozí chování, žádný rozvrh.

## 7. Kroky

| Krok | Soubory | Testy |
|---|---|---|
| O1 pruh | `determinism/wall.py`, `docs/brain-gate.md` §3 | `test_wall.py` |
| O2 srdce staví karty | `heart/opora_heart.py`, `heart/prompt.md`, `determinism/snapshot.py` (PLÁN) | `test_opora_heart*.py`, `test_snapshot.py` |
| O3 git | `heart/inputs.py`, `heart/supervisor.py`, `determinism/snapshot.py` (GIT), `docs/brain-heart.md` §1 | `test_inputs.py`, `test_supervisor*.py`, `test_snapshot.py` |
| O4 skill | `.claude/skills/opora-control-center/references/srdce.md`, `SKILL.md` | lint skillu |
| O5 zapnutí | — (klik člověka v panelu Asistent) | `GET /api/brain/gate-setting` |
