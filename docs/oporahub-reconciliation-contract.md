# Durable GitHub reconciliation — implementation contract

Status: implementation contract. Validation evidence is reported in the PR.
Operational usage is documented in oporahub-reconciliation.md. This specification
does not itself prove completion. The implementation extends the versioned-plan,
review-policy and execution protocols without changing their authority.

## Outcome

A human opts into persistent read-only tracking of one numerically pinned GitHub PR
and one accepted plan revision. The backend resumes after a crash and records a
remote merge once. A browser or Office worker need not remain open. No GitHub
writes, plan acceptance, graph/spec/state changes, card completion or deployment.
PolicyObservation and its current-head fences remain unchanged.

A plan advance does not stop the original subscription: observe its original PR
outcome and label it historical for the current plan. Human-approved association
is linkage, not proof the code implements the plan. Show source head SHA and merge
commit SHA separately. Say PR merged according to the observation, never that
source-head checks verified the merge commit or that a branch still contains it.

## Binding and human controls

Use immutable content-addressed bindings, separate from mutable job state. Binding:
{id,schemaVersion:1,project,workspace,acceptedRevision,identityEvidenceId,
 repository:{id,fullName,baseBranch},pr:{id,number,headRepoId},enrolledHeadSha,
 configuration,intervalSeconds:300,by,createdAt}. Capture full server configuration
including repoPath/sourcePath. Names casefold, branch exact, IDs safe positive
integers; headRepoId may become null in later observations if a fork is deleted.
No automatic transfer to a different numeric repo/PR/base branch/head repository.
A missing head repo is not a replacement identity and must not conceal a merge.

Enrollment requires a complete scoped server evidence snapshot for the exact CURRENT
accepted revision; pin all IDs server-side. No network while configuring. Human
session only. One enabled binding per scope/repoID/PRID is sufficient initially.
Creating another requires explicitly pausing the existing binding first; return
409 with a safe explanation, never silently replace or rebind. Multiple PRs per
workspace are supported. Old bindings/events remain readable.

Control mutations append immutable content-hashed audit records and increment a
persisted generation. Control {id,bindingId,parentControlId,generation,action,
enabled,requestId,requestDigest,by,createdAt,project,workspace}. Enrollment is
action=enroll generation1; pause/resume/retry require expectedGeneration CAS.
requestId is an opaque bounded printable identifier using existing request-ID
validation conventions; scope-wide uniqueness, exact canonical request replay
returns original result, changed request under same ID conflicts. No automatic
client retry. Resume retains the original binding pin and revalidates config,
accepted historical record, writable/active workspace and no other enabled watch
for that PR. Retry schedules durable work, never directly calls GitHub.

## Durable storage and job protocol

New project-DB tables for bindings, controls/request replay, jobs, attempts,
immutable observations and transition events. Share one transaction for every
binding/control/job mutation and every observation/event/job finish. Do not commit
inside repository helpers. Register PROJECT_TABLES/schema and protect destructive
old-backup restore against every new history/authority table. Preserve archive,
restart and existing evidence compatibility. Validate stored scope/hash/shape.

Job has bindingId, control generation, due time, monotonically increasing claim
 epoch, owner nonce, lease expiry, failure count, last attempt/observation/transition
references and sanitized error. Claim checks enabled + due + absent/expired lease
inside BEGIN IMMEDIATE, increments epoch and persists pending attempt BEFORE GET.
Reclaim expired work marks abandoned attempt interrupted. Never reset epochs.
Network occurs outside graph/project/SQL locks. Finish checks owner, epoch,
generation, enabled state and actual expiry under graph->project locks + tx.
Pause sets enabled=false and fences old writers (this is the disable operation). No stale worker may create an observation,
transition or current projection. Scope/config/readOnly/archive mismatches pause
with explanation; preserve histories. Verify bound accepted record still exists.
Current accepted head mismatch alone only makes revisionRelation historical.

Provider cooldown is a limited flow-control exception: sanitized Retry-After/reset
metadata may raise the persisted maximum provider-wait scalar even when the result
has become stale or paused. It can only delay requests; it cannot change the
publication fact, control generation, lease ownership or successful attempt. This
prevents restart from bypassing a known provider limit. Stop/closed-DB guards still
apply before any such metadata write.

Each successful poll records a small immutable observation with interval and
validated PR lifecycle data. Failed attempts remain auditable and make current
health retrying/unknown; last successful historical fact stays inspectable.
Do not display a retained fact as newly fetched after failure or pending read.
Transition dedup compares with last semantic state, ignoring read timestamps.
A->B->A is a new transition. The merged fact additionally has a stable event key
from bound repoID+PRID+mergedAt+mergeCommitSha; duplicate fetch/retry/restart cannot
create a second merge event. Atomic observation/event/job advance is mandatory.
Completed-attempt replay returns the original result; changed replay conflicts.

