# OporaHub GitHub review/check policy — implementation contract proposal

Status: approved implementation contract; delivery and validation are tracked in the PR. This document specifies required behavior, not evidence of completion. Scope: local policy over read-only, server-fetched GitHub evidence. Never merge, write GitHub, mark a card complete, or convert worker receipts into verified evidence.

## Semantics and limits

A successful evaluation means: the newest bounded GitHub observation satisfies this exact local policy for this accepted revision and PR SHA. It does not prove branch-protection compliance, workflow integrity, independent humans, deployment, or present remote state. Numeric GitHub account IDs identify accounts, not people. The local human middleware session is one operator, not multi-party approval.

Trust check runs by exact (appId, name), not name alone. Status contexts remain informational: current normalization lacks creator identity. In particular GitHub Actions appId + name is not a workflow provenance guarantee. No branch-protection API or workflow enrichment is required for this deliberately limited first slice.

## Types (JSON; strict keys, bounded inputs)

Scope = {project: string, workspace: string}; use existing scope validation.
Id = existing 40-hex content ID; Sha = 40 lowercase hex; GitHubId = positive safe integer, reject booleans.
Rules = {
  requiredChecks: [{appId: GitHubId, name: string}],
  reviewerIds: GitHubId[],
  minimumCodeApprovals: integer,
  minimumPlanApprovals: integer,
  maxObservationAgeSeconds: integer
}
Bounds: 1..32 distinct check pairs; check name 1..255 chars; 1..100 unique reviewer IDs; both approval minimums 1..reviewerIds.length; age 30..3600 seconds. No implicit default policy, wildcards, permissive empty rules, or client-supplied verdicts. Normalize deterministic ordering before hashing. Reviewer allowlist limits qualifying approvals; any eligible write-permission human changes-requested review remains blocking even outside that allowlist.

PolicyRevision = {
  id: Id, schemaVersion: 1, project, workspace,
  kind: 'review-policy', parentPolicyRevision: Id|null,
  enabled: boolean, repository: {id: GitHubId, fullName: string, baseBranch: string},
  identityEvidenceId: Id, rules: Rules,
  by: {kind:'human', name:string}, createdAt: UTC timestamp
}
Disabled revision retains the preceding repository, evidence reference and rules for audit. Policy fields/by/time/id are constructed server-side; actor never comes from JSON.

## HTTP

GET /api/oporahub/review-policy?project=P&workspace=W
=> {project, workspace, policyHead:Id|null, policy:PolicyRevision|null, canConfigure:boolean,
    unavailableReason:string|null, acceptedHead:Id|null}

GET /api/oporahub/review-policy/history?project=P&workspace=W
=> {policyHead:Id|null, items:PolicyRevision[]} newest first, max100; no credentials.

POST /api/oporahub/review-policy
body {project,workspace,expectedPolicyHead:Id|null,identityEvidenceId:Id,rules:Rules}
Human only. Resolve identityEvidenceId through scoped immutable evidence repository; require complete, valid server evidence and repository/branch match current authoritative project configuration. Pin its numeric repository ID. Raw repository IDs/URLs in body are not accepted. Validate rules and create+activate an enabled revision atomically under graph/project locks and BEGIN IMMEDIATE with policy-head CAS. Same canonical request against immediately-created revision may return that revision; stale CAS otherwise409, no silent overwrite.
=> {policyHead:Id,policy:PolicyRevision}

POST /api/oporahub/review-policy/disable
body {project,workspace,expectedPolicyHead:Id}
Human only, same CAS. Append disabled revision rather than deleting the ref/history.
=> {policyHead:Id,policy:PolicyRevision}

Existing POST /api/oporahub/github-evidence remains identifier-only and keeps current request fields/actor rules. It starts and finishes a durable observation attempt described below; no policy parameter required. Response retains {snapshot,evaluation}, adds policyEvaluation. GET evidence list/detail likewise adds policyEvaluation without changing old evaluation fields.

GET /api/oporahub/review-policy/status?project=P&workspace=W&prNumber=N
=> {project,workspace,prNumber,policyEvaluation:PolicyEvaluation}
No arbitrary evidence selector for CURRENT status. Historical evidence detail can display assessment of that snapshot, but currentEligible=false unless it is the eligible latest attempt.

