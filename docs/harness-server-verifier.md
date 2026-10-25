# Server-owned Harness fixture verification

The optional native verifier repeats the accepted baseline/candidate comparison in
fresh containers and compares the output itself. A worker can request a check;
it cannot submit the verifier's observed output. This closes a different boundary
from validating the shape of a worker report or observing a green CI check.

This module requires the installed Harness accepted paired-plan resolver. On older
installations, requests fail explicitly without executing anything. Configure the
native server, after approving the runtime image and ensuring Docker is available:

```json
{"project":"PROJECT_ID","workspace":"WORKSPACE_ID","image":"node@sha256:APPROVED_64_LOWERCASE_HEX_DIGEST","maxExperiments":1}
```

Set that JSON as `OPORA_HARNESS_VERIFIER`. With the variable absent the verifier is
disabled. The scope is exact and the image must already be installed; no image is
pulled automatically. Workers cannot supply an image, command, mount or Docker
options. This is a configured server capability, not a fallback for unavailable
worker tools. The configured native process, image and Docker engine are trusted.

An authenticated active execution requests:

```text
POST /api/oporahub/harness-verifier/requests
{project, workspace, executionId, token, epoch, plan: {id, digest}}
```

Normal Host/Origin/session and actor boundaries still apply. The token authorizes
the request only. Code, cases and expected outputs come from the immutable accepted
assignment; hashes must match. No code or observations supplied in the request are
accepted. The existing verification history and artifact APIs expose the record.

The service commits an admission to the existing verification store before starting
the runner. One plan can be admitted per execution epoch. Identical requests replay
the same record; a different plan or image conflicts. One pending admission occupies
the configured scope. A process lock also prevents simultaneous local requests.

Every invocation uses a new nonroot, read-only container, no network, no host mounts,
no host environment, dropped capabilities and `no-new-privileges`. Fixed limits are
128 MiB memory, one CPU, 32 processes, 128 KiB combined stdout/stderr and five seconds
per invocation. There are at most eight predeclared cases (16 invocations), alternating
baseline/candidate order, and a 60-second launch budget. Cleanup time is additional;
the process is not an invoice or hard physical termination guarantee. A missing
daemon/image, timeout, output overflow, lost execution authority or unconfirmed cleanup
stops further launches and retains unknown outcomes. There is no host Node fallback.

The runner compares exact UTF-8 stdout bytes and successful exit. It stores only
counts, reasons, elapsed times and output digests; never code, arguments, raw output
or credentials. Fixture cases are correlated and do not count as independent tasks.
Tokens and monetary cost are not inferred from elapsed time.

Admission survives a server crash. A replay before its recovery deadline returns the
pending record and never launches a replacement. After 90 seconds, replay attempts
bounded cleanup of only the deterministically named containers of that admission.
Confirmed cleanup produces an inconclusive report; uncertain cleanup keeps admission
pending and blocks further launches. Recovery never fabricates lost observations.

Completed reports use `trust: server-observed`; `independentlyVerified` means only
that this native process independently observed the complete accepted fixture check.
It does not certify the oracle, production behavior, security or the candidate's
causal benefit. Authority is checked again before recording; a stale run is historical
and inconclusive. `currentEligibility` and `promotionAllowed` remain false. The
worker's original report is preserved separately. Importing a report through the
worker verification endpoint cannot overwrite server-owned evidence.

Promotion still requires the independent review, task diversity, coverage, fault
tests and hierarchy policy described by the Harness learning contract. This verifier
does not alter running kits, accept plans or close cards. Optional experience delivery uses the existing role-scoped memory worker described below.

Verification: run adjacent runner/service/API tests, existing verification import
tests, the full backend suite, frontend tests and build. The isolated integration
pilot must also exercise the actual accepted paired-plan resolver and Docker runner;
mocked service tests alone are not that proof.

### Scoped history

