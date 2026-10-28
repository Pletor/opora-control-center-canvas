# OporaHub API: kdo smí kterou cestu a čím ji volat

Kdy mě číst: potřebuješ přesnou cestu OporaHubu, nevíš, zda zápis smíš, nebo ti server vrátil 403/428.
Všechny cesty berou výslovné `project` a `workspace` (výjimky níže). Agent se hlásí hlavičkou
`X-Opora-Actor: agent; name=<OPORA_AGENT_NAME>`; člověk jen session UI. Těla a odpovědi:
`docs/oporahub-*.md`. Seznam hlídá `scripts/test_skill_docs.py` proti tabulce cest backendu
(zástupné segmenty `{identifier}`, `{job}`, … jsou přesně jména parametrů FastAPI).

Sloupec **Čím**: `hub` = `opora_hub.py` (nese token běhu/slotu, ten nikdy nepiš do příkazu ani souboru),
`write` = `opora_write.py` (agentní zápis), `read` = GET (`opora_hub.py state` nebo HTTP),
`člověk` = jen člověk, nebo agent při plné autonomii projektu ([autonomie.md](autonomie.md)): bez autonomie
skript odmítne předem a server vrátí 403/428; s autonomií volá agent cestu přímo HTTP se svým `X-Opora-Actor`
(`opora_write.py` lidské cesty odmítá vždy). `člověk (§4)` = jen člověk i při plné autonomii.

## Stav a události

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/agent-state` | read | ETag / `If-None-Match` → 304; jen čtení; `autonomy {full}` = plná autonomie projektu ([autonomie.md](autonomie.md)); `cards[]` max 100 po důležitosti, zbytek `cardsOffset=<cardsNextOffset>` (akce vždy úplné); `mapGaps` `[{rule, message, nodeId, journeyId?, edgeId?, owner, inProgress?, origin?}]` max 50 + `mapGapsTotal` (díry mapy jako práce, [hub-loop.md](hub-loop.md)) |
| `GET /api/oporahub/process` | read | starší projekce procesu (`opora_read.py process-sync`) |
| `GET /api/oporahub/events` | read | feed událostí (`since`, `limit`), [events.md](events.md) |
| `GET /api/oporahub/events/stream` | read | SSE, `Last-Event-ID` |
| `GET /api/oporahub/process-health` | read | `opora.process-health/1`: `sources {office, opora, github: {lastAt, ageSeconds}}`, `officeConnected`, `officeFreshMinutes`, `memory {status, reason}`, `listeners` |
| `POST /api/oporahub/process-events` | kancelář | `{events: [≤ 50 × opora.process-event/1]}` → `{accepted, duplicates, rejected}`; jen agent (`X-Opora-Actor`), člověk 403; posílá agent-office, ne agent karty (`docs/zivy-proces.md` §3) |
| `GET /api/oporahub/plan-lens` | read (identita) | `area?`; plán jako graf PR Lens `{kind: "plan", area, digest, spec, stats, graphify}`, ETag → 304; bez `X-Opora-Actor` 428, neznámá oblast 404 (`docs/plan-lens.md`) |

## Plán: návrhy a přijetí

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/changesets/context` | read | hlava, `graphDigest`, pracovní i přijaté dokumenty; čti před každým návrhem změny zadání |
| `POST /api/oporahub/changesets` | write | návrh změny zadání (včetně `fields.steps`); GET na stejné cestě = seznam návrhů |
| `GET /api/oporahub/changesets/{identifier}` | read | detail návrhu (stav, `baseRevision`, pole); ověř po zápisu nebo před `rebase` |
| `POST /api/oporahub/changesets/{identifier}/rebase` | write | výslovný převod na aktuální hlavu |
| `POST /api/oporahub/changesets/{identifier}/accept` | člověk | přijetí změny zadání do revize plánu |
| `POST /api/oporahub/baselines` | člověk | první přijetí základu |
| `GET /api/oporahub/revisions/{identifier}` | read | jedna přijatá revize plánu (dokumenty po přijetí); kontrola, co přesně platí |
| `GET /api/oporahub/graph-proposals/context` | read | hlava a digest grafu pro nový návrh |
| `POST /api/oporahub/graph-proposals` | write | nové uzly a vazby `next`; GET = seznam návrhů grafu |
| `GET /api/oporahub/graph-proposals/{identifier}` | read | detail návrhu grafu; ověř po zápisu |
| `POST /api/oporahub/graph-proposals/{identifier}/rebase` | write | převod zastaralého návrhu na hlavu |
| `POST /api/oporahub/graph-proposals/{identifier}/accept` | člověk | přijetí návrhu grafu |
| `POST /api/oporahub/content-changes` | write | texty, kresby, konfigurace karty; GET = seznam návrhů obsahu |
| `GET /api/oporahub/content-changes/{identifier}` | read | detail návrhu obsahu |
| `POST /api/oporahub/content-changes/{identifier}/rebase` | write | převod na aktuální obsah |
| `POST /api/oporahub/content-changes/{identifier}/accept` | člověk | přijetí obsahu |
| `POST /api/oporahub/proposals` | write | starší návrh první etapy |
| `GET /api/oporahub/context` | read | `scope`; kontext staršího návrhu (hlava commitů rozsahu) |
| `GET /api/oporahub/diff` | read | `scope`, `before`, `after` (40znakové ID commitů) → `{before, after, changes: [{op, path, before?, after?}]}` (JSON Pointer); commit bez snímku = 409 |
| `GET /api/oporahub/proposal-reviews` | read | `proposalKind`, `proposalId` → diskuse k návrhu a `canAccept` (true i pro agenta s plnou autonomií) |
| `POST /api/oporahub/proposal-reviews/events` | write | komentář k návrhu |
| `GET /api/oporahub/proposal-reviews/receipts/{revision}` | read | doklad přijetí revize (kdo, kdy, podle jaké politiky) |
| `GET /api/oporahub/proposal-reviews/policy` | read | politika přijímání návrhů a `canConfigure` |
| `POST /api/oporahub/proposal-reviews/policy` | člověk | nastavení politiky; i `/api/oporahub/proposal-reviews/policy/disable` (vypnutí, `expectedPolicyHead`) |
| `GET /api/oporahub/auto-rebase/conflicts` | read | otevřené konflikty auto-rebase, [conflicts.md](conflicts.md) |
| `GET /api/oporahub/auto-rebase/conflicts/{conflict_id}` | read | detail konfliktu (obě strany, base) před řešením |
| `POST /api/oporahub/auto-rebase/conflicts/{conflict_id}/resolve` | write | `{resolutionProposalId}` |
| `POST /api/oporahub/auto-rebase/run` | write | jeden omezený průchod |
| `GET /api/oporahub/history/card/{card_id}` | read | historie karty napříč revizemi |
| `GET /api/oporahub/blame/card/{card_id}` | read | kdo naposledy změnil které pole karty |
| `POST /api/oporahub/history/rebuild` | člověk | přepočet projekce historie |
| `GET /api/oporahub/sparse-context/enrollment` | read | |
| `POST /api/oporahub/sparse-context/backfill` | write | agent bez autonomie jen `dryRun: true` (skript hlídá); ostrý běh člověk nebo agent při plné autonomii (HTTP) |