PolicyEvaluation = {
  evaluatorVersion:1,
  status:'not_configured'|'disabled'|'unknown'|'blocked'|'satisfied',
  policyRevision:Id|null,evidenceId:Id|null,attemptSequence:integer|null,
  binding:{acceptedRevision:Id|null,repositoryId:GitHubId|null,prId:GitHubId|null,
           headRepoId:GitHubId|null,headSha:Sha|null,baseSha:Sha|null,baseBranch:string|null},
  checks:{policyVerified:boolean,required:[{appId,name,status:'passed'|'missing'|'pending'|'failed'|'unknown',runId:GitHubId|null}]},
  codeReview:{status:'approved'|'changes_requested'|'missing'|'unknown',minimum:integer|null,reviewIds:GitHubId[],reviewerIds:GitHubId[]},
  planReview:{status:'approved'|'changes_requested'|'missing'|'unknown',minimum:integer|null,reviewIds:GitHubId[],reviewerIds:GitHubId[]},
  freshness:{currentEligible:boolean,observedFrom:string|null,observedUntil:string|null,
             expiresAt:string|null,evaluatedAt:string,remoteFreshness:'historical-observation'},
  blockers:string[]
}
checks.policyVerified true ONLY when currentEligible AND every required check passes. Overall satisfied additionally requires open, non-draft PR and both review thresholds without blockers. Do not label overall satisfied simply 'verified code'. Unknown freshness outranks old passing/failing statuses for CURRENT authority; retain historical data in snapshot.

Error convention: existing router/domain error mapping; identity human-required403/428 per established middleware, stale CAS409, strict malformed inputs existing400/422 mapping. Preserve existing evidence API errors. No token or GitHub authorization headers in responses/logs.

## Durable data and observation ordering

New additive schema, included in PROJECT_TABLES/project initialization:
- opora_review_policies(project_id,workspace_id,id,parent_id,created_at,content), primary(project_id,workspace_id,id); immutable canonical scoped content/hash validation.
- opora_review_policy_refs(project_id,workspace_id,policy_id), primary(project_id,workspace_id); CAS pointer, no deletion on disable.
- opora_review_attempts(project_id,workspace_id,sequence INTEGER,pr_number,configured_repository,configured_branch,accepted_revision,policy_revision nullable,started_at,finished_at nullable,state,evidence_id nullable,error_code nullable), primary(project_id,workspace_id,sequence).
Sequence allocated MAX+1 inside BEGIN IMMEDIATE; no reliance on timestamps for newest ordering. state in pending/complete/failed/context_changed. Records may transition pending -> terminal once. Policy and attempt repositories never commit caller transactions.

At observation start: locks + short tx; capture accepted head/config/policy head; allocate sequence and pending attempt, commit; release all locks before network. A newer pending attempt immediately makes previous evidence ineligible for CURRENT policy satisfaction.
At finish: locks + short tx; recheck current accepted head, config and policy pointer. Store bounded immutable snapshot with schemaVersion2 and attemptSequence, observedFrom, observedUntil (server UTC). Normal read failure stores existing incomplete evidence plus terminal failed attempt. Context/policy change marks context_changed, does not publish a success under new context; return409 as appropriate. Finish older attempt without replacing newer attempt authority. Every controlled failure path after start must terminalize its attempt. Crash leaves pending; current verdict unknown until a newer attempt succeeds, never falls back to older success.

Latest attempt selection: highest sequence for this scope, configured repository/branch and PR number, INCLUDING failed/pending/context_changed. Require selected attempt captured CURRENT accepted head and policy head. Then require complete snapshot, matching numeric repo/PR/head identity, open non-draft PR, valid timestamps and age. Failed refresh invalidates older positive evidence regardless of sameSHA. Late completion of attemptN cannot override attemptN+1. A mismatch expectedHeadSha is a failed/context_changed attempt, not an unrecorded error leaving old badge green.

Policy activation does not reinterpret old evidence as currently satisfied: require a new attempt captured under that exact policy revision. No policy ref at start or disabled ref => ordinary observation still available, policy not_configured/disabled. A changed policy during a read leaves old-policy result historical.

Age calculated from observedFrom, not completion, so slow collection cannot extend freshness. Reject future/negative interval and observedUntil<observedFrom. Existing reader deadline60s still applies. Checks/reviews are not a GitHub atomic snapshot; the observation interval is visible. No claim of remote freshness beyond this.

## Pure evaluation and compatibility