`GET /api/oporahub/harness-verifier/requests?project=...&workspace=...&nodeId=...`
returns up to 100 newest fixture records (nodeId is optional). Reading history
requires the normal human/agent actor and does not require the runner to remain enabled.
Fixture requests carry `domain: harness-fixtures`; legacy records without a domain
remain formal records. Filtering occurs before the history limit, so fixture runs
cannot hide or invalidate the formal verification page or generate formal fix proposals.

Each new request persists the accepted plan problem in its origin and request identity,
alongside the immutable plan and script digests. Consumers must match all three before
applying fixture evidence to a library candidate. Historical records without a problem
binding remain readable but cannot establish problem-specific recommendation evidence.


### Lasting quarantine projection

History also returns `quarantine` (`harness.fixture-quarantine/1`). It groups complete,
server-owned failed fixture reports across the entire scoped verification store by accepted
problem, candidate ID and content digest. A source verification ID remains attached.
This projection is independent of the newest100-request history window: later passing runs
cannot erase an earlier candidate failure. It uses existing immutable verification records,
not a second outcome ledger. At most1000 cohorts are returned. Overflow or failed legacy
records without a problem binding sets `complete:false`; consumers must not treat missing
rows as healthy candidates. This does not publish a tool, change an active snapshot, or
claim production failure causality. Explicit assignment remains a visible user policy choice.


## Optional fixture experience delivery

With the native Harness memory projection installed, the report transaction also
queues an immutable `harness.fixture-memory/1` fact. The response's
`memoryDelivery.available` indicates whether that integration is installed; it is
not a delivery or indexing acknowledgment. Without it, verification remains usable
and the field is false. Replaying a completed request can enqueue an eligible
historical report after integration is installed, without another container run.

Only complete, cleaned-up, server-observed reports whose authority was current at
completion qualify. The queue validates native request/report digests and exact
scope before delivery. Metadata distinguishes fixture results from production
success and contains no executable source, arguments or raw outputs. Existing
registered role credentials, memory enablement, leases and retries govern delivery;
`GET /api/oporahub/harness-memory` reports its status when that module is installed.
A recalled fixture experience cannot promote a tool, clear native quarantine,
change an accepted kit, or count as human acceptance of the task.


## Durable experiment ceiling

`maxExperiments` is a required server-owned integer from 0 to 1000. It limits total
native verifier admissions in the exact configured project/workspace, using the
existing immutable request ledger. A missing limit rejects configuration; zero
permits only replay or recovery of existing requests, never new container runs.
Pending, failed, inconclusive and interrupted admissions all consume capacity.
Restarting, changing execution epoch, deleting a report or replaying a request does
not refund it. Existing pre-policy native requests count as spent too.

The ceiling check and admission insertion share one database transaction. Raising
the ceiling is an explicit server policy change, never a worker request field.
The per-execution deadline and ordinary execution authorization remain enforced.
The independent nonproduction allocation gate below also applies. Statistical
promotion gates and incumbent rollback remain separate unfinished work.


The scoped `GET /requests` response includes `budget` (`harness.experiment-capacity/1`)
with admitted/limit/remaining counts and explicit disabled, unavailable or other-scope
configuration states. Node filtering never narrows the workspace-wide counter.
`capacityAvailable` is only a snapshot, not a reservation or execution permission;
POST admission rechecks the same counter atomically. Configuration details from
another scope are not exposed. Agents can stop scheduling when capacity is exhausted
without repeatedly issuing rejected execution requests.


## Nonproduction exploration share

New native fixture admissions additionally require server-owned
`OPORA_HARNESS_EXPLORATION={"project":"PROJECT","workspace":"WORKSPACE","environment":"nonproduction"}`.
This explicitly classifies the entire selected workspace as eligible nonproduction work.
Do not configure it for production or mixed production/nonproduction workspaces.
A worker cannot supply or widen this policy. Existing configurations without this new
policy can read/replay evidence and recover interrupted cleanup, but cannot start new experiments.

