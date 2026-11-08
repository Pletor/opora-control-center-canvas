# Research graph API

Research is an independent semantic graph within one project and workspace. It links to the
structure, vault fragments, Pletor questions, and tickets without copying their lifecycle.
Renaming/removing a structure node never deletes research. A `decision` card is a recorded
proposal/decision discussion, **not proof of human approval**; `status=resolved` does not approve
or modify a plan. Existing plan and ticket authority remains unchanged.

## Reading

`GET /api/research?project=P&workspace=W&archived=0` returns `{cards, edges}`. Each card header
omits `content` and `sources`; `sourceCount` and `platforms` describe available evidence. Headers
retain topicPath, verification, refs, ID, revision and metadata.
Headers also contain `relationCounts: {incoming, outgoing}`, derived from the returned scoped edges;
these counts are not stored in card revisions and remain independent of client-side filters.
Edges include their full reason, resolved/missing context and direction. `archived=1` includes archived records. Edges to hidden
archived cards are hidden in the active listing, but remain stored and visible in details.

`GET /api/research/cards/ID?project=P&workspace=W&revision=N` returns `{card, history, edges}`.
Without revision it returns latest; with revision it returns that immutable snapshot. `history`
is card revision metadata; `edges` are latest incident edges, including archived edges. Full
content and quotes are returned without truncation. Missing card/revision is 404.

Trusted internal consumers use `service.listing(canvas, project, workspace, archived=False)`
and `service.detail(canvas, project, workspace, id, revision=None)`.

HTTP reads require a human UI session or a valid worker/heart token for this project/workspace.
A heart token for main may also access the project's recorded active workspace. This exception
does not extend to worker tokens or unrelated workspaces.

## Writing

`POST /api/research` takes exactly `{project, workspace, key, operations}`. Only the human UI or
heart token can write, even when the project's gate is disabled. Research memory can also be written in main without changing Structure.
`key` is a client-generated idempotency identifier (max 200 characters). Replay with identical
operations returns the original result, even after later revisions. Reusing it with different
operations is 409. All operations commit atomically or none do.

Card operation (all listed fields required):

```json
{"op":"card","id":"rc_login","expectedRevision":0,"kind":"finding",
 "title":"Session lifecycle","summary":"The UI does not determine session expiration.",
 "topicPath":["Login","Authentication logic"],"content":"Complete explanation and context",
 "status":"open","verification":{"status":"unverified","method":"","at":""},
 "sources":[],"refs":{"nodeIds":[],"questionIds":[],"ticketIds":[],"sessionIds":[],
 "fragmentIds":[],"attachmentIds":[]}}
```

Card kinds: question, finding, visual, option, decision. Status: open, resolved.
Verification: unverified, verified, observed, false, unreachable, inference, conflict.
Verified/observed require a nonempty method, timestamp and sources; source verification is
performed by the research pipeline, not by trusting arbitrary worker submissions.

Each source is `{ref, platform, quote, title, accessedAt, timestamp?, revision?, location?, discoveredVia?, verification?}`.
`ref` is original URL, code location, or attachment identity; it is not restricted to web URLs.
No source is fetched by this API. Render refs as text unless an allowed link protocol is present.
Google belongs in discoveredVia when the actual evidence comes from another page. Video segment
and code revision belong in timestamp and revision; location identifies the source file and lines.
Optional source verification carries its own status, method and time, separate from the interpretation.
UI/REA observation does not prove hidden
implementation. External refs arrays preserve stable identities; the API validates their shape,
not the lifetime/existence of every referenced external artifact.

Edge operation:

```json
{"op":"edge","id":"re_login_logic","expectedRevision":0,"fromId":"rc_login",
 "toId":"rc_logic","relation":"continues_to","reason":"Screen states do not establish authentication behavior.",
 "resolved":"Form layout and error states","missing":"Identity verification and session lifetime",
 "evidenceIds":["rc_login"]}
```

Relations: supports, contradicts, elaborates, option_for, supersedes, resolves, continues_to.
Reason is always required; continues_to and resolves also require resolved and missing. Endpoints are
separate cards and evidenceIds are card IDs in the same workspace. The complete resulting graph
is checked after the batch, so cards and their edges can be created atomically in any order.

`expectedRevision=0` creates a new entity; updates supply its current positive revision. Updates
supply the complete card/edge fields. Unknown fields are rejected. Stale revision is 409.
Each entity appears at most once per batch. Server supplies revision, archived, createdAt,
updatedAt and by; callers cannot impersonate those metadata fields.

Archive with `{op:"archive", entity:"card"|"edge", id, expectedRevision, archived:true|false}`.
Archive/unarchive adds a new revision and preserves content, sources, refs and all older revisions.
There is no delete endpoint. Semantic edge revisions are preserved and readable at `GET /api/research/edges/ID?project=P&workspace=W&revision=N`, returning `{edge, history, workspace}`.

Limits reject rather than truncate: 1–1000 operations, 2,000,000 content characters/card,
1000 sources/card, 200,000 quote characters/source, and existing application HTTP body limit
(which can return 413 before field validation). Use smaller independent batches/cards if needed.
Malformed fields return 422; revision/key/reference conflicts 409; invalid auth 401/403.