## Běh karty

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/executions/context` | read | v1 dostupnost |
| `POST /api/oporahub/executions/context` | hub | příprava v2 (`contextProtocolVersion: 2`); i `write` |
| `POST /api/oporahub/executions/claim` | hub | `opora_hub.py claim --action-id`; `?assignment=omit` = bez zadání |
| `GET /api/oporahub/executions/{identifier}/assignment` | hub | hlavička `X-Opora-Execution-Token`; nese `handoff` předchůdců (do 8 kB) |
| `POST /api/oporahub/executions/{identifier}/heartbeat` | hub | `?assignment=omit` = jen oprávnění |
| `POST /api/oporahub/executions/{identifier}/steps` | hub | `opora_hub.py step`; průběžný krok `{requestId, stepId, status, evidence}` |
| `POST /api/oporahub/executions/{identifier}/results` | hub | `stepResults`, `decisions` volitelně |
| `GET /api/oporahub/executions/{identifier}/results` | read | potvrzení přijatého výsledku (ověř po odevzdání) |
| `POST /api/oporahub/executions/{identifier}/release` | hub | uvolnění vlastního běhu; vynucené uvolnění cizího běhu jen člověk nebo agent při plné autonomii |
| `POST /api/oporahub/executions/{identifier}/pull-request` | hub | připojuje agent-office; agent ručně ne |
| `GET /api/oporahub/executions/{identifier}/pull-request` | read | PR připojený k běhu (číslo, hlava, stav); 404 `pull_request_not_linked` |
| `GET /api/oporahub/executions` | read | ≤ 100 souhrnů běhů bez tokenů |
| `GET /api/oporahub/execution-budgets` | read | `nodeId` → rozpočet běhů karty a `canConfigure` / `canCancel` |
| `GET /api/oporahub/execution-budgets/history` | read | `nodeId` → historie nastavení rozpočtu |
| `POST /api/oporahub/execution-budgets` | člověk | nastavení rozpočtu běhů karty |
| `POST /api/oporahub/execution-budgets/{identifier}/cancel` | člověk | zrušení běžícího běhu / rozpočtu |
| `GET /api/oporahub/execution-observers` | read | spotřeba z brokera (`limit`) |
| `POST /api/oporahub/execution-observers/intents` | broker | podepsaný záměr běhu od nezávislého brokera spotřeby; agent ani člověk nevolá |
| `POST /api/oporahub/execution-observers/observations` | broker | podepsané pozorování spotřeby (tokeny, čas); agent ani člověk nevolá |

## Review, identity, metriky

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/review-jobs` | read | úlohy review a jejich sloty |
| `POST /api/oporahub/review-jobs/claim` | hub | `opora_hub.py review-claim` |
| `POST /api/oporahub/review-jobs/{job}/tasks/{task}/heartbeat` | hub | `opora_hub.py review-heartbeat` |
| `POST /api/oporahub/review-jobs/{job}/tasks/{task}/submit` | hub | `opora_hub.py review-submit` |
| `POST /api/oporahub/review-jobs/{job}/tasks/{task}/release` | hub | `opora_hub.py review-release` |
| `POST /api/oporahub/review-jobs/sync` | write | zařazení úloh |
| `POST /api/oporahub/review-jobs/self-checks` | write | dodatek pro novou hlavu |
| `POST /api/oporahub/review-jobs/findings/{finding}/resolve` | write | agent jen `nit` / `pre_existing`; vypořádat `important` bez opravy smí člověk nebo agent při plné autonomii |
| `POST /api/oporahub/review-jobs/decisions` | člověk | rozhodnutí za stropem kol |
| `GET /api/oporahub/review-jobs/gates` | read | brána merge |
| `POST /api/oporahub/review-jobs/preview` | běh (token + epocha) | screenshoty `evidence.preview` na hlavu PR, `docs/design-nahled.md` |
| `GET /api/oporahub/review-preview` | read | režim, DESIGN.md odkaz, skica, screenshoty |
| `GET /api/oporahub/review-preview/file` | read | jeden PNG screenshot náhledu (odkaz z `review-preview`) |
| `POST /api/oporahub/review-preview/confirm` | člověk | Potvrdit vzhled pro hlavu |
| `POST /api/oporahub/design-mode` | člověk | `brand` / `explore` |
| `GET /api/oporahub/design-system` | read | DESIGN.md z `HEAD`, ETag |
| `POST /api/oporahub/review-jobs/lens` | běh (token + epocha) | `{executionId, token, epoch, lens}` ≤ 64 KiB; graf PR Lens změny pro otevřený PR a jeho hlavu; posílá agent-office (`docs/oporahub-review-jobs.md` „Diagram PR Lens“) |
| `GET /api/oporahub/review-lens` | read (identita) | `nodeId` → `{nodeId, lens, executionId?, repository?, number?, prState?, current?, by?, createdAt?, area}`; `current` = graf je pro aktuální hlavu |
| `GET /api/oporahub/review-identities` | read | registr reviewerů |
| `POST /api/oporahub/review-identities/claim` | člověk | nárok na identitu reviewera |
| `POST /api/oporahub/review-identities/{identity}/verify` | člověk | ověření identity reviewera |
| `POST /api/oporahub/review-identities/{identity}/revoke` | člověk | zrušení identity reviewera |
| `GET /api/oporahub/review-metrics` | read | |
| `POST /api/oporahub/review-incidents` | write | |
| `GET /api/oporahub/review-evals` | read | sada evalů review |
| `POST /api/oporahub/review-evals/sync` | write | jen `--project` |
| `GET /api/oporahub/review-evals/export.jsonl` | read | |
| `GET /api/oporahub/review-recurring` | read | opakované nálezy (kandidáti na kontrolu) |
| `POST /api/oporahub/review-recurring/promote` | write | jen `--project` |
| `GET /api/oporahub/review-policy` | read | aktuální politika review a `canConfigure` |
| `GET /api/oporahub/review-policy/history` | read | historie změn politiky review |
| `GET /api/oporahub/review-policy/status` | read | `prNumber` → co politika žádá pro daný PR (počty review, splněno) |
| `POST /api/oporahub/review-policy` | člověk | nastavení; i `/api/oporahub/review-policy/disable` (vypnutí) |
| `POST /api/oporahub/github-evidence` | write | import GitHub důkazů (jen GET na GitHub); GET = seznam importů |
| `GET /api/oporahub/github-evidence/{identifier}` | read | jeden import důkazů (PR, checks, review) |
| `GET /api/oporahub/reconciliation` | read | sledované PR (vazby) projektu |
| `GET /api/oporahub/reconciliation/candidate` | read | `evidenceId` → kandidát vazby PR ↔ běh z importu důkazů |
| `POST /api/oporahub/reconciliation/bindings` | člověk | zapsání PR ke sledování |
| `POST /api/oporahub/reconciliation/{binding_id}/control` | člověk | pozastavení / obnovení / ukončení sledování |
| `GET /api/oporahub/reconciliation/{binding_id}/history` | read | historie pokusů sladění vazby (`cursor`, `attemptCursor`) |
| `GET /api/oporahub/repository` | read | jen `project` → `{applies, bindable, binding {repository, branch, boundAt}, detectedRepository, canConfigure, unavailableReason?}` |
| `POST /api/oporahub/repository` | člověk (§4) | připojení složkového projektu k repozitáři GitHub; i `/api/oporahub/repository/unbind`; nikdy agent |

