# Stav pro agenty: jeden deterministický dokument

Agent dosud skládal obraz OporaHubu z přibližně čtrnácti endpointů a sám usuzoval,
co dál. `GET /api/oporahub/agent-state?project=<id>&workspace=<id>[&cardsOffset=<n>]` vrací jeden
strojově čitelný dokument: přesné hlavy pro CAS, zdraví každé etapy smyčky,
rozhodnutí čekající na člověka a seznam připravených či blokovaných akcí. Další
krok počítá backend podle pevných pravidel, ne jazykový model. Stejná data budou
podkladem lidské infografiky (návrh „OporaHub — přehled“ v Claude Design).

Dokument je **jen ke čtení**: neprovádí claim, přijetí ani přechod stavu a nezapisuje
do SQLite. Skládá existující služby (`OporaChangesets`, `ProcessSync`,
`OporaExecutions`, seznamy návrhů a `classify_risk`) pod zámky projektu, takže jde
o konzistentní snímek. Akce nejsou oprávnění: každý zápis dál ověří původní API.

Po dobu skládání drží zámky projektu, takže na něj čeká každý claim, heartbeat i zápis.
Skládání proto běží v jednom bloku `steady_reads` a celoprojektová fakta (přijatý kontext,
uložený stav Desktop v3, ověření přijatého grafu a obsahu, redigované karty specifikace)
počítá jednou na dokument přes `CanvasService.steady_value`, ne znovu pro každou kartu.
Hlídá to `backend/canvas/test_opora_agent_state_budget.py`.

Kód: `backend/canvas/opora_agent_state.py` (skládání), `opora_agent_state_rules.py`
(konstanty a pravidla zdraví), `opora_agent_state_pulls.py` (volitelná vazba na PR)
a router `backend/api/editor/opora_agent_state_routes.py`.

## Tvar odpovědi (`schemaVersion: 1`)

