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
- **O2b – tvar dávky a chyby.** Odmítnutá dávka (4xx) dá do `hint` vlastní text serveru (a `field`/`expected`
  z 422), ne obecnou radu; srdce opraví jen to pole. Prompt „Plán“ nese krátký vzor dávky (sektor + dvě karty `node`
  s `card {layer, status: "ready"}`, `spec {goal, non_goals, acceptance, steps[{id, order, title, acceptance[],
  dependsOn[]}]}`, `checks[{id, command}]` a vazba `next`); tentýž vzor vypíše `plan --example`
  (`opora_heart.PLAN_EXAMPLE`). Test `backend/api/brain_opora/test_heart_plan.py` vzor z promptu vytáhne, porovná
  s nástrojem a pošle skutečnému `/api/canvas-plan` s `dryRun`, takže vzor nezastará.
- **O2b – přijetí plánu (rozhodnutí člověka 2026-10-29: „srdce plánuje, orchestrátor koná“).** Ostrý `plan` hned po
  dávce přijme plán sám, tokenem srdce: opakovaně čte `GET /api/oporahub/agent-state` a provede kroky
  `propose_graph` (`POST /api/oporahub/graph-proposals`, tělo = `project`, `workspace` + `preconditions` akce),
  přijetí návrhu grafu (`POST /api/oporahub/graph-proposals/{id}/accept`) a případně `accept_baseline`
  (`POST /api/oporahub/baselines`), nejvýš 6 kroků. Cizí návrhy zadání a obsahu (`accept` mimo graf) nechává
  člověku. Oprávnění: obě routy přijetí volají `require_authority` → `acts_as_human`; token srdce ve vlastním
  projektu se zapnutou bránou dostane ve zdi `Verdict(heart=True)` a middleware mu dá oprávnění `human` (plná
  autonomie, záznam `by: {kind: agent, name: heart}`), takže routy nebylo třeba měnit. Výstup `plan` má
  `accepted: true|false` a `acceptSteps`; při `false` `code` a `hint` (např. `plan_not_accepted`). `--no-accept`
  nechá přijetí člověku. Uzavření karty (`awaitingHumanClose`) zůstává člověku.
- **O2c – další plán nad přijatým grafem.** Fáze 2 je vždy další plán. Dávka plánu (`/api/canvas-plan`) nad už
  přijatým grafem by změnila jen pracovní graf: agent-state pro to nemá krok přijetí (návrh grafu záměrně nic
  z pracovního grafu nepřebírá) a claim všech karet by se zablokoval („Working graph differs from the accepted
  graph“). `plan` proto nejdřív čte `GET /api/oporahub/graph-proposals/context`; když má přijatý graf
  (`graphManifestId`), pošle dávku stejnou cestou jako formulář „Rozšíření plánu“ v UI
  (`frontend/hub/graph-proposals`): `POST /api/oporahub/graph-proposals {parentRevision: acceptedHead,
  expectedGraphDigest: graphDigest, subject, plan}` a hned `POST /api/oporahub/graph-proposals/{id}/accept
  {expectedAcceptedHead, expectedGraphDigest, adoptBaseGraphDigest: null}` tokenem srdce. Karty vzniknou na plátně až
  přijetím, pracovní a přijatý graf zůstanou shodné a dřívější claimy platí. Návrh grafu nese jen pole uzlu `ref, kind
  (node|sector|area), name, parent, purpose, spec, sourceRef, position, size, memberOf` a vazby `next`; `card`
  a `checks` nástroj vynechá s varováním, jiná pole odmítne (`code: plan_shape`) dřív než server. `--dry-run` ověří
  přírůstek dávkou plánu s `dryRun`. Výstup: `acceptSteps: ["graph_addition", "accept"]`, `proposalId`, `refs`.
  Žádná routa ani agent-state se neměnily. Test: `backend/api/brain_opora/test_heart_plan.py` (plán 1 → claim
  ready; plán 2 se sektorem `@id` a vazbou na existující kartu → nová karta ready, dřívější ready zůstal).
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

## 8. O6 – Kancelář jako kanál člověka (rozhodnutí 2026-10-30)

Člověk mluví s orchestrátorem v agent-office; orchestrátor jeho záměr **předá srdci doslova** a sám neplánuje.
Člověk 2026-10-30 povolil ladit oprávnění tak, aby kruh běžel bez schvalování (kromě uzavření karty).