At the HTTP boundary, requested `main` resolves to the recorded active workspace when present,
otherwise main itself. All responses include the effective `workspace`; retain it for subsequent
operations. Internal service functions use their exact supplied workspace. Main research memory
is independent of Structure editability and remains preserved if the active workspace changes.

## Conversation journal

Research reads lazily reconcile durable `pletor_questions.json` events: the original question,
every refinement, every heart answer (including full text, refs, unknown/reason and author),
and the exact closing note. Each event becomes a stable card with questionIds and a semantic
link to the original question. Research cards carrying the same questionId are linked as well.
These journal cards are explicitly unverified conversation records; closing a question is not
human approval of a plan or implementation. Topics start as `Nezařazené otázky / question ID`;
only the heart's later reasoning assigns a substantive topic.

Chronological edges connect successive events only when every recorded timestamp is a valid,
distinct timestamp with an explicit time zone. Equal timestamps, missing offsets or legacy
placeholder times leave chronology unspecified; full original timestamps remain in the cards.
These edges describe recorded order, never inferred causality or approval.

Reconciliation is create-only. Heart retags, content edits, archives and edge edits are retained.
A failed projection leaves the source question JSON intact and the next read retries missing
records. There is no cross-store transaction pretending to atomically change JSON and SQLite.
Each bounded SQL batch is atomic; retries deduplicate stable IDs and never add repeated revisions.

New questions pin `researchWorkspace` once at creation (main resolves to the current active
workspace, if any); existing Pletor `workspace` delivery routing remains unchanged. Later active
workspace changes do not move or copy that question. Legacy questions without a pin use their
original literal workspace; legacy main questions are not copied into successive active branches.

## Complete reads and synchronization

`GET /api/research/topics?project=P&workspace=W` returns semantic topic paths and children.
`GET /api/research/cards/ID/parts?project=P&workspace=W&size=12000` returns complete card JSON
in bounded Unicode-code-point chunks. Continue with the returned `revision`, `snapshot`, and
`offset=nextOffset`; concatenate `text` and parse only after `nextOffset=null`. A changed scope or
snapshot is rejected. The immutable revision remains readable when the latest card changes.

`GET /api/research/events?project=P&workspace=W&after=0&limit=100` returns durable ordered
invalidations, `nextCursor` and `hasMore`. Follow pages until exhausted and retain the cursor.
Card/edge revisions, replay receipt and event commit together. Replays add no event; conversation
journal projection uses the same transaction. The Canvas polls this feed to refresh changed data.

Sources may additionally carry `verification:{status,method,at}`. This verifies the source passage,
not a project-specific interpretation: imported practice/risk recommendations retain their complete
raw content but are marked `inference`, even when their supporting quotation was verified.

## Reviewed decisions and native tasks

The decision inspector lets a human explicitly review a decision, its original question, exact
evidence revisions, rationale, assumptions and constraints. `POST /api/research/decision-reviews`
takes `{project,workspace,review:{decisionId,decisionRevision,problemId,evidence:[{id,revision}],
rationale,assumptions,constraints}}`. Only a human UI session may create this immutable review.
It is a research-path decision, **not acceptance of a native task proposal**.

`GET /api/research/decision-reviews?project=P&workspace=W&decisionId=ID` lists reviews;
`GET /api/research/decision-reviews/ID?project=P&workspace=W` returns the full immutable record.
The heart or human proposes tasks with `POST /api/research/decision-reviews/ID/tasks`, body
`{project,workspace,tasks:[{ref,title,goal,acceptance,dependsOn, parentId?,nodeId?}]}`.
New tasks use native graph proposals. Existing IDs use native specification proposals, preserving
their previous constraints, criteria, steps and harness. New and existing tasks are proposed separately;
changes to existing graph dependencies belong to the native graph editor, not a specification update.

Each task's accepted specification pins a compact reference to the full research review. Complete
provenance is never shortened to fit native field limits. An unchanged retry returns the same native
proposal and IDs; changed retries conflict. The native OporaHub UI remains the only acceptance path.
`GET .../ID/tasks` reads native acceptance; `POST .../ID/reconcile` with `{project,workspace}`
adds reverse research links only after actual acceptance. The inspector exposes this synchronization.

## Returned office problems

`POST /api/research/tickets/branch` takes `{project,workspace,ticketId,feedbackId}` and derives
the original session, task, task version and execution from the existing ticket. The deterministic
question card pins that origin in `content.ticketOrigin` JSON; repeat delivery returns the same branch.
There is no new ticket store. A solution card must link to the branch through `resolves`.

`POST /api/research/tickets/answer` adds `{cardId,revision,text}` to that body and uses native
`ticket.answer`. The delivered answer identifies the exact research revision and original feedback.
The original holder receives it through existing ticket polling. Identical retries are harmless;
a different answer conflicts. Task removal does not erase the research or its original identity.

The heart CLI exposes `research-map reviews`, `tasks`, `task-status`, `reconcile`, `ticket-branch`
and `ticket-answer`. It cannot create a human review. Long Pletor replies use
`pletor-answer --question ID --file dilna/out/answer.txt --ref CARD_ID`, avoiding shell-quoted
prose while keeping the existing permissions and the 8,000-character response limit.
