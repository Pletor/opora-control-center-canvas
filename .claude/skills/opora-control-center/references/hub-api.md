# OporaHub API: kdo smí kterou cestu a čím ji volat

Kdy mě číst: potřebuješ přesnou cestu OporaHubu, nevíš, zda zápis smíš, nebo ti server vrátil 403/428.
Všechny cesty berou výslovné `project` a `workspace` (výjimky níže). Agent se hlásí hlavičkou
`X-Opora-Actor: agent; name=<OPORA_AGENT_NAME>`; člověk jen session UI. Těla a odpovědi:
`docs/oporahub-*.md`. Seznam hlídá `scripts/test_skill_docs.py` proti tabulce cest backendu.

Sloupec **Čím**: `hub` = `opora_hub.py` (nese token běhu/slotu, ten nikdy nepiš do příkazu ani souboru),
`write` = `opora_write.py` (agentní zápis), `read` = GET (`opora_hub.py state` nebo HTTP),
`člověk` = skript odmítne předem, server vrátí 403/428.

## Stav a události

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/agent-state` | read | ETag / `If-None-Match` → 304; jen čtení |
| `GET /api/oporahub/process` | read | starší projekce procesu (`opora_read.py process-sync`) |
| `GET /api/oporahub/events` | read | feed událostí (`since`, `limit`), [events.md](events.md) |
| `GET /api/oporahub/events/stream` | read | SSE, `Last-Event-ID` |

## Plán: návrhy a přijetí

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/changesets/context` | read | hlava, `graphDigest`, pracovní i přijaté dokumenty |
| `POST /api/oporahub/changesets` | write | návrh změny zadání (včetně `fields.steps`) |
| `POST /api/oporahub/changesets/{id}/rebase` | write | výslovný převod na aktuální hlavu |
| `POST /api/oporahub/changesets/{id}/accept` | člověk | |
| `POST /api/oporahub/baselines` | člověk | první přijetí základu |
| `GET /api/oporahub/graph-proposals/context` | read | |
| `POST /api/oporahub/graph-proposals` | write | nové uzly a vazby `next` |
| `POST /api/oporahub/graph-proposals/{id}/rebase` | write | |
| `POST /api/oporahub/graph-proposals/{id}/accept` | člověk | |
| `POST /api/oporahub/content-changes` | write | texty, kresby, konfigurace karty |
| `POST /api/oporahub/content-changes/{id}/rebase` | write | |
| `POST /api/oporahub/content-changes/{id}/accept` | člověk | |
| `POST /api/oporahub/proposals` | write | starší návrh první etapy |
| `POST /api/oporahub/proposal-reviews/events` | write | komentář k návrhu |
| `POST /api/oporahub/proposal-reviews/policy` | člověk | i `/api/oporahub/proposal-reviews/policy/disable` |
| `GET /api/oporahub/auto-rebase/conflicts` | read | [conflicts.md](conflicts.md) |
| `POST /api/oporahub/auto-rebase/conflicts/{id}/resolve` | write | `{resolutionProposalId}` |
| `POST /api/oporahub/auto-rebase/run` | write | jeden omezený průchod |
| `GET /api/oporahub/history/card/{id}` | read | i `/api/oporahub/blame/card/{id}` |
| `POST /api/oporahub/history/rebuild` | člověk | |
| `GET /api/oporahub/sparse-context/enrollment` | read | |
| `POST /api/oporahub/sparse-context/backfill` | write | agent jen `dryRun: true` (skript hlídá) |