- **Relé záměru (OPORA).** `POST /api/brain/heart/messages {project, workspace, text}` přijme kromě člověka i
  platný token pracovníka brány téhož projektu (hlavička jako u `opora_gate.py`). Zpráva se uloží do
  `brain/messages.jsonl` s `via: "<jméno relace>"`, budí srdce hned jako zpráva člověka a ve snímku má
  `ZPRÁVY ČLOVĚKA` značku „(přes <via>)“. Klient: `opora_gate.py tell "TEXT"`.
- **Orchestrátor v projektu se srdcem (agent-office).** Kancelář pozná zapnuté srdce
  (`GET /api/brain/gate-setting?project`). Pak `planning.start` v režimu `opora` použije prompt `planning.heart`:
  1. `opora_gate.py session` + `tell` se záměrem člověka (doslova, s fokusem); `canvas-plan` nikdy;
  2. čeká na dávku srdce (`GET /api/brain/heart/status`, nejvýš ~10 min) a pak čte nové karty (agent-state, frontier);
  3. do souhrnu zapíše, co srdce naplánovalo, a otázky srdce pro člověka (eskalace).
  Karty rozdá kancelář sama (hand-out → execution v pruhu → dělník ve worktree → PR); srdce se o sloučení dozví z gitu.
- **Oprávnění orchestrátora.** Planner v režimu srdce dostane `--allowedTools` pro skripty skillu
  (`Bash(python:*)` nad `opora_*.py`), `Read`, `Grep`, `Glob`, aby nečekal na schválení příkazů.

## 9. O7 – Srdce staví worktree podle práce (rozhodnutí 2026-10-30)

Člověk: „srdce musí budovat worktree podle toho, co dělá; všechno na agenty.“ V git projektu je `main` jen
architektura (prostředí › doména › stránka); karty žijí v pracovním prostoru = git worktree větve `work/<id>`
vázaný na doménu (`POST /api/workspaces`, `require_domain`).

- Srdce v `main` staví architekturu (domény, stránky) `plan`em; pro práci na doméně si založí pracovní prostor
  `opora_heart.py workspace --domain <nodeId>` (token srdce) a plánuje v něm karty (`plan --workspace W`).
  Jeden prostor = jedna doména nebo fáze; existující prostor domény znovu použije.
- `--workspace W` u `plan`, `task`, `decide` přepíše prostor dávky. Snímek git projektu má sekci `PROSTORY`
  (id, doména, větev, karty volné/běží/hotové).
- `GET /api/brain/heart/status` vrací `activeWorkspace` = prostor posledního přijatého plánu. Kancelář v režimu
  srdce jde za ním (nepřipnul-li člověk jiný).
- `ctx plan-of --project P [--workspace W]`: plán jiného projektu (karty, kroky, cíle) jako data do dílny, např.
  převod plánu lokální Ample do Ample git.

**Zjištěno testem proti skutečné aplikaci** (`backend/api/brain_opora/test_heart_workspace.py`, git projekt
z `managed_fixture`, brána zapnutá, token srdce prostoru `main`):