The fixed allocation is at most one admitted experiment per nineteen distinct completed
baseline cards: `experiments / (baselineCards + experiments) <= 0.05`. This is a conservative
work-allocation budget, not a percentage of tool calls, CPU time, costs, or production exposure.
Baseline credit requires native Harness enrollment, a current verified human-close outcome,
a matching merged PR and retained native human closure event bound to that same execution/card,
and the card's current confirmed state. Self-reports, unknown outcomes, fixture passes, foreign
scopes and repeated execution epochs do not increase credit. Any card ever used for a native
experiment is excluded from baseline credit, including the proposed experiment's own card.

All native admission rows consume capacity, including old, failed, pending and interrupted
attempts. The gate and insertion share the existing write transaction; no new ledger exists.
The cumulative `maxExperiments` ceiling still applies. An empty workspace needs nineteen
eligible ordinary completed cards before its first autonomous experiment; there is no bootstrap
exception. Human acceptance in these counts is process completion, not proof of causal tool benefit.

`budget.exploration` in the existing history response reports status, baseline card count,
admitted count, remaining slots and policy digest. It grants no reservation. Admission excludes
its own card, so a generic snapshot can be more permissive than a specific request. A missing
native learning projection, invalid/missing policy or unavailable closure evidence denies work.
Pruning source events, reopening cards or changing policy can withdraw credit: spent attempts
are never refunded, further admissions stop, and running fixture authority is rechecked between
trials. Historical work is not retrospectively erased or relabeled successful.

## Native stability eligibility

`POST /api/oporahub/harness-verifier/eligibility` accepts the same current execution
credentials and accepted plan reference as `/requests`. It reads evidence without running
containers or changing the accepted assignment. Server configuration is explicit:
`OPORA_HARNESS_STABILITY={"project":"PROJECT","workspace":"WORKSPACE","approvedPlanDigests":["SHA256"]}`.
The approved digests identify independently chosen fault plans; a worker cannot lower the
thresholds or approve its own plan in the request.

The fixed project gate requires twenty verified outcomes across at least five cards,
at least 95% evidence coverage for the exact resource version and problem, no linked
regression, and a complete native comparison against the accepted baseline using the
configured image. Every candidate trial must pass. Retained output digests, exit codes,
reasons, ordering, report digests and current source bindings are revalidated. Unknown
outcomes remain in the denominator; missing modules, pruned closure events, reopened
cards, ambiguous enrollment and incomplete histories cannot supply success credit.

`harness.stability-eligibility/1` returns the scoped evidence and policy fingerprints,
the candidate/baseline/plan references and explicit reasons for denial. `eligible` is
only a read-time project assessment: `promotionAllowed` and `reservation` remain false.
A subsequent stable-state transition must reread evidence; this endpoint does not yet
publish a stable version or implement rollback. Closure evidence measures successful
work with a selected kit, not causal benefit from an individual tool. Neither the
sample threshold nor fixture coverage establishes global or production correctness.

### Reassessment after the evaluation session ends

`POST /api/oporahub/harness-verifier/eligibility/retained` accepts only
`project`, `workspace` and `verificationId`, with the same identified human/agent
boundary as verifier history. It resolves an existing native verification and its
retained accepted assignment, reconstructs the native request binding and rereads
the current policy, exact-version outcomes, regression evidence and fixture reports.
An expired or released evaluation lease is not needed for this read; it cannot be
used to execute work, publish a stable version or revive the old session.

The response uses `harness.retained-stability/1`, sets `executionAuthority: false`
and includes a `source` reference with verification/request/report fingerprints.
The nominated source must itself be one of the currently validated reports.
Missing or corrupt evidence cannot be replaced by another positive report, a
caller-supplied result or a stored stable label. A policy change or new regression
can withdraw eligibility. No token or assignment contents are returned.

This enables future pre-assignment recommendation reconciliation; the Office
selector must still integrate the fresh assessment and version-bound state.


## Multiple explicit project scopes

Each of `OPORA_HARNESS_VERIFIER`, `OPORA_HARNESS_EXPLORATION` and
`OPORA_HARNESS_STABILITY` accepts its existing single policy or an opt-in envelope:

```json
{"schema":"harness.scopes/1","scopes":[
  {"project":"project-a","workspace":"draft","image":"node@sha256:APPROVED_64_LOWERCASE_HEX_DIGEST","maxExperiments":10},
  {"project":"project-b","workspace":"draft","image":"node@sha256:APPROVED_64_LOWERCASE_HEX_DIGEST","maxExperiments":2}
]}
```

This example is for the verifier. Use the same envelope with the existing
`environment: "nonproduction"` entries for exploration, and `approvedPlanDigests`
entries for stability. Configure every desired project/workspace explicitly in
all applicable settings. No wildcard, default, cross-project fallback or worker
configuration override exists. Missing scopes cannot start verification or claim
stability. The complete document is validated before selection: duplicate scopes,
unknown fields or an invalid neighboring policy refuse the configuration. Limits
are 32 scope entries and 64 KiB per setting (the operating system may impose less).

The selected entry alone determines the policy fingerprint; wrapping a legacy
entry or changing an unrelated project does not invalidate its evidence. Removing
or changing the active project's policy is checked during execution and retained
assessment. Existing SQL counters, accepted assignments, proof sources and memory
remain project/workspace-scoped. Projects do not borrow experiment capacity or
verified outcomes. The existing process-wide verifier lock still serializes runs.

Roll out this server version before switching configuration to an envelope. Older
servers reject the envelope; they do not silently use the first project. To roll
back, restore the original singleton settings before restoring the old server.
No stored records need migration. This enables independent evidence collection
for multiple projects, not global promotion: sanitized publication, cross-project
eligibility and multi-environment proof remain separate requirements.


## Shared fixture eligibility

An operator may configure `OPORA_HARNESS_TRANSFER` only for intentionally published,
reviewed and sanitized tool versions. The setting authorizes exposing the listed
source identities and proof digests, not arbitrary project data. Publish/review the
resource through the existing repository/shared-catalog process first. This module
neither sanitizes nor copies resource contents or private OpenViking lessons.

```json
{"schema":"harness.transfer-policy/1","publications":[{
  "id":"shared-checker-v1","problem":"numeric.identity",
  "candidate":{"id":"script:shared-checker","digest":"64_LOWERCASE_HEX_CHARACTERS"},
  "sources":[{"project":"PROJECT","workspace":"WORKSPACE","verificationId":"NATIVE_ID"}]
}]}
```

Limits: 16 publications, 8 sources per publication, 64 KiB setting; no unknown
fields or duplicate IDs/source references. All entries validate before selection.
A missing setting disables the endpoint. A malformed or withdrawn publication
returns unavailable. Existing single-project functionality needs no transfer setting.

Authenticated human/agent callers POST only `{"publication":"shared-checker-v1"}`
to `/api/oporahub/harness-verifier/eligibility/shared`. They cannot supply source
proofs, outcomes, images or an eligibility override. The normal server origin/session
boundaries and 4096-byte request limit apply.

The service freshly reuses retained native project eligibility for every listed
source and matches the exact candidate ID/content digest and problem. All sources
must remain eligible; at least three distinct project IDs and two distinct currently
configured pinned Node image digests are required. Multiple workspaces of one project
do not increase the project count. Before a positive response, every proof and the
publication policy are rechecked. Source withdrawal, regression, missing data,
changed evidence or changed runtime prevents a positive result. Each individual
source still needs its existing project sample, coverage and approved-comparison gates.

The `harness.shared-eligibility/1` response includes approved source references,
report/evidence digests, pinned images, project/image counts and explicit reasons.
It never returns accepted assignments, execution credentials, raw script content or
raw output. The publication and evidence snapshot have their own digests. No task
counts are pooled into a target project's local success rate.

`eligible` describes only this shared fixture-transfer snapshot. Distinct image
contents are not proof of independent production environments or causal task benefit.
The result is not a reservation and can become stale; consumers must recheck before
use and verify the target catalog's exact version, declared capabilities and accepted
assignment. `promotionAllowed`, `executionAuthority` and `reservation` remain false.
Automatic global promotion, target recommendation integration and publishing sanitized
global memory lessons remain separate work. Removing the setting withdraws transfer
eligibility without deleting project evidence or modifying accepted kits.