## Běh karty

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/executions/context` | read | v1 dostupnost |
| `POST /api/oporahub/executions/context` | hub | příprava v2 (`contextProtocolVersion: 2`); i `write` |
| `POST /api/oporahub/executions/claim` | hub | `opora_hub.py claim --action-id`; `?assignment=omit` = bez zadání |
| `GET /api/oporahub/executions/{id}/assignment` | hub | hlavička `X-Opora-Execution-Token`; nese `handoff` předchůdců (do 8 kB) |
| `POST /api/oporahub/executions/{id}/heartbeat` | hub | `?assignment=omit` = jen oprávnění |
| `POST /api/oporahub/executions/{id}/steps` | hub | `opora_hub.py step`; průběžný krok `{requestId, stepId, status, evidence}` |
| `POST /api/oporahub/executions/{id}/results` | hub | `stepResults`, `decisions` volitelně; GET = potvrzení |
| `POST /api/oporahub/executions/{id}/release` | hub | uvolnění vlastního běhu |
| `POST /api/oporahub/executions/{id}/pull-request` | hub | připojuje agent-office; agent ručně ne |
| `GET /api/oporahub/executions` | read | ≤ 100 souhrnů běhů bez tokenů |
| `POST /api/oporahub/execution-budgets` | člověk | i `/api/oporahub/execution-budgets/{id}/cancel` |
| `GET /api/oporahub/execution-observers` | read | spotřeba z brokera |

## Review, identity, metriky

| Cesta | Čím | Poznámka |
|---|---|---|
| `POST /api/oporahub/review-jobs/claim` | hub | `opora_hub.py review-claim` |
| `POST /api/oporahub/review-jobs/{id}/tasks/{id}/heartbeat` | hub | `opora_hub.py review-heartbeat` |
| `POST /api/oporahub/review-jobs/{id}/tasks/{id}/submit` | hub | `opora_hub.py review-submit` |
| `POST /api/oporahub/review-jobs/{id}/tasks/{id}/release` | hub | `opora_hub.py review-release` |
| `POST /api/oporahub/review-jobs/sync` | write | zařazení úloh |
| `POST /api/oporahub/review-jobs/self-checks` | write | dodatek pro novou hlavu |
| `POST /api/oporahub/review-jobs/findings/{id}/resolve` | write | agent jen `nit` / `pre_existing` |
| `POST /api/oporahub/review-jobs/decisions` | člověk | za stropem kol |
| `GET /api/oporahub/review-jobs/gates` | read | brána merge |
| `GET /api/oporahub/review-identities` | read | |
| `POST /api/oporahub/review-identities/claim` | člověk | i `/api/oporahub/review-identities/{id}/verify`, `/api/oporahub/review-identities/{id}/revoke` |
| `GET /api/oporahub/review-metrics` | read | |
| `POST /api/oporahub/review-incidents` | write | |
| `POST /api/oporahub/review-evals/sync` | write | jen `--project` |
| `GET /api/oporahub/review-evals/export.jsonl` | read | |
| `POST /api/oporahub/review-recurring/promote` | write | jen `--project` |
| `POST /api/oporahub/review-policy` | člověk | i `/api/oporahub/review-policy/disable` |
| `POST /api/oporahub/github-evidence` | write | import GitHub důkazů (jen GET na GitHub) |
| `POST /api/oporahub/reconciliation/bindings` | člověk | i `/api/oporahub/reconciliation/{id}/control` |

## Formální ověření

| Cesta | Čím | Poznámka |
|---|---|---|
| `GET /api/oporahub/verifications/{id}` | read | [formal.md](formal.md) |
| `GET /api/oporahub/verifications/ledger` | read | |
| `POST /api/oporahub/verifications/{id}/fix-proposal` | write | idempotentní návrh karty |
| `POST /api/oporahub/verifications/requests` | hub | token běhu; posílá CI / vykonavatel |
| `POST /api/oporahub/verifications/{id}/report` | hub | token běhu; posílá CI / vykonavatel |

## Mimo OporaHub, ale v procesu

`close_card` = `done.confirmed` přes `/api/desktop-v3/state`: **jen člověk**. Ostatní cesty plátna
(dávka, graf, texty, storyboard) a čtecí příkazy jsou v [api.md](api.md).