## Reader, scheduling and lifecycle

Separate bounded GET-only merge/lifecycle reader using fixed api.github.com origin,
no redirects/proxies, environment token only, bounded bytes/deadline/calls and
sanitized errors. Reuse existing security primitives; do not alter review DTOs.
Validate repository + base repository numeric identity and exact PR ID/number/base
branch against binding. Normalize open/closed-unmerged/merged, headSha, headRepoId,
draft, merged boolean, mergedAt and mergeCommitSha. Closed is never enough to infer
merged; pre-merge test merge SHA is never a merged fact. Reject incomplete or
inconsistent metadata. A deleted fork head may be null; other numeric mismatch
requires human attention. Observation interval is server-side and visible.

One standalone manager owned by app lifespan, not feature logic in factory/service.
Discover project subscriptions fairly in bounded batches; one serial request stream,
bounded global cadence and no network before opt-in. Default open interval300s;
closed-unmerged continues at slower900s because reopening is possible. Complete
merged state becomes reconciled/terminal, an historical fact rather than ongoing
branch-containment monitoring; explicit retry may observe again. Persist exponential
backoff with bounded jitter/max3600s, honor sanitized Retry-After/rate-reset metadata
and global provider cooldown. Never hot-loop or bypass provider cooldown on retry.
Identity/config failures pause action-required; transient errors retry automatically.

Lease must exceed bounded network deadline, with no indefinite heartbeat extension.
Shutdown stops new claims, cancels/wakes idle work, and prevents any late DB access
or result writes after service close. A blocked network call may leave a recoverable
pending lease; recheck stopping after acquiring finish locks and before DB access.
Bound joins and requests; do not close DB beneath an active local transaction.

## HTTP and public DTO

Prefix /api/oporahub/reconciliation. Existing middleware identity conventions apply.
GET ?project&workspace => {project,workspace,currentAcceptedHead,canConfigure,
 unavailableReason,serverNow,items:[{binding,control,job,latestAttempt,
 lastSuccessfulObservation,revisionRelation}]}. Bounded list, no owner nonce/token.
GET /candidate?project&workspace&evidenceId => validated enrollment summary and
canConfigure; no remote read. Include existing enabled binding for that PR.
POST /bindings body {project,workspace,expectedAcceptedHead,identityEvidenceId,
requestId} => {binding,control,job}. No caller IDs/author/merged outcome.
POST /{bindingId}/control body {project,workspace,expectedGeneration,
action:'pause'|'resume'|'retry',requestId} => {binding,control,job}.
GET /{bindingId}/history?project&workspace&cursor => bounded immutable bindings,
controls, attempt/observation/event summaries and explicit nextCursor; detail by
observation/event ID may be separate if useful. All scope-checked, safe text.

Public job states scheduled/checking/retrying/paused/reconciled, next due,
lease expiry, failures and sanitized reason. latestAttempt and lastSuccessfulObservation
are separate. revisionRelation includes bound/current accepted revisions and match.
Observed PR states unknown/open/closed-unmerged/merged are independent of job health
and review-policy status. Sparse lists; no full history repeated in every row.

## Frontend

New feature frontend/hub/github-reconciliation with README and adjacent pure tests.
App composition only; use existing shared poller for read-only status. Browser does
not enqueue timers or call GitHub itself. Human evidence selection + exact pin
summary + persistent-network opt-in confirmation. Scope/selection/generation/action
changes reset confirmation. No unguarded async writes or automatic POST retries.
Show old revision linkage, last successful historical fact, current attempt state,
retry timing, source/merge SHAs and transition history. Empty Canvas still exposes
history. Numeric IDs and constructed GitHub links only; untrusted text never HTML.
Update OporaHub workspace README inventory too. Backend retries survive tab close.

## Required proof

Required: actual schema+HTTP human403/428, spoof/cross-scope rejects, replay/CAS;
independent DB claim race, expiry takeover and stale finish; pause/resume;
plan advances during GET preserve old-bound fact and do not mutate accepted head;
remote already merged before enrollment; crash before/within/after event commit;
restart finds due/expired work and exactly one merge event; closed-unmerged reopen;
deleted fork; repo recreation/retarget; malformed/oversize/rate/timeout data;
rollback entire DB transaction; history pagination/integrity and backup/archive;
bounded fairness/shutdown; no credentials/owner tokens exposed or Github writes.
Browser isolated actual factory/schema/middleware with synthetic reader: enroll ->
automatic open -> failure/backoff -> merged -> restart -> one merge event -> plan
advance displays historical binding, review remains separate. Screenshots.