Pure evaluator accepts immutable policy/snapshot, latestAttempt, current server context and now. No I/O, DB reads or mutation. Reuse existing decisive-review selection and check identity grouping; avoid an alternative weaker review parser.
- Latest decisive per numeric reviewer; comments do not erase decisions; dismissal supersedes approval.
- Human User with server-verified current write/maintain/admin/push permission, excluding PR author. Unknown permission cannot silently erase a blocker.
- Qualifying approvals from allowlist, exact current head SHA. Each account counted once in each category; same qualifying review may satisfy code+plan, explicitly documented.
- Plan requires exact existing Opora-Plan line in review body for current scope/accepted revision. PR body alone does not count.
- Required check pairs only; choose newest numeric run ID for same pair and SHA as existing semantics; conflicting duplicate identity fails. Require completed/success. Other observed check failures remain visible but do not become implicit requirements.
- New required checks evaluator must not use observed_checks' aggregate-all status as a policy decision.
- Preserve old evaluator result and immutable snapshots. schemaVersion1 observations remain readable and cannot obtain CURRENT policyVerified:true. UI says 'refresh required for this policy'. No backfilling fabricated attempt timing or identities, no rewriting hashes.
- With no policy, preserve current observed-only display and policyVerified:false. Disabled policy is an explicit state, never an empty-rule pass.
- New tables join backup-down protection: any policy history/attempt history forbids destructive old-database restore just as existing OporaHub history; archive/project behavior follows existing immutable-history conventions.

## Ownership for three agents

A — policy authority/storage/API: new schema/repositories, immutable validation/CAS, human routes, attempt ordering API, adjacent transaction/migration tests. Own shared project schema/PROJECT_TABLES and backup guard registration at integration gate. Publish DTO and repo interfaces first.
B — evaluator + reader/evidence integration: new pure evaluator/tests; extend server reader observation timing; narrow evidence service wiring for start/finalize attempts and additive policyEvaluation. Reuse existing review/check normalization. Own existing reader/evidence files only; no schema edits.
C — UI + independent integration/browser proof: new policy editor/history/status module registered in existing OporaHub UI; mocked UI tests and real isolated browser scenario; independently review bypasses/CAS/failed-refresh behavior. Root owns docs and final merge/full-suite gates.

Repo interfaces agreed before coding: Policies.read(id), head(), activate(content,expected_head); Attempts.begin(pr,config,accepted,policy,started), finish(sequence,state,evidence_id,finished,error), latest(pr,config). Each scoped instance, caller tx mandatory for writes. Reads fail closed on corrupt scope/content. Evidence response assembly queries current policy/latest once per PR to avoid per-item repeated scans.

## UX and proof

Policy editor: human-only configure button; show pinned repository/branch/ID; required check rows choose observed app IDs + exact names; reviewer account IDs with observed names as labels only; explicit code/plan minimums and TTL. Show warning that app+name is not workflow identity. Explicit confirmation summary before activation/disable, policy-history link and stale-CAS reload. No auto-saving policy during evidence refresh.
Status: separate observed checks, policy checks, code review, plan review; show accepted revision, SHA, policy revision, observation interval/expiry. Pending/failed refresh visibly replaces current satisfied badge with unknown; historical result remains inspectable. Refresh button uses existing identifier-only POST; read-only agents may observe but cannot change policy. No-policy view offers setup, never green verification. Deleted-card execution history remains separate.

Required tests: strict types/bool rejection/limits; human vs agent policy writes; immutable ID integrity; CAS race and transaction rollback/restart; no-policy/disabled behavior; old v1 evidence refresh requirement; wrong app same name; missing check; pending rerun supersedes older success; duplicate/conflicting runs; oldSHA; neutral/skipped; irrelevant check failure; reviewer self/bot/unknown permission/dismissal/comment/changesrequested/allowlist/threshold; exact plan marker; repository recreation; accepted revision and policy changes during fetch; TTL boundary/future times/long collection; newest failed or pending attempt; later success then older request completion; crashed pending attempt; expectedSHA mismatch invalidation; forged client fields rejected; scope isolation; restore restriction preserves history; no token leakage; no card mutation or GitHub writes. Browser: configure -> fresh satisfied -> failed refresh unknown -> policy CAS/edit requires refresh -> disable -> historical inspection. Existing evidence API tests remain unchanged except additive fields.