| Pole | Význam |
|---|---|
| `generatedAt` | Čas sestavení (UTC, sekundy); jediné pole mimo ETag |
| `projectId`, `workspaceId` | Rozsah dokumentu |
| `heads` | `acceptedHead`, `acceptedRevision` (alias téže hlavy pro execution API), `graphDigest`, `workingDiffers`, `contextVersion` (verze pracovních zadání prostoru, `specificationsVersion`) a `budgetPolicyHead` (mapa karta → hlava pravidel běhů; pravidla jsou per karta) |
| `stages[]` | Pořadí `plan, proposal, acceptance, claim, work, evidence, review, pull_request, merge, plan_writeback`; každá `{id, count, health, reason}` |
| `riskMix` | `{low, elevated, critical}` nepřijatých a nenahrazených návrhů podle serverového rizika (`standard` → `low`) |
| `decisions[]` | Nejvýše 3 rozhodnutí člověka `{id, kind, targetId, title, actionId}` |
| `actions[]` | `{id, verb, method, path, targetId, preconditions, status, blockReason?, budget?, command?}`; `command` jen u `ready` akce: hotový řádek `opora_hub.py start --node N` (claim) nebo `opora_hub.py act --action-id ID`, `null` u akce, kterou klient sám neprovádí |
| `gaps[]` | Známé nenapojené schopnosti `{id, stage, reason}` |
| `cards[]` | Etapa karty `{nodeId, stage, health, reason, executionId, kind, layer, order, blockedBy, topoIndex, nextActionId, gate, lease, lastEventAt, pr?}`, nejvýše 100 na stránku, seřazené podle [důležitosti](#strop-a-stránkování-karet) a uvnitř podle `nodeId` (viz [Etapa karty](#etapa-karty-cards) a [Graf karet](#graf-karet-dag)); `lastEventAt` je čas (`at`, ISO) nejnovější události karty v prostoru, `null` bez události |
| `truncated` | `cards[]` neobsahuje všechny karty prostoru (další stránka existuje nebo `cardsOffset > 0`); `actions`, `decisions`, `stages` a `heads` jsou přesto vždy úplné |
| `cardsTotal` | Počet všech karet (uzel, sektor) prostoru |
| `cardsNextOffset` | Hodnota `cardsOffset` pro další stránku `cards[]`, `null` na poslední stránce |
| `mapGaps`, `mapGapsTotal`, `guards` | [Díry mapy](#díry-mapy-jako-práce-mapgaps) a [nálezy strážců](#nálezy-strážců-guards) |
| `eventsCursor` | Kurzor [toku událostí](oporahub-events.md) (`id` poslední události outboxu, `0` bez událostí) přečtený ve **stejném snímku** jako zbytek dokumentu (viz [Podmíněné čtení](#podmíněné-čtení)) |

`health` je `ok`, `waiting`, `blocking` nebo `not_connected`. `reason` je strojový kód.
Pořadí polí, etap, akcí (podle slovesa a `targetId`) i mezer je stabilní.

## Pravidla zdraví

Pravidla platí v uvedeném pořadí; konstanty jsou v `opora_agent_state_rules.py`.

| Etapa | Pravidlo |
|---|---|
| `plan` | Žádná karta → `waiting/empty_plan`; read-only prostor (čistý `main` git projektu, jen architektura) → `ok/read_only_architecture` a žádné `accept_baseline` ani `propose_graph`; bez přijatého základu → `blocking/no_accepted_baseline`; pracovní zadání se liší → `waiting/working_differs_from_accepted`; jinak `ok` |
| `proposal` | Se zapnutým [automatickým rebase](oporahub-auto-rebase.md): otevřený konflikt → `waiting/auto_rebase_conflicts`; zastaralý návrh, který smyčka nevyřídila (ne redundantní, bez vyřešeného konfliktu) → `waiting/stale_proposals`. S `OPORA_AUTO_REBASE=0`: nepřijatý a nenahrazený návrh s jiným rodičem než přijatou hlavou → `waiting/stale_proposals` |
| `acceptance` | Chybějící základ → `waiting/baseline_awaiting_human`; čerstvý návrh starší než `ACCEPTANCE_WAIT_SECONDS` (24 h) → `waiting/acceptance_overdue`; mladší → `ok/awaiting_human_within_window` |
| `claim` | Počítá karty `ready`; vyčerpané pokusy nebo opravy → `blocking/budget_exhausted` |
| `work` | Poslední běh karty ve stavu `running` s termínem (pronájem nebo pevný konec rozpočtu) v minulosti → `blocking/lease_past_deadline`; mrtvý běh bez výsledku, jehož karta znovu nabízí `claim`, se nepočítá |
| `evidence` | Nahlášený výsledek je zastaralý → `waiting/stale_evidence`. Zastaralý je jen tehdy, když se od claimu změnil **výřez karty**, na kterém stálo zadání běhu (vlastní a související zadání, kroky, vlastní vazby `next`, předávka), stejně jako běh v [`active`](oporahub-executions.md) (`OporaExecutions.slice_changed`: v1 digest živého zadání s hlavou z claimu, v2 linie přijatého výřezu). Přijatá změna plánu jinde (nová karta, unlink, prune) výsledek nezastará; zavřená karta a přepočet události bez canvasu (běh v1 v `stage.changed`) dál porovnávají přijatou hlavu |
| `review` | Se zapnutým [automatickým review](oporahub-review-jobs.md): brána otevřeného PR `blocked` → `blocking/review_gate_blocked`, ne-`ready` → `waiting/review_gate_pending`; když bránu drží [pravidlo brány](oporahub-review-jobs.md#pravidla-brány), důvodem etapy je přímo jeho kód (blokující v pořadí `open_security_findings`, `self_checks_failed`, `required_checks_failed`; čekající v pořadí `stale_against_main`, `self_checks_missing`, `security_review_not_enqueued`, `security_review_in_progress`, `required_checks_pending`, `base_freshness_unobserved`, `template_unobserved`, `template_incomplete`); pak nahlášený nezastaralý výsledek (viz `evidence`) na nepotvrzené kartě → `waiting/human_review_required` |
| `pull_request` | Bez modulu vazby → `not_connected`; výsledek bez PR → `blocking/results_without_pull_request` |
| `merge` | Bez modulu → `not_connected`; otevřené PR → `waiting/pull_requests_open` |
| `plan_writeback` | Bez modulu nebo bez hlášení `planWrittenBack` → `not_connected`; mergnuté PR bez zápisu do plánu → `waiting/merged_without_plan_writeback` |

Počítá se jen poslední běh každé karty (jako v [procesu Control Center](oporahub-process-sync.md));
starší běhy jsou historie, ne nová blokace.

## Etapa karty (`cards[]`)

Plátno Editoru ukazuje u každé karty malý odznak etapy ze stejného čtení jako přehled
(`backend/canvas/opora_agent_state_cards.py`, čistá funkce nad už sebranými fakty). Karta stojí
v nejvzdálenější dosažené etapě; platí první pravidlo:

| Podmínka | `stage` / `health` / `reason` |
|---|---|
| karta potvrzena (`done.confirmed`) | `plan_writeback` / `ok` / `card_closed` |
| PR sloučeno a čeká na uzavření člověkem | `merge` / `waiting` / `awaiting_human_close` |
| PR sloučeno se zápisem / bez zápisu do plánu | `plan_writeback` / `ok` / `plan_written_back`, jinak `waiting` / `merged_without_plan_writeback` |
| otevřené PR s bránou review | `review` se zdravím brány (`blocked` → `blocking`, `pending` → `waiting`, `ready` → `ok`) a důvodem pravidla, které bránu drží (stejné pořadí jako etapa `review`), jinak `review_gate_ready` |
| otevřené PR bez brány | `pull_request` / `waiting` / `pull_requests_open` |
| poslední běh `running` | `work` / `ok` / `runs_active`, po termínu `blocking` / `lease_past_deadline`; mrtvý běh bez výsledku, jehož karta znovu nabízí `claim`, sem nepatří (viz níže) |
| poslední běh s výsledkem | změněný výřez karty (viz `evidence`) → `evidence` / `waiting` / `stale_evidence`, jinak `review` / `waiting` / `human_review_required`; historický výsledek (změněný výřez) na kartě, která znovu nabízí `claim`, sem nepatří (viz níže) |
| akce `claim` karty | `claim` / `ok` / `cards_ready`, blokovaná → `blocking` / `budget_exhausted`, `budget_policy_required` či `blocked_by_predecessor` |
| jinak | `plan` / `ok` / `card_in_plan` (bez přijatého základu `blocking` / `no_accepted_baseline`) |

Autoritou běhu je pronájem (`card_leases.expires_at`), ne stav v ledgeru: termín běhu `running` je nejdřívější
z konce v ledgeru, konce rozpočtu a pronájmu se stejným tokenem (bez něj je termín pryč). Mrtvý běh (bez výsledku,
bez aktivního pronájmu) projekce procesu nepočítá, karta je `ready` a dostane akci `claim`; etapa karty je pak
`claim` a etapa `work` ho nezapočítá. `lease_past_deadline` tak zůstává jen pro okno, kdy je termín pryč, ale
karta claim ještě nenabízí (např. hodiny čtení předběhnou čtení pronájmu, nebo karta claim nemá z jiného důvodu).

Stejně se předá zpět karta, jejíž poslední výsledek zastaral změnou vlastního výřezu (přeplánování, nový předchůdce):
projekce procesu ho bere jako historický, karta propadne připraveností a dostane akci `claim` (`ready`, nebo
`blocked_by_predecessor`, dokud předchůdce není hotový); etapa karty je `claim`. Dokud má karta otevřené nebo sloučené
PR, akce `claim` se nevydá a etapu drží PR. Rozpočet v2 se počítá na přijatou revizi, takže nová revize má nové
pokusy, ale zapsaná karta potřebuje novou politiku rozpočtu člověka (`budget_policy_required`).

`executionId` je běh, ke kterému etapa patří (u PR běh vazby), jinak `null`.

`pr` je `{number, state}` PR navázaného na kartu (`state` `open` | `merged` | `closed`, `number` je `null`
u lokálního sloučení bez GitHubu); plátno a Velín z něj kreslí odznak PR v barvách GitHubu. Pole chybí, když
karta PR nemá, když je karta uzavřená (`done.confirmed`) a u PR zavřeného bez sloučení, které nepatří
poslednímu běhu karty (nový běh je nový pokus). Bere se stejná vazba jako pro etapu (otevřené PR má přednost).

### Strop a stránkování karet

Akce, rozhodnutí a etapy se počítají ze **všech** karet prostoru (`ProcessSync.read(..., limit=None)`);
strop 100 (`CARD_LIMIT` v `opora_agent_state_cards.py`) platí jen pro výpis `cards[]`. Dřív se karty
ořízly už v projekci procesu v pořadí vzniku, takže karta za stou nedostala ani akci `claim`
a autopilot ji nikdy nepřevzal. Výpis je seřazený podle důležitosti, takže strop ubírá nejdřív
uzavřené karty:

| Pořadí | Karty |
|---|---|
| 0 | rozjeté: běh, důkazy, review, PR, merge, sloučené bez zápisu do plánu |
| 1 | `claim` / `cards_ready` |
| 2 | blokovaný `claim` (`blocked_by_predecessor`, rozpočet) |
| 3 | `plan` (v plánu, bez akce) |
| 4 | uzavřené (`card_closed`, `plan_written_back`) |

Zbytek agent dočte parametrem `cardsOffset=<cardsNextOffset>` (celé číslo `>= 0`, záporné → `422`):
stejný snímek akcí, jen další okno `cards[]`. Každá stránka má vlastní ETag (tělo se liší), takže
`If-None-Match` platí per stránka. Mezi stránkami se může stav změnit; rozhoduje vždy `actions[]`.

Stopu práce jedné karty (běhy dělníků s kroky a důkazy, poslední změny, zprávy na vazbách, příznaky
„potřebuje úsudek“) agent-state nenese; čte se zvlášť přes `GET /api/oporahub/card-trail`, viz
[stopa-prace-karty.md](stopa-prace-karty.md).

## Graf karet (DAG)

Vazby `next` (port chybí nebo je `next`) mezi kartami (uzel, sektor) tvoří orientovaný acyklický
graf: cílová karta navazuje na zdrojovou. `backend/canvas/card_dag.py` hlídá ukládání grafu
(`save_graph`, tedy i `POST /api/graph`, dávku plánu, krok zpět a obnovu verze): uložení, které
**přidá** vazbu uzavírající cyklus, skončí `409` s tělem
`{"error", "code": "card_cycle", "cycle": ["b", "a", "b"]}` (uzavřená cesta id karet). Cyklus už
uložený ve starých datech se toleruje, aby šel projekt otevřít a opravit; jeho karty dostanou
`topoIndex` až za acyklickou částí.

Pole karty v `cards[]` (`backend/canvas/opora_agent_state_dag.py`):

| Pole | Význam |
|---|---|
| `kind` | Typ workflow z předpony názvu (`research`, `prototype`, `grilling`, `task`, `gate`), jinak `null` |
| `layer` | Uložená vrstva `card.layer` (`frontend` / `backend` / `database` / `library`), jinak `null` |
| `blockedBy` | Seřazení předchůdci po `next`, kteří ještě nejsou hotoví: hotový = vazba PR `merged` s `planWrittenBack: true`, u starých dat `done.confirmed` |
| `order` | Uložené pořadí karty podle záměru (`order` uzlu, celé číslo 1–9999, doporučeně fáze × 100 + pozice), jinak `null`. Není závislost: nic neblokuje |
| `topoIndex` | Pořadí v topologickém řazení všech karet prostoru (Kahn, remízy podle `order`, karta bez něj jako 10000, pak podle id; vazby `next` mají přednost) |
| `nextActionId` | `id` první akce (v pořadí `actions[]`), jejíž `targetId` je karta nebo běh její etapy; jinak `null` |
| `gate` | `{status, rule}` brány review otevřeného PR karty (`rule` = kód pravidla podle priority etapy `review`, jinak první důvod brány), bez brány `null` |
| `lease` | `{holder, expiresAt, epoch}` posledního běhu karty ve stavu `running` s termínem (pronájem nebo pevný konec rozpočtu) v budoucnosti; jinak `null`. `holder` = vlastník claimu, `expiresAt` ISO UTC (`backend/canvas/opora_agent_state_lease.py`) |

Karta s neprázdným `blockedBy` má akci `claim` blokovanou důvodem `blocked_by_predecessor`
(rozpočtové důvody mají přednost) a nezapočítává se do `count` etapy `claim`. Endpoint claim
totéž vynucuje sám (`409 blocked_by_predecessor`).

### Kroky plánu v kartě

Každá položka `cards[]` nese `steps: {total, done, current, items}` (`opora_agent_state_steps.py`):
počet přijatých [kroků plánu](oporahub-plan-steps.md), počet hotových podle `stepResults` všech
běhů (hotový krok zůstává hotový), ID prvního nehotového kroku (`null`) a `items`
`[{id, status, executionId}]` po krocích v topologickém pořadí. Dále `dod` = [jediná definice
hotovo](oporahub-plan-steps.md#jediná-definice-hotovo): `{steps, card_acceptance, gate_ready, merged,
plan_written_back, journeys, human_close}` (booleany), `gate` (`review` / `external` / `local`, [lokální sloučení](lokalni-slouceni.md)), `done`, `missing`
(a `blockingJourneys`, když brání cesta zákazníka, `docs/brana-cesty.md` §5). Akce `claim` vzniká jen pro kartu s přijatými kroky;
stará pipeline `stages` připravenost neovlivňuje.

## Rozhodnutí a akce

Rozhodnutí formální pozornosti (`verification_counterexample`, `verification_failed`)
jdou vždy první. Modul `opora_agent_state_formal.py` je odvodí z úložiště ověření. Za nimi
řadí pevná priorita ostatní rozhodnutí: přijetí základu, přijetí návrhu `critical`, `elevated`,
`low` (uvnitř podle stáří), kontrola nahlášeného výsledku, uzavření karty po merge PR. Každé ukazuje na akci.

Akce ze všech zdrojů (základní pravidla, konflikty auto-rebase, brána review, formální pozornost, opakované nálezy)
řadí jeden seznam priorit `VERB_ORDER` v `opora_agent_state_rules.py` v pořadí tabulky níže,
uvnitř slovesa podle `targetId`; test hlídá, že tabulka a `VERB_ORDER` souhlasí.

| `verb` | Cíl | Stav |
|---|---|---|
| `propose_graph` | `POST /api/oporahub/graph-proposals` | `ready`, když karty mají zadání, ale přijatá revize nemá graf plánu (žádná, nebo jen `accept_baseline`) a čeká žádný návrh grafu; běh v2 bez grafu plánu nepřevezme (`409 graph_acceptance_required`). `preconditions` = celé tělo bez `project`/`workspace`: `{parentRevision, expectedGraphDigest, subject, plan: {nodes: [], edges: []}}`; prázdný plán převezme pracovní graf i zadání karet |
| `accept` | `…/{id}/accept` podle druhu návrhu | vždy `blocked/human_only`; `preconditions` = celé tělo bez `project`/`workspace` včetně převzetí základu (`adoptBaseGraphDigest`, `adoptBaseContentDigest`, `reviewed…Id`) |
| `accept_baseline` | `POST /api/oporahub/baselines` | vždy `blocked/human_only`; `preconditions` nesou i výchozí `subject` |
| `rebase` | `…/{id}/rebase` zastaralého návrhu | `ready` (výslovný převod; automatický běží na serveru) |
| `proposal.resolve_conflict` | `POST /api/oporahub/auto-rebase/conflicts/{id}/resolve` | `ready` u otevřeného konfliktu auto-rebase; řešením je běžný nový návrh nad aktuální hlavou |
| `claim` | `POST /api/oporahub/executions/claim` | `ready`, nebo `blocked/budget_exhausted`, `budget_policy_required` či `blocked_by_predecessor` (nedokončený předchůdce v grafu karet; ID akce se mění se sadou blokujících karet); `budget` nese zbývající pokusy a opravy |
| `review` | `GET /api/oporahub/executions/{id}/results` | `blocked/human_only` (AI review chybí) |
| `review.claim` | `POST /api/oporahub/review-jobs/claim` | `ready` u úlohy review s volným slotem (jen se zapnutým automatickým review); `preconditions` `{role, headSha}` |
| `review.self_checks` | `POST /api/oporahub/review-jobs/self-checks` | `ready`, když brána hlásí `self_checks_missing`; `targetId` = `executionId`, `preconditions` `{executionId, headSha, required}` |
| `pr.update_branch` | `PUT github:/repos/{owner}/{repo}/pulls/{n}/update-branch` (provede údržba PR v agent-office rebasem) | `ready`, když brána hlásí `stale_against_main`; `targetId` = `executionId`, `preconditions` `{repository, number, expectedHeadSha, baseRef, baseSha}` |
| `link_pull_request` | `POST /api/oporahub/executions/{id}/pull-request` | `ready` s modulem vazby, jinak `blocked/not_implemented` |
| `close_card` | `POST /api/desktop-v3/state` (`done.confirmed` karty) | jen když vazba hlásí `awaitingHumanClose` a karta ještě není potvrzená; `blocked/human_only`, když [definici hotovo](oporahub-plan-steps.md#jediná-definice-hotovo) chybí jen lidské uzavření, jinak `blocked/done_state_incomplete` bez rozhodnutí; `preconditions` = `{executionId, mergeSha, missing, gate}` (`gate` = `review` / `external` / `local`; vazbu dává i `local-merge`, [lokální sloučení](lokalni-slouceni.md)) |
| `verification.investigate` | `GET /api/oporahub/verifications/{id}` | `ready`; nejnovější CI check daného druhu (`formal/tlc`, `formal/lean`, `formal/conformance`, `formal-trusted/*`) běhu skončil `counterexample`, `failed` nebo `inconclusive` (viz [ověřování](oporahub-verification.md#automatické-ověřování-v-ci-etapa-3b)) |
| `verification.fix` | `POST /api/oporahub/verifications/{id}/fix-proposal` (`{project, workspace}`) | `ready` u `counterexample` a u `failed`, které není jen `runner_error`; idempotentně založí návrh karty „Opravit formální ověření“, přijímá člověk |
| `review.promote_to_check` | `POST /api/oporahub/review-recurring/promote` | `ready`, `attention: true`; třída nálezu se opakuje v ≥ N PR projektu a ještě není povýšená na kontrolu (viz [lidé v review](oporahub-review-identity.md)) |

Při plné autonomii je akce `blocked/human_only` pro agenta `ready` s `autonomy: "full"`
([plná autonomie](plna-autonomie-agenta.md)). U `propose_graph`, `accept_baseline` a `accept` stačí poslat
`{project, workspace, ...preconditions}`; neplatné tělo vrací `422` s `field`, `expected` a `example`.
`preconditions` obsahují přesné hodnoty k opakování v těle požadavku (`expectedAcceptedHead`,
`expectedGraphDigest`, `expectedContextVersion`, u protokolu v2 `expectedBudgetPolicyHead`
a `previousExecutionId`). Ostatní pole těla (důvod, `requestId`, `ttlSeconds`) doplní agent
podle kontraktu dané operace. `id` akce je `act_` + SHA-256 z `(verb, targetId, příslušná hlava)`:
u návrhů a přijetí je to přijatá hlava, u claimu `contextVersion` karty, u výsledků jejich
přijatá revize. Stejné ID znamená stejný úmysl; agent blokovanou akci se stejným ID
neopakuje a po změně hlavy dostane nové ID.

## Podmíněné čtení

Dokument je snímek; změny mezi snímky nese [tok událostí](oporahub-events.md)
(`GET /api/oporahub/events`, SSE `…/events/stream`). Čtení agent-state žádnou událost nevytváří.

`eventsCursor` a `cards[].lastEventAt` čte `backend/canvas/opora_agent_state_events.py` jedním
`SELECT MAX(id)` a jedním seskupeným `SELECT` na stejném spojení a pod stejným zámkem projektu
jako ostatní fakta dokumentu (zapisovatelé událostí drží tentýž zámek). Snímek tedy odráží právě
události do `eventsCursor` včetně: konzument přečte `agent-state`, otevře
`GET /api/oporahub/events/stream` s `Last-Event-ID: <eventsCursor>` a nic nezmešká ani nedostane dvakrát.

Odpověď nese silný `ETag` z těla bez `generatedAt` (`backend/api/http_etag.py`). `eventsCursor`
**v ETagu je**: nová událost znamená zápis, po kterém se snímek může lišit, a `304` tak vždy
vrací dvojici snímek + kurzor, která k sobě patří. Bez nových událostí a bez změny stavu dál
platí `304`.
Agent posílá `If-None-Match` a při nezměněném stavu dostane `304` bez těla.
Pravidla závislá na čase (`acceptance_overdue`, `lease_past_deadline`) změní tělo
i ETag, jakmile hranici překročí.

## Volitelná vazba execution → PR

Modul `backend/canvas/opora_execution_pull_requests.py` vzniká samostatně. Pokud jde
importovat, `opora_agent_state_pulls.py` zavolá jeho `list_execution_pull_requests`
(s `(project, workspace)` nebo `(canvas, project, workspace)` podle počtu parametrů)
a čte položky `executionId`, `state` (`open`/`merged`/`closed`) a volitelně
`planWrittenBack`, `cardId`, `mergeSha` a `awaitingHumanClose` (z té vzniká rozhodnutí
`close_card`). Výpis vazeb je čisté čtení snímku bez `BEGIN IMMEDIATE`, takže dokument
zůstává jen ke čtení i se skutečným modulem. Bez modulu jsou tři PR etapy `not_connected` a `gaps` obsahuje
`pull_request_link`. Testy podstrčí zdroj přes `register(...)`; žádná vazba se nevymýšlí.

## Díry mapy jako práce (`mapGaps`)

`mapGaps` (nejvýš 50) a `mapGapsTotal`: nálezy kontroly mapy nad přijatou architekturou projektu jako fronta
práce `{rule, message, nodeId, journeyId?, edgeId?, owner}`; `nodeId` je karta, na které se díra řeší,
`owner: "human"` u `page.no-goal` a `journey.broken`. Tvar a výběr řešitele:
[architektura pro agenty §5.1](architektura-pro-agenty.md). Nic se neodškrtává; díra zmizí, když ji kontrola
mapy přestane hlásit.

Worktree ([kontrola mapy a worktree](navrhy/2026-10-28-kontrola-mapy-a-worktree.md) §4): v dokumentu prostoru
worktree `w` díra, kterou `w` už zavřel, chybí; díra zavřená v jiném worktree nese `inProgress: {workspaceId,
branch, actor}` (na ní se pracuje, agent ji nebere); díry, které `w` otevřel, jsou na začátku s `origin:
"worktree"` (agent je způsobil, opraví je první). Na `main` / `draft` platí jen `inProgress`. `mapGapsTotal`
počítá výsledek. Strážce `mapa` a trend čtou dál jen main.

## Nálezy strážců (`guards`)

`guards = {open: {block, warn, info}, findings: [...]}`: otevřené nálezy [strážců](strazci.md) prostoru
dokumentu (`workspaceId` nálezu, výchozí `draft`) z tabulky `guard_findings`, `findings` nejvýš 20, `block`
první, uvnitř od nejnovějšího `lastSeen`. Položka `{key, guard, rule, severity, message, nodeId?, journeyId?,
executionId?, workspaceId, firstSeen, lastSeen}`. Karta s otevřeným nálezem dostane v `cards[]`
`guardFindings: {count, severity}` (nejvyšší závažnost); karta bez nálezu pole nemá. Nálezy strážce `mapa`
se **vynechávají** všude: díry mapy jsou jen v `mapGaps` (jeden zdroj děr mapy, strážci §5). Agent nález
nevyřizuje odškrtnutím; nález zmizí, když strážce při dalším běhu přestane hlásit jeho příčinu.
Modul `backend/canvas/opora_agent_state_guards.py`.

## Mezery

Vždy přítomné: `ai_review` (kontrolu výsledku dělá člověk; chybí, když je zapnuté [automatické review](oporahub-review-jobs.md)), `lean_verification`
(Lean v CI dokazuje jen čisté jádro OporaHubu, ne kód karet, viz [ověřování](oporahub-verification.md)) a
`auto_rebase` jen s `OPORA_AUTO_REBASE=0` (jinak převádí server, viz [automatický rebase](oporahub-auto-rebase.md)). `pull_request_link` dokud chybí modul výše.

## Ověření

`uv run pytest backend/canvas/test_opora_agent_state.py backend/canvas/test_opora_agent_state_card_page.py backend/canvas/test_opora_agent_state_pull_integration.py backend/api/editor/test_opora_agent_state_routes.py`
pokrývá tvar, prázdný projekt, každé pravidlo zdraví, `human_only` u přijetí,
deterministická ID, vyčerpaný rozpočet, vazbu PR, čtení bez SQL zápisů, `304` a plán nad 100 karet
(akce `claim` za starým řezem, uzavřené karty až na konci, `cardsOffset`).