| Otázka | Skutečnost |
|---|---|
| `plan` architektury v `main` | `POST /api/canvas-plan` projde (`_check_main`: jen dávka, která mění čistě architekturu, tj. uzly se `site` a jejich předky, a nepíše stav Desktop v3). Karta v `main` → 409 „Čistý main je pouze pro čtení…“; nástroj k tomu dá `hint` s `workspace --domain` a `plan --workspace`. |
| přijetí v `main` | Nejde a není potřeba: agent-state `main` sice nabídne `propose_graph`, ale `POST /api/oporahub/graph-proposals` vrátí 409 „Graph additions require a writable workspace.“ Architektura leží jednou pro projekt (`ARCHITECTURE_WID`) a do prostorů se skládá. Nástroj v `main` přijetí vynechá; výstup `architecture: true` bez `accepted`. |
| vedlejší účinek změny architektury | Prostor s už přijatým plánem má po změně architektury v `main` `workingDiffers: true`, agent-state mu nenabízí žádný krok a **žádnou kartu nejde převzít**. Řešení bez nové routy: návrh změn grafu `POST /api/oporahub/graph-proposals {parentRevision, expectedGraphDigest, subject, plan: {adoptArchitectureContext: true}}` a `POST …/{id}/accept {…, adoptBaseGraphDigest: null, reviewedChangesId: id}` tokenem srdce (stejná volba jako v UI úprav plánu). Nástroj to dělá sám: po ostrém plánu architektury ve všech prostorech s `architectureContext.differs` (`adopted`), a před plánem v prostoru, jehož architektura se pohnula mimo nástroj (`acceptSteps: ["adopt_architecture", "accept", …]`). |
| `POST /api/workspaces {project, nodeId, actor}` | Routa (`backend/api/project/project_workspace_routes.py`) nevolá `require_authority`; v projektu se zapnutou bránou ji zeď pustí jen člověku a tokenu srdce (`Verdict(heart=True)`), pracovník bez tokenu dostane 403 `gate_required`. Oprávnění se **neměnilo**. Uzel, který není doménou (`require_domain`), vrátí 409 „Worktree musí patřit doméně…“. Seznam prostorů s doménou (`node_id`) a větví je v `GET /api/view?project&workspace=main` → `workspaces`; `GET /api/project-workspaces` dává jen popisky. |
| karty v prostoru | `plan --workspace W`: první plán = `canvas-plan` + `propose_graph` + `accept`, další plán = přírůstek návrhem grafu (O2c); claim karty je `ready`. Token srdce je vydaný pro `main`, ale zeď ho posuzuje podle projektu, takže platí ve všech prostorech projektu. Výjimka: `ctx` a `escalate` dál kontrolují prostor relace, proto `--workspace` nemají (u `ctx plan-of` je `--workspace` prostor cizího plánu). |
| `activeWorkspace` | Přijatý plán zapíše `brain/active_workspace.json {workspace, at}` (cwd dávky); `supervisor.status` ho čte (`brain_files.active_workspace`). Žádná tabulka. |
| PROSTORY | Snímek git projektu (každý prostor, ze kterého srdce běží): `- <celé id> · doména <jméno> [· větev, když není work/<id>] · karty volné n · běží n · hotové n`, ≤ 800 znaků. Celé ID místo zkráceného, protože ho srdce předává do `--workspace`. Karty = uzly `node` obsahu prostoru, stav z executions (`work_states`). |

## 10. O8 – Architektura nejdřív, nejpečlivěji (zásady člověka 2026-10-30)

Architektura určuje strom projektu a vrstev; z ní agent bere dlouhodobý směr, aby stavěl jen potřebné (žádné
vzdušné zámky, nic navíc, žádné slepé uličky). Není to dogma, je to výchozí uvažování srdce:

1. **Prostředí podle účelu.** Web = marketing a cesta zákazníka (navodit, aby člověk vstoupil dovnitř).
   Aplikace = logika a procesy, za které zákazník platí. Vývoj = až když je aplikace v produkci; co ve vývoji
   funguje a je otestované, jde do produkce (jako větev → main).
2. **Doména** otevře mapu a navigaci: navbar, kolik stránek, co na nich zákazník čeká a jak fungují.
3. **Stránka** řeší obsah: navbar, hero, cta, aside, bloky, footer. Stránka aplikace řeší proces (např. příjem
   surových dat stránek a souborů → uložení → příprava ke zpracování) a dělí se na vrstvy, sektory a uzly,
   které se smí zanořovat a propojovat.
4. **Postup:** kostra shora (vrstvy → oblasti → uzly), pak detail. Před předáním kanceláři výzkum ve schránce:
   ověřené podklady, že to jde takto postavit a bude to fungovat. Teprve pak karty.
5. **Worktree nese stránku + co se dělá** (název prostoru čitelný pro člověka i kancelář).
6. **Chronologie a sémantika:** srdce pracuje systematicky a v pořadí; každá karta má jasné předchůdce
   (`next` vazby, `dependsOn` kroků), aby kancelář věděla, co dřív a co později, a nikdo nikomu nelezl do práce.
7. **Plná autonomie:** OPORA je domov srdce. Kancelář plán přetaví do funkčního kódu a ten je pravda; srdce
   z něj ověřuje, co funguje, co zlepšit a kudy dál.

Komunikace srdce ↔ kancelář musí být bezchybná: měří se volání, zamítnutí, čas a cena (sonda O1).
