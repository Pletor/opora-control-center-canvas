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
nejvýše 3 kola a další kola hlídají jen nový diff bez opakování nálezů.

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
| `approvals.low/medium/high` | 0 / 1 / 2 | Požadovaná lidská schválení |
| `approvals.sensitive_minimum` | 1 | Citlivá změna vždy aspoň tolik schválení |
| `approvals.agent_account_ids` | `[]` | Číselná GitHub ID účtů agentů; jejich schválení se nepočítají |

## Riziko ze změny

Při zařazení úlohy server mimo zámky přečte (jen GET) PR a jeho soubory
(`/pulls/{n}/files`, nejvýše 3 stránky po 100) a ověří, že hlava PR před i po čtení
je přesně SHA úlohy. Přejmenování počítá starou i novou cestu.

1. Změnu nejde přečíst, je neúplná, hlava se pohnula, nebo projekt nemá GitHub
   → `high` (`change_unobserved`), tj. 2 schválení. Selhání nikdy nesnižuje riziko.
2. Řádky ≥ `high_lines` nebo soubory ≥ `high_files` → `high` (`large_change`);
   ≥ medium prahy → `medium` (`medium_change`); jinak `low` (`small_change`).
3. Zásah do citlivé cesty zvedne úroveň aspoň na `medium` a přidá důvod
   `sensitive_path:<glob>`; požadavek je aspoň `sensitive_minimum`.

Úroveň se ukládá do úlohy (`riskTier`, `risk.reasons`) a nemění se zpětně.

## Životní cyklus úlohy

Úloha vzniká pro každé otevřené PR vazby běhu s novým `headSha`. Zařazení spouští
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
 "reviewGate": {"status": "pending|blocked|ready", "openImportant": 0,
                "requiredHumanApprovals": 1, "humanApprovalsAtHead": 0, "reasons": []}}
```

Lidská schválení se berou jen z uložených [GitHub důkazů](oporahub-github.md):
nejnovější úplný snímek PR **s hlavou rovnou aktuálnímu `headSha`**, se stejnými
pravidly jako hodnocení důkazů (účet typu User s oprávněním write/maintain/admin,
ne autor PR, rozhoduje poslední rozhodnutí reviewera, schválení musí mít `commitId`
= hlava). Účty z `agent_account_ids` a boti se nepočítají. Schválení starší hlavy
se po novém commitu nepočítá. Důkazy se nenačítají automaticky; načtěte je
v OporaHubu (GitHub důkazy) po schválení.

| Důvod | Stav |
|---|---|
| `review_round_cap_reached`, `open_important_findings`, `changes_requested`, `invalid_review_evidence` | `blocked` |
| `review_not_enqueued`, `review_in_progress`, `human_approvals_missing`, `github_evidence_missing`, `github_evidence_stale_head` | `pending` |

Bez úlohy pro aktuální hlavu se požaduje úroveň `high`. `ready` znamená jen, že
podmínky této brány jsou splněny; nemerguje, nepřijímá plán ani neuzavírá kartu.

## Stav pro agenty

Při zapnuté funkci [agent-state](oporahub-agent-state.md) etapa `review` čte brány
otevřených PR: některá `blocked` → `blocking/review_gate_blocked`, některá ne-`ready`
→ `waiting/review_gate_pending`, jinak původní pravidla. Akce `review.claim`
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

`Assignment = {reviewJobId, taskId, role, slot, token, epoch, expiresAt, serverNow,
job, knownFindings, candidates?}`; `job = {reviewJobId, executionId, cardId,
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

## Kód a ověření

Schéma `database/schema/opora_review_job_schema.py`, úložiště
`database/repositories/opora_review_jobs.py`; služby `backend/canvas/opora_review_jobs.py`
(zařazení), `opora_review_job_tasks.py` (lease a fáze), `opora_review_aggregation.py`
(čistá agregace), `opora_review_findings.py`, `opora_review_gate.py`, `opora_review_risk.py`,
`opora_agent_state_reviews.py`; čtení GitHubu `backend/integrations/github_pr_change_reader.py`;
router `backend/api/editor/opora_review_job_routes.py`.

`uv run pytest backend/canvas/test_opora_review_risk.py backend/canvas/test_opora_review_jobs.py
backend/canvas/test_opora_review_gate.py backend/api/editor/test_opora_review_job_routes.py
backend/integrations/test_github_pr_change_reader.py` pokrývá idempotentní zařazení,
lease/epochu, agregaci hlasů, deduplikaci otisků mezi koly, inkrementální `sinceSha`,
strop kol a lidské rozhodnutí, pravidla rizika, schválení staré hlavy, nezapočtení
agentů a čtení agent-state bez zápisu.
