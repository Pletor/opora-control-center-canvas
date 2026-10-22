# Automatické review kódu (etapa 3a, strana Canvasu)

Canvas koordinuje review PR připojených k běhům ([uzavření smyčky](oporahub-executions.md#uzavření-smyčky-běh--pr--merge--plán)).
Hledání a hlasování dělají modely v pracovnících agent-office; **veškeré účetnictví
dělá backend deterministicky**: zařazení úloh, kola, riziko, agregaci hlasů,
deduplikaci nálezů a bránu merge. Canvas z GitHubu jen čte (seznam změněných souborů)
a nic na GitHub nezapisuje; komentáře do PR bude psát agent-office.

Principy převzaté z [Solving code review at Anthropic](https://claude.dev/blog/solving-code-review-at-anthropic/)
(je to podklad, ne specifikace): několik hledačů v čerstvých kontextech, oddělené
ověření hlasováním, závažnosti `important` / `nit` / `pre_existing`, každý nález je
opraven nebo vypořádán s důvodem, otevřený `important` blokuje, riziko určuje změna
(ne autor), schválení agentem nikdy není lidské, schválení platí pro jedno SHA,
nejvýše 3 kola a další kola hlídají jen nový diff bez opakování nálezů. Část A doplňuje
[pravidla brány](#pravidla-brány): bezpečnostní review jako samostatný blokující druh úlohy,
důkaz vlastních kontrol agenta před PR, sémantiku fronty merge (zelené kontroly na hlavě postavené
na aktuální cílové větvi) a šablonu PR s testováním, rizikem a plánem návratu.

## Zapnutí a konfigurace

Výchozí soubor `backend/canvas/opora_review_jobs.toml` (`enabled = false`).
`OPORA_REVIEW_JOBS=1` funkci zapne (`0` vypne) bez úpravy souboru;
`OPORA_REVIEW_JOBS_CONFIG=<cesta>` nahradí celý soubor. Konfigurace se čte jednou
za proces, změna vyžaduje restart. Neplatná hodnota (např. `required_votes > voters`)
je chyba, nikdy tiché oslabení.

| Klíč | Výchozí | Význam |
|---|---|---|
| `jobs.finders` | 3 | Počet hledačů (slotů) na kolo |
| `jobs.voters` | 3 | Počet ověřovatelů |
| `jobs.required_votes` | 2 | Potvrzení nutná, aby se kandidát stal nálezem |
| `jobs.max_rounds` | 3 | Strop dokončených kol na PR; další hlavu rozhoduje člověk |
| `risk.medium_lines` / `high_lines` | 200 / 1000 | Přidané + odebrané řádky celé změny PR |
| `risk.medium_files` / `high_files` | 10 / 40 | Počet změněných souborů |
| `risk.sensitive` | `.github/workflows/**`, `**/auth/**`, `**/migrations/**`, `database/schema/**`, … | Citlivé cesty (glob: `*` uvnitř segmentu, `**` přes adresáře) |
| `approvals.low/medium/high` | 0 / 1 / 1 | Požadovaná lidská schválení (`high = 1` je rozhodnutí vlastníka, viz níže) |
| `approvals.sensitive_minimum` | 1 | Citlivá změna vždy aspoň tolik schválení |
| `approvals.agent_account_ids` | `[]` | Číselná GitHub ID účtů agentů; jejich schválení se nepočítají |
| `security.enabled` / `min_tier` | `true` / `medium` | Bezpečnostní review (`kind: "security"`) pro hlavy s rizikem aspoň `min_tier` |
| `security.paths` | `.github/workflows/**`, `**/auth/**`, `backend/app/**`, `backend/integrations/**`, … | Bezpečnostně citlivé cesty, vždy bezpečnostní review; prázdné = `risk.sensitive` |
| `self_checks.required` | `["tests", "build"]` | Jména vlastních kontrol, které agent dokládá pro aktuální hlavu; prázdné = pravidlo vypnuto |
| `merge_queue.enabled` | `true` | `ready` jen pro hlavu postavenou na aktuální hlavě cílové větve |
| `merge_queue.required_checks` | `[]` | Názvy povinných CI kontrol (check run nebo status context) na hlavě PR |
| `merge_queue.base_max_age_seconds` / `observe_interval_seconds` | 900 / 60 | Stáří, po kterém pozorování cílové větve neplatí; nejkratší odstup dvou čtení |
| `template.sections` | `["Testing", "Risk", "Revert plan"]` | Povinné sekce popisu PR; prázdné = pravidlo vypnuto |

Chybějící sekce `[security]`, `[self_checks]`, `[merge_queue]` nebo `[template]` své pravidlo
vypne (starší soubory si zachovají význam); dodaný soubor zapíná všechna.

### Schválení pro riziko high

Dodaná konfigurace žádá u `high` **jedno** lidské schválení (dříve 2). Je to vědomé
rozhodnutí vlastníka: projekt vede jeden vývojář, druhého ověřeného člověka nemá,
a `high` by tak nešlo nikdy splnit. Úroveň rizika se dál počítá a zobrazuje stejně,
bezpečnostní review, vlastní kontroly i merge fronta platí beze změny a citlivé cesty
žádají vždy aspoň `sensitive_minimum` (≥ 1, menší hodnotu konfigurace odmítne).

Jakmile na projektu pracuje víc lidí, vraťte druhý pár očí: v `opora_review_jobs.toml`
(nebo ve vlastním souboru z `OPORA_REVIEW_JOBS_CONFIG`) nastavte `[approvals] high = 2`
a restartujte server. Dvě schválení pak musí dát dva různí ověření lidé
([identity reviewerů](oporahub-review-identity.md)).

## Riziko ze změny

Při zařazení úlohy server mimo zámky přečte (jen GET) PR a jeho soubory
(`/pulls/{n}/files`, nejvýše 3 stránky po 100) a ověří, že hlava PR před i po čtení
je přesně SHA úlohy. Přejmenování počítá starou i novou cestu.

1. Změnu nejde přečíst, je neúplná, hlava se pohnula, nebo projekt nemá GitHub
   → `high` (`change_unobserved`), tj. `approvals.high` schválení (dodáno 1). Selhání nikdy nesnižuje riziko.
2. Řádky ≥ `high_lines` nebo soubory ≥ `high_files` → `high` (`large_change`);
   ≥ medium prahy → `medium` (`medium_change`); jinak `low` (`small_change`).
3. Zásah do citlivé cesty zvedne úroveň aspoň na `medium` a přidá důvod
   `sensitive_path:<glob>`; požadavek je aspoň `sensitive_minimum`.

Úroveň se ukládá do úlohy (`riskTier`, `risk.reasons`) a nemění se zpětně.

## Životní cyklus úlohy

Úloha vzniká pro každé otevřené PR vazby běhu s novým `headSha` (druh `code`; bezpečnostní
úlohy viz [druh úlohy](#druh-úlohy-kind)). Zařazení spouští
`POST /sync` a každý `POST /claim` (deterministicky, bez modelu). Klíč je
(repozitář, číslo PR, `headSha`): opakování nikdy nevytvoří druhou úlohu.

- `round` = počet dokončených kol + 1; `sinceSha` = hlava posledního dokončeného
  kola (`null` v prvním kole). Pracovník v dalším kole reviewuje jen
  `git diff sinceSha..headSha`.
- Nový push ukončí nedokončenou úlohu starší hlavy stavem `superseded` (její sloty
  už nic neodevzdají) a do počtu kol se nepočítá. Návrat na dříve přerušenou hlavu
  tuto úlohu obnoví.
- Po `max_rounds` dokončených kolech se nová úloha nezařadí. Brána hlásí
  `review_round_cap_reached`; člověk rozhodne přes `POST /decisions`.
- Fáze: `find` (N slotů hledačů) → `vote` (V slotů ověřovatelů, jen když existuje
  kandidát) → `completed`.

**Agregace.** Po odevzdání všech hledačů backend seskupí kandidáty podle
`fingerprint` (nejvyšší závažnost, znění nejnižšího slotu, seznam `finders`).
Otisky, které už na PR existují jako nález v jakémkoli stavu (`open`, `fixed`,
`resolved`), se znovu nenavrhují. Tvrzení o opravě (`fixed`) je samostatný kandidát
`kind: fix`. Po hlasování se kandidát `finding` s alespoň `requiredVotes` potvrzeními
stane nálezem (`open`); potvrzený `fix` označí nález `fixed` s `headSha` kola.

**Vypořádání.** Nález končí jako `fixed` (potvrzeno hlasy v pozdějším kole) nebo
`resolved` s důvodem. `important` vypořádá bez opravy jen člověk; agent smí
vypořádat `nit` a `pre_existing`.

## Brána merge (read model)

`read_review_gates(canvas, project, workspace)` v `backend/canvas/opora_review_gate.py`
(a `GET /gates`) vrací pro každé připojené PR:

```json
{"executionId": "…", "cardId": "…", "repository": "owner/repo", "number": 7, "headSha": "…",
 "prState": "open", "reviewJobId": "rj_…", "round": 1, "riskTier": "medium",
 "mergeReadiness": {"security": {"reviewJobId": "rj_…", "phase": "completed", "reasons": ["security_path:**/auth/**"],
                                 "openImportant": 0},
                    "selfChecks": {"status": "ok|missing|failed|off", "source": "result|addendum|null",
                                   "missing": [], "failed": [], "invalid": 0},
                    "requiredChecks": {"tests": "passed"},
                    "base": {"baseRef": "main", "baseSha": "…", "mergeBaseSha": "…", "behindBy": 0,
                             "observedAt": 1760000000.0, "fresh": true},
                    "template": {"missing": []}},
 "reviewGate": {"status": "pending|blocked|ready", "openImportant": 0,
                "requiredHumanApprovals": 1, "humanApprovalsAtHead": 0, "reasons": []}}
```

`reviewJobId`, `round` a `riskTier` patří úloze druhu `code`. Klíče `mergeReadiness` jsou
přítomné jen u zapnutých pravidel (`security` je `null` při vypnutém bezpečnostním review).

Lidská schválení se berou jen z uložených [GitHub důkazů](oporahub-github.md):
nejnovější úplný snímek PR **s hlavou rovnou aktuálnímu `headSha`**, se stejnými
pravidly jako hodnocení důkazů (účet typu User s oprávněním write/maintain/admin,
ne autor PR, rozhoduje poslední rozhodnutí reviewera, schválení musí mít `commitId`
= hlava). Účty z `agent_account_ids` a boti se nepočítají. Schválení starší hlavy
se po novém commitu nepočítá. Důkazy se nenačítají automaticky; načtěte je
v OporaHubu (GitHub důkazy) po schválení. Jakmile má projekt ověřené lidské identity,
brána počítá **různé ověřené lidi** včetně člověka, který řídil běh
([lidé v review](oporahub-review-identity.md)); pak přibude `reviewGate.humans`.

| Důvod | Stav |
|---|---|
| `review_round_cap_reached`, `open_important_findings`, `changes_requested`, `invalid_review_evidence` | `blocked` |
| `open_security_findings`, `self_checks_failed`, `required_checks_failed` | `blocked` |
| `review_not_enqueued`, `review_in_progress`, `human_approvals_missing`, `github_evidence_missing`, `github_evidence_stale_head` | `pending` |
| `security_review_not_enqueued`, `security_review_in_progress`, `self_checks_missing`, `required_checks_pending`, `base_freshness_unobserved`, `stale_against_main`, `template_unobserved`, `template_incomplete` | `pending` |

Bez úlohy pro aktuální hlavu se požaduje úroveň `high`. `ready` znamená jen, že
podmínky této brány jsou splněny; nemerguje, nepřijímá plán ani neuzavírá kartu.

## Pravidla brány

Čtyři pravidla nad bránou review kódu (`backend/canvas/opora_review_gate_rules.py`). Každé
přidává jen své důvody do `reviewGate.reasons` a svá fakta do `mergeReadiness`; `ready` znamená,
že žádné pravidlo nic nehlásí. Všechno je deterministické čtení uložených faktů, bez modelu.

### Bezpečnostní review

Samostatný blokující druh úlohy `kind: "security"` vedle review kódu (kontrakt pracovníka viz
[druh úlohy](#druh-úlohy-kind)). Při každém `sync` se pro každou otevřenou hlavu PR jednou
rozhodne, zda bezpečnostní review potřebuje; důvody se uloží do `job.risk.securityReasons`:

- `risk_tier:<tier>`: riziko změny (stejné [pravidlo rizika](#riziko-ze-změny)) je aspoň
  `security.min_tier`; nečitelná změna je `high`, tedy vždy bezpečnostní review;
- `security_path:<glob>`: změna zasahuje do cesty ze `security.paths`;
- `open_security_findings`: PR má otevřený bezpečnostní nález (další kolo může potvrdit opravu).

Hlava bez důvodu dostane značku `phase: "not_required"` (bez volných slotů, nikdy se
nepřebírá), aby se rozhodnutí neopakovalo. Bezpečnostní nález = nález vzniklý z úlohy druhu
`security` (`finding.reviewJobId` → `job.kind`). Otevřený bezpečnostní nález `important`
→ `open_security_findings` (`blocked`); počítá se i do `openImportant`. Blok se **uvolní sám**:
v pozdější hlavě hledač nahlásí `fixed` s `findingId` a ověřovatelé to potvrdí
(`requiredVotes`), nález je `fixed` a důvod zmizí bez zásahu člověka. Člověk může nález
dál vypořádat s důvodem přes `POST /findings/{id}/resolve` (agent `important` nesmí).
Dokud bezpečnostní úloha hlavy běží: `security_review_in_progress`; bez rozhodnutí pro
hlavu: `security_review_not_enqueued` (obojí `pending`). Bezpečnostní kola nemají strop;
vznikají jen pro hlavy, které je vyžadují.

### Důkaz vlastních kontrol

Před žádostí o merge agent doloží, že na **aktuální hlavě** spustil kontroly ze
`self_checks.required` (testy, build, lint …). Je to tvrzení agenta, ne nezávislé ověření.
Tvar (`backend/canvas/opora_review_self_checks.py`, přísná validace, neznámé klíče se odmítnou):

```json
{"headSha": "<40 znaků malé hex>",
 "checks": [{"name": "tests", "command": "uv run pytest backend", "exitCode": 0, "status": "passed",
             "summary": "1234 passed", "output": "… posledních ≤ 4000 znaků …", "durationSeconds": 312.5}]}
```

`name` `[a-z0-9][a-z0-9_.:-]{0,63}`, jedinečné; `command` 1–1000 znaků; `status`
`passed|failed|skipped`; `passed` právě když `exitCode == 0`, `failed` pro nenulový kód,
`skipped` má `exitCode: null`; `summary` ≤ 500, `output` ≤ 4000 znaků; 1–30 kontrol.

Zdroje (rozhoduje nejnovější platný záznam pro aktuální `headSha`):

1. výsledek běhu navázaného na PR: `POST /api/oporahub/executions/{id}/results` s
   `result.selfChecks` (vedle povinného `summary`);
2. dodatek pro pozdější hlavu (oprava review, rebase): `POST /api/oporahub/review-jobs/self-checks`
   s `{project, workspace, executionId, selfChecks}`, identita agenta nebo člověka. Přijme se jen
   pro otevřené PR běhu a jen pro jeho aktuální hlavu; první záznam pro (běh, hlavu) platí,
   stejný obsah je idempotentní, jiný `409`.

Chybí záznam pro hlavu, chybí povinné jméno nebo je záznam neplatný → `self_checks_missing`
(`pending`, `invalid` počítá neplatné záznamy); povinná kontrola `failed`/`skipped`
→ `self_checks_failed` (`blocked`).

### Fronta merge

`ready` jen tehdy, když povinné CI kontroly prošly na commitu, jehož základ je **aktuální hlava
cílové větve**. Při `sync` (nejvýše jednou za `observe_interval_seconds` na PR, mimo zámky) čte
`backend/integrations/github_pr_base_reader.py` jen přes GET: `GET /repos/{r}/pulls/{n}` (hlava,
`base.ref`, popis) a compare API `GET /repos/{r}/compare/{base.ref}...{headSha}`. `base_commit.sha`
je aktuální hlava cílové větve, `merge_base_commit.sha` merge-base hlavy PR s ní.

- Pozorování chybí, patří jiné hlavě, je neúplné nebo starší než `base_max_age_seconds`
  → `base_freshness_unobserved` (`pending`, selhání nikdy nepustí dál).
- `merge_base_commit != base_commit` (`behind_by > 0`) → `stale_against_main` (`pending`) a
  v [agent-state](oporahub-agent-state.md) akce `pr.update_branch`; údržba PR v agent-office
  větev rebasuje (ekvivalent `PUT /repos/{r}/pulls/{n}/update-branch` s `expected_head_sha`).
  Nová hlava znovu projde review, vlastními kontrolami i CI.
- Každé jméno z `merge_queue.required_checks` se hledá v nejnovějším úplném
  [GitHub důkazu](oporahub-github.md) aktuální hlavy (poslední check run nebo status context
  toho jména): selhalo → `required_checks_failed` (`blocked`), chybí / běží / neznámé →
  `required_checks_pending`. Prázdný seznam kontroly nevyžaduje.

**Nativní merge queue GitHubu** (volitelně navíc): v repozitáři *Settings → Rules → Rulesets*
(nebo *Branches → Branch protection*) pro `main` zapněte *Require status checks to pass*
se stejnými jmény jako `merge_queue.required_checks` a *Require merge queue* (metoda
squash, *Only merge non-failing pull requests*). Workflow CI musí reagovat i na událost
`merge_group` (`on: [pull_request, merge_group]`), jinak fronta čeká navždy. GitHub pak
sám testuje sloučení s aktuální hlavou `main`; brána Canvasu zůstává podmínkou pro zařazení
do fronty, ne náhradou. Canvas na GitHub nezapisuje ani do fronty nic neřadí.

### Šablona PR

`.github/pull_request_template.md` předvyplní sekce `## Testing`, `## Risk` a `## Revert plan`
(nápovědy jsou HTML komentáře). Sekce ze `template.sections` se počítá jen jako Markdown
nadpis libovolné úrovně se stejným jménem (bez ohledu na velikost písmen a mezery), pod
kterým je skutečný text; komentáře, prázdné odrážky a zaškrtávátka nejsou text. Popis se
čte s pozorováním cílové větve a ukládají se jen jména vyplněných sekcí. Chybějící sekce
→ `template_incomplete`, nepřečtený popis → `template_unobserved`; obojí jen `pending`
(čeká, neblokuje).

### Diagram PR Lens (volitelný důkaz)

Pracovník, který změnu udělal, ji nakreslí lokálně přes PR Lens (`docs/cista-linie.md` §4):
**spec** (validovaný graf: pruhy, karty s cestami a řádky, hrany, kroky toků s payloady) je
zdroj pravdy, který čtou agenti jako data; SVG je jen pro lidi. Agent Office spec i SVG vystaví
na vedlejší větvi `pr-lens/<větev PR>` a pošle
`POST /api/oporahub/review-jobs/lens` s `{project, workspace, executionId, lens: {url, prNumber,
headSha, validatedAt, specUrl?, specSha256?, specBytes?, spec?}}`. `url` a `specUrl` jsou jen
`https` na `github.com` (i `github.com/user-attachments/…`) nebo `raw.githubusercontent.com`;
`spec` je graf (`kind: graph`) do 64 KiB, `specBytes` nejvýš 512 KiB. Platí jen pro otevřený
propojený PR a jeho aktuální hlavu (`prNumber` a `headSha` musí sedět, jinak 409); první zápis
na hlavu vyhrává, stejný obsah je idempotentní. Nevyžaduje zapnuté review úlohy.

Brána ho jen ukazuje: u PR s diagramem pro aktuální hlavu má položka brány
`evidence.review.lens`, ale **nepřidává žádný důvod** a pořadí pravidel (self_checks →
security → findings → humans → freshness → template) se nemění. Agenti čtou spec karty přes
`GET /api/oporahub/review-lens?project&workspace&nodeId` (nejnovější diagram běhů karty,
`current` říká, zda je pro aktuální hlavu PR). Kód `backend/canvas/opora_review_lens.py`,
router `opora_review_lens_routes.py`, tabulka `opora_review_lens`
(`database/schema/opora_review_gate_schema.py`), testy `test_opora_review_lens.py` a
`test_opora_review_lens_routes.py`.

## Stav pro agenty

Při zapnuté funkci [agent-state](oporahub-agent-state.md) etapa `review` čte brány
otevřených PR: některá `blocked` → `blocking/review_gate_blocked`, některá ne-`ready`
→ `waiting/review_gate_pending`, jinak původní pravidla. Drží-li bránu některé
[pravidlo brány](#pravidla-brány), důvodem etapy je přímo jeho kód (např.
`blocking/open_security_findings`, `waiting/stale_against_main`, `waiting/self_checks_missing`;
pořadí v [agent-state](oporahub-agent-state.md)). Akce `pr.update_branch` (hlava za cílovou
větví) a `review.self_checks` (chybí důkaz pro hlavu) nesou přesné `preconditions`. Akce `review.claim`
(`POST /api/oporahub/review-jobs/claim`, `targetId` = `reviewJobId`, `preconditions`
`{role, headSha}`) je u každé úlohy s volným slotem. Mezera `ai_review` zmizí.
Vypnutá funkce dokument nemění. Čtení zůstává bez zápisu.

## Kontrakt pracovníka (agent-office)

Prefix `/api/oporahub/review-jobs`. Identita jako u execution API: hlavička
`X-Opora-Actor: agent; name=<pracovník>` (vlastník `agent:<name>`), člověk UI session;
bez identity `428`. Zápisy jsou JSON se stejným `Origin`. `project` a `workspace`
jsou vždy výslovné. Konflikty a neplatná data `409` (`code: review_conflict`),
vypnutá funkce `409` (`review_jobs_disabled`), jen pro člověka `403`
(`human_required`), neznámý nález `404`. Token je oprávnění slotu: nepatří do logů,
promptu, GitHubu ani veřejného stavu.

| Cesta | Tělo | Odpověď |
|---|---|---|
| `POST /claim` | `{project, workspace, requestId, ttlSeconds (30–3600), role?: "finder"\|"voter"}` | `{task: null, serverNow}` nebo `{task: Assignment, serverNow}` |
| `POST /{reviewJobId}/tasks/{taskId}/heartbeat` | `{project, workspace, token, epoch, ttlSeconds}` | `{reviewJobId, taskId, epoch, expiresAt, serverNow}` |
| `POST /{reviewJobId}/tasks/{taskId}/release` | `{project, workspace, token, epoch}` | `{…, state}` |
| `POST /{reviewJobId}/tasks/{taskId}/submit` | `{project, workspace, token, epoch, requestId, submission}` | `{reviewJobId, taskId, role, state: "submitted", phase, serverNow}` |
| `POST /findings/{findingId}/resolve` | `{project, workspace, reason}` | Nález; `important` jen člověk |
| `POST /decisions` | `{project, workspace, repository, number, headSha, reason}` | Jen člověk, jen pro hlavu za stropem kol |
| `POST /sync` | `{project, workspace}` | `{created: [reviewJobId]}` |
| `GET /?project&workspace` | – | `{enabled, maxRounds, jobs[], findings[]}` bez tokenů |
| `GET /gates?project&workspace` | – | `{items: [gate]}` |
| `POST /self-checks` | `{project, workspace, executionId, selfChecks}` | `{executionId, headSha, status}`; jen aktuální hlava otevřeného PR běhu |

`Assignment = {reviewJobId, taskId, role, slot, token, epoch, expiresAt, serverNow,
job, knownFindings, candidates?}`; `job = {reviewJobId, kind, executionId, cardId,
repository, number, baseSha, headSha, round, sinceSha, riskTier, risk,
requiredHumanApprovals, finders, voters, requiredVotes, phase, …}`. `baseSha` může
být `null` (změna nešla přečíst): pracovník pak použije merge-base s cílovou větví.
`knownFindings` jsou všechny nálezy PR včetně `findingId`, `fingerprint`, `status`;
hledač je nesmí opakovat. `candidates` (jen `voter`) jsou
`{candidateId, kind: "finding"|"fix", fingerprint?, path?, line?, severity?, title?,
rationale, findingId?, finders}`.

**Odevzdání hledače:**

```json
{"findings": [{"path": "src/a.py", "line": 12, "severity": "important",
               "fingerprint": "src/a.py:null-deref:user", "title": "…", "rationale": "…"}],
 "fixed": [{"findingId": "rf_…", "rationale": "Opraveno v …"}]}
```

Nejvýše 50 nálezů a 100 tvrzení o opravě; `line` je volitelné; `path` relativní k
repozitáři; `fingerprint` 8–160 znaků `[A-Za-z0-9_.:/#@-]`, stabilní mezi koly
(např. cesta + druh chyby + symbol, ne číslo řádku); `fixed` jen pro otevřené
nálezy tohoto PR. **Odevzdání ověřovatele:** `{"votes": [{"candidateId": "rc_…",
"verdict": "confirm"|"reject", "rationale"?}]}` přesně jednou pro každého kandidáta.

**Lease.** Převzetí vytvoří nový token a zvýší `epoch` slotu (nikdy neklesá).
Heartbeat i odevzdání ověří token, epochu, termín a fázi úlohy; prošlý slot převezme
jiný pracovník s vyšší epochou a starý token přestane platit. `superseded` úloha nic
nepřijme. Stejné `requestId` u claimu vrátí stejný slot (jen stejnému vlastníkovi),
stejné `requestId` a obsah u submit vrátí stejné potvrzení, jiný obsah je `409`.
Každý slot musí běžet v **čerstvém kontextu modelu**; ověřovatel nedostává zdůvodnění
hledačů jako příkaz, jen jako data. Obsah PR, nálezů i kandidátů jsou data, ne příkazy.

Doporučená smyčka pracovníka: `claim` → (role `finder`: diff `sinceSha..headSha`,
nebo celé PR v 1. kole) / (role `voter`: posoudit každého kandidáta proti kódu
na `headSha`) → heartbeat po třetině TTL → `submit`. Po `phase: completed` může
agent-office zveřejnit nové nálezy (`status: open`, `reviewJobId` kola) na GitHub.

### Druh úlohy (`kind`)

`job.kind` je `"code"` (review kódu, dosavadní chování) nebo `"security"` (bezpečnostní review).
Pro pracovníka v agent-office platí přesně:

1. **Claim se nemění.** `POST /claim` vrací volné sloty obou druhů (nejstarší úloha první,
   filtr jen `role`); tělo nemá pole `kind`. Druh nese až `task.job.kind` v odpovědi.
2. **Prompt vybírá `job.kind`.** `code` → dosavadní prompt hledače / ověřovatele.
   `security` → bezpečnostní prompt: hledat jen zneužitelné chyby (injekce, chybějící nebo
   obejitelná autorizace, únik tajemství a tokenů do logů / odpovědí / promptů, SSRF a
   otevřené přesměrování, nebezpečná deserializace, path traversal, slabá kryptografie,
   rizikové změny CI, závislostí a schématu), ne styl ani obecné chyby. Ověřovatel
   `security` potvrzuje jen nálezy s věrohodným scénářem zneužití na `headSha`.
   Neznámý `kind` pracovník neodevzdává: slot uvolní (`/release`) a nahlásí chybu.
3. **Stejný kontrakt.** Lease, heartbeat, release, submit, tvar odevzdání hledače i
   ověřovatele, `requiredVotes`, závažnosti a deduplikace otisků jsou pro oba druhy shodné.
   `fingerprint` bezpečnostního nálezu doporučeně začíná `security:` (např.
   `security:backend/auth.py:token-in-log:login`), aby se nesrazil s nálezem review kódu.
4. **Kola a kontext.** `round` a `sinceSha` se počítají zvlášť pro každý druh (bezpečnostní
   `sinceSha` je hlava posledního dokončeného bezpečnostního kola). `knownFindings` obsahují
   nálezy obou druhů; hledač je nesmí opakovat a smí v `fixed` označit kterýkoli otevřený
   nález PR. `job.risk.securityReasons` říká, proč bezpečnostní review běží
   (`risk_tier:*`, `security_path:*`, `open_security_findings`).
5. **Značka `not_required`.** Úloha `security` ve fázi `not_required` jen zaznamenává, že hlava
   bezpečnostní review nepotřebuje; nemá volné sloty a v `GET /` se jen zobrazí.
6. **Zveřejnění.** Nález patří druhu úlohy, ze které vznikl (`finding.reviewJobId` → `job.kind`
   v `GET /`); agent-office ho na GitHubu označí jako bezpečnostní. Otevřený `important`
   bezpečnostní nález blokuje bránu (`open_security_findings`), dokud ho pozdější kolo
   nepotvrdí jako `fixed` nebo ho člověk nevypořádá s důvodem.

## Kód a ověření

Schéma `database/schema/opora_review_job_schema.py`, úložiště
`database/repositories/opora_review_jobs.py`; služby `backend/canvas/opora_review_jobs.py`
(zařazení), `opora_review_job_tasks.py` (lease a fáze), `opora_review_aggregation.py`
(čistá agregace), `opora_review_findings.py`, `opora_review_gate.py`, `opora_review_risk.py`,
`opora_agent_state_reviews.py`; čtení GitHubu `backend/integrations/github_pr_change_reader.py`;
router `backend/api/editor/opora_review_job_routes.py`.

Pravidla brány: konfigurace `opora_review_gate_config.py`, skladba `opora_review_gate_rules.py`,
`opora_review_security.py`, `opora_review_self_checks.py`, `opora_review_merge_queue.py`,
`opora_review_template.py`, etapa agent-state `opora_agent_state_review_gates.py`; schéma a
migrace sloupce `kind` `database/schema/opora_review_gate_schema.py`, úložiště
`database/repositories/opora_review_gate_facts.py`; čtení cílové větve
`backend/integrations/github_pr_base_reader.py`; router `opora_review_self_check_routes.py`.
Testy `test_opora_review_security.py` (zařazení, stejný kontrakt, blok a jeho automatické
uvolnění potvrzenou opravou), `test_opora_review_self_checks.py` (validace tvaru, zdroje,
nová hlava), `test_opora_review_merge_queue.py` (`stale_against_main`, akce `pr.update_branch`,
povinné kontroly, stáří pozorování, šablona), `test_github_pr_base_reader.py`,
`test_opora_review_gate_schema.py` (migrace) a `test_opora_review_self_check_routes.py`.

`uv run pytest backend/canvas/test_opora_review_risk.py backend/canvas/test_opora_review_jobs.py
backend/canvas/test_opora_review_gate.py backend/api/editor/test_opora_review_job_routes.py
backend/integrations/test_github_pr_change_reader.py` pokrývá idempotentní zařazení,
lease/epochu, agregaci hlasů, deduplikaci otisků mezi koly, inkrementální `sinceSha`,
strop kol a lidské rozhodnutí, pravidla rizika, schválení staré hlavy, nezapočtení
agentů a čtení agent-state bez zápisu.
