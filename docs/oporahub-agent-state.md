# Stav pro agenty: jeden deterministický dokument

Agent dosud skládal obraz OporaHubu z přibližně čtrnácti endpointů a sám usuzoval,
co dál. `GET /api/oporahub/agent-state?project=<id>&workspace=<id>` vrací jeden
strojově čitelný dokument: přesné hlavy pro CAS, zdraví každé etapy smyčky,
rozhodnutí čekající na člověka a seznam připravených či blokovaných akcí. Další
krok počítá backend podle pevných pravidel, ne jazykový model. Stejná data budou
podkladem lidské infografiky (návrh „OporaHub — přehled“ v Claude Design).

Dokument je **jen ke čtení**: neprovádí claim, přijetí ani přechod stavu a nezapisuje
do SQLite. Skládá existující služby (`OporaChangesets`, `ProcessSync`,
`OporaExecutions`, seznamy návrhů a `classify_risk`) pod zámky projektu, takže jde
o konzistentní snímek. Akce nejsou oprávnění: každý zápis dál ověří původní API.

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
| `actions[]` | `{id, verb, method, path, targetId, preconditions, status, blockReason?, budget?}` |
| `gaps[]` | Známé nenapojené schopnosti `{id, stage, reason}` |
| `truncated` | Projekce karet narazila na limit 100 (`ProcessSync`) |

`health` je `ok`, `waiting`, `blocking` nebo `not_connected`. `reason` je strojový kód.
Pořadí polí, etap, akcí (podle slovesa a `targetId`) i mezer je stabilní.

## Pravidla zdraví

Pravidla platí v uvedeném pořadí; konstanty jsou v `opora_agent_state_rules.py`.

| Etapa | Pravidlo |
|---|---|
| `plan` | Žádná karta → `waiting/empty_plan`; bez přijatého základu → `blocking/no_accepted_baseline`; pracovní zadání se liší → `waiting/working_differs_from_accepted`; jinak `ok` |
| `proposal` | Nepřijatý a nenahrazený návrh s jiným rodičem než přijatou hlavou → `waiting/stale_proposals` |
| `acceptance` | Chybějící základ → `waiting/baseline_awaiting_human`; čerstvý návrh starší než `ACCEPTANCE_WAIT_SECONDS` (24 h) → `waiting/acceptance_overdue`; mladší → `ok/awaiting_human_within_window` |
| `claim` | Počítá karty `ready`; vyčerpané pokusy nebo opravy → `blocking/budget_exhausted` |
| `work` | Poslední běh karty ve stavu `running` s termínem (pronájem nebo pevný konec rozpočtu) v minulosti → `blocking/lease_past_deadline` |
| `evidence` | Nahlášený výsledek patří jiné přijaté revizi → `waiting/stale_evidence` |
| `review` | Nahlášený výsledek aktuální revize na nepotvrzené kartě → `waiting/human_review_required` |
| `pull_request` | Bez modulu vazby → `not_connected`; výsledek bez PR → `blocking/results_without_pull_request` |
| `merge` | Bez modulu → `not_connected`; otevřené PR → `waiting/pull_requests_open` |
| `plan_writeback` | Bez modulu nebo bez hlášení `planWrittenBack` → `not_connected`; mergnuté PR bez zápisu do plánu → `waiting/merged_without_plan_writeback` |

Počítá se jen poslední běh každé karty (jako v [procesu Control Center](oporahub-process-sync.md));
starší běhy jsou historie, ne nová blokace.

## Rozhodnutí a akce

Rozhodnutí řadí pevná priorita: přijetí základu, přijetí návrhu `critical`, `elevated`,
`low` (uvnitř podle stáří), kontrola nahlášeného výsledku, uzavření karty po merge PR. Každé ukazuje na akci.

| `verb` | Cíl | Stav |
|---|---|---|
| `accept_baseline` | `POST /api/oporahub/baselines` | vždy `blocked/human_only` |
| `accept` | `…/{id}/accept` podle druhu návrhu | vždy `blocked/human_only` |
| `rebase` | `…/{id}/rebase` zastaralého návrhu | `ready` (výslovný převod, ne automatický) |
| `claim` | `POST /api/oporahub/executions/claim` | `ready`, nebo `blocked/budget_exhausted` či `budget_policy_required`; `budget` nese zbývající pokusy a opravy |
| `review` | `GET /api/oporahub/executions/{id}/results` | `blocked/human_only` (AI review chybí) |
| `link_pull_request` | `POST /api/oporahub/executions/{id}/pull-request` | `ready` s modulem vazby, jinak `blocked/not_implemented` |
| `close_card` | `POST /api/desktop-v3/state` (`done.confirmed` karty) | vždy `blocked/human_only`; jen když vazba hlásí `awaitingHumanClose` a karta ještě není potvrzená; `preconditions` = `{executionId, mergeSha}` |

`preconditions` obsahují přesné hodnoty k opakování v těle požadavku (`expectedAcceptedHead`,
`expectedGraphDigest`, `expectedContextVersion`, u protokolu v2 `expectedBudgetPolicyHead`
a `previousExecutionId`). Ostatní pole těla (důvod, `requestId`, `ttlSeconds`) doplní agent
podle kontraktu dané operace. `id` akce je `act_` + SHA-256 z `(verb, targetId, příslušná hlava)`:
u návrhů a přijetí je to přijatá hlava, u claimu `contextVersion` karty, u výsledků jejich
přijatá revize. Stejné ID znamená stejný úmysl; agent blokovanou akci se stejným ID
neopakuje a po změně hlavy dostane nové ID.

## Podmíněné čtení

Odpověď nese silný `ETag` z těla bez `generatedAt` (`backend/api/http_etag.py`).
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

## Mezery

Vždy přítomné: `ai_review` (kontrolu výsledku dělá člověk), `lean_verification`
(Lean se nespouští automaticky, viz [ověřování](oporahub-verification.md)) a
`auto_rebase` (převod návrhu je výslovný). `pull_request_link` dokud chybí modul výše.

## Ověření

`uv run pytest backend/canvas/test_opora_agent_state.py backend/canvas/test_opora_agent_state_pull_integration.py backend/api/editor/test_opora_agent_state_routes.py`
pokrývá tvar, prázdný projekt, každé pravidlo zdraví, `human_only` u přijetí,
deterministická ID, vyčerpaný rozpočet, vazbu PR, čtení bez SQL zápisů a `304`.