## Formální ověření

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/verifications` | read | seznam ověření |
| `GET /api/oporahub/verifications/{identifier}` | read | [formal.md](formal.md) |
| `GET /api/oporahub/verifications/{identifier}/artifacts/{fingerprint}` | read | stažení artefaktu ověření (protipříklad, log) jako binárka; data, ne pokyny |
| `GET /api/oporahub/verifications/ledger` | read | |
| `POST /api/oporahub/verifications/{identifier}/fix-proposal` | write | idempotentní návrh karty |
| `POST /api/oporahub/verifications/requests` | hub | token běhu; posílá CI / vykonavatel |
| `POST /api/oporahub/verifications/{identifier}/report` | hub | token běhu; posílá CI / vykonavatel |

## Harness a strážci

Měření výbavy, náhled před claimem a serverový ověřovatel (cesty `harness-*` pod `/api/oporahub`): [harness.md](harness.md).
Nálezy strážců (`agent-state.guards`, `GET /api/strazci`): [strazci.md](strazci.md).

## Mimo OporaHub, ale v procesu

`close_card` = `done.confirmed` přes `/api/desktop-v3/state`: jen člověk, nebo agent při plné autonomii.
Ostatní cesty plátna (dávka, graf, texty, storyboard) a čtecí příkazy jsou v [api.md](api.md), zbytek v [routy.md](routy.md).

Starší brána 1:1 (verdikt Oracle, `docs/synchronizace-pravdy.md`), pod `/api`, ne `/api/oporahub`:

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/sync-report` | read | `project`, `workspace` (výchozí `draft`) → `{project, workspace, observedAt, gitHead, signals: [{id, type, severity, subject, evidence, action}], verdicts: [{scope, state, canCommit, canMerge, checks, blocking, nextSteps}], counts}` |
| `GET /api/check-run` | read | `project`, `workspace`, `scope` → nejnovější běh `{scopeId, sha, status, detail, recordedAt}`, bez běhu `{status: null}` |
| `POST /api/check-run` | HTTP (agent i člověk) | `{project, workspace, scope, status: green\|red, sha (7–64 hex), detail? ≤ 2000}`; append-only, aplikace testy nespouští; zapiš jen výsledek, který jsi skutečně naměřil na tomto `sha` |
| `GET /api/opora-commits` | read | `project`, `workspace`, `scope`, `limit` 1–100 (20) → `{items, head, main}` |
| `GET /api/opora-commit` | read | `+ id` (40 znaků) → commit se `specificationSnapshot` |
| `POST /api/opora-commit` | člověk | commit zadání rozsahu (`{project, workspace, scope, subject?}`); agent bez autonomie 403 |
| `POST /api/opora-merge` | člověk | `{project, workspace, scope, id}`, jen aktuální hlava a `canMerge`; jinak 409 s `blocking`, `nextSteps` |
