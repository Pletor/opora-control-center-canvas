# Brain gate: contract of `brain_opora/determinism` (H1)

Status: contract for H1. Source of truth for the code in `backend/brain_opora/determinism/` and
`backend/api/brain_opora/`. Background is in `docs/navrhy/2026-10-28-srdce-opory.md`.

Workers are agent sessions, for example from agent-office. They enter a project with the gate switched on **only
through the gate**: they send a request and the answer arrives in their inbox. Writes to the canvas come only from the
human and the heart. This layer never calls a model.

## 1. Switch per project

`project.json` → `settings.brain.gate: bool`, default `false`.
- Only a human may change it: `POST /api/brain/gate-setting {project, enabled}`, guarded by `require_human`.
- A project with the gate off behaves exactly as today. Nothing in this contract changes it.

## 2. Roles and tokens

| Role | Proof | How it is issued |
|---|---|---|
| human | UI cookie (`HumanSession`, as today) | — |
| heart | `X-Opora-Gate-Token`, row with `role = 'heart'` | only in-process, `tokens.issue_heart(project, workspace)` (used by H2), never through a route |
| worker | `X-Opora-Gate-Token`, row with `role = 'worker'` | `POST /api/gate/sessions` |

Rules:
- A token is 32 random bytes, url-safe. Only `sha256(token)` is stored. The token appears once, in the issuing response.
- A worker token lives 8 h (`expires_at`). Any expired or revoked token gets 401 `{code: "gate_token_invalid"}`.
- A token is bound to one `(project, workspace)`. Using it for another project gets 403 `{code: "gate_scope"}`.
- The gate is loopback-only (`is_loopback_only`). It is never reachable through the tunnel.

## 3. The wall (middleware)

The wall runs only for a project with `settings.brain.gate = true`. The project is taken from `project` in the query
or the body, the same way `_authority` does it.

| Request | Result |
|---|---|
| `GET` / `HEAD` | allowed as today (reading is free) |
| human | allowed as today |
| valid heart token for this project | allowed and treated as an agent with full autonomy in this project |
| `/api/gate/*` with a valid worker token | allowed |
| orchestrator lane (`LANE` in `determinism/wall.py`: card work such as `/api/oporahub/executions/*`, review jobs, `agent-output`; list in `docs/brain-heart-orchestrator.md` §2) | allowed with any token or none; canvas, proposals and rules stay walled |
| intent relay `POST /api/brain/heart/messages` (`RELAY` in `determinism/wall.py`, `docs/brain-heart-orchestrator.md` §8) with a valid worker token of this project | allowed; the route stores `via` = session name |
| anything else that writes | 403 `{error, code: "gate_required", hint: "Write through the gate: POST /api/gate/requests"}` |

## 4. Gate API (`backend/api/brain_opora/gate_routes.py`)

| Call | Body / query | Answer |
|---|---|---|
| `POST /api/gate/sessions` | `{project, workspace, worker: {name, office?, floor?}}` | `201 {sessionId, token, expiresAt}` |
| `GET /api/gate/kinds` | header token, or none | `200 {role, kinds}`: the kinds of the caller's role with schemas, example and error codes (`docs/brain-control-api.md` §1) |
| `POST /api/gate/requests` | header token (worker or heart); `{kind, body}` with a kind from `determinism/kinds.py` | `201 {ticketId, seq, kind, status, answer?}`; a worker sending a heart kind gets 403 `heart_required` |
| `GET /api/gate/inbox` | header token; `?after=<answeredSeq>&wait=<0..30>` | `200 {tickets: [...], last}`: answered tickets of **this session** with `answeredSeq > after`, in answer order (`answeredSeq` grows per project on every answer, so a ticket answered late is never lost behind the cursor). With `wait > 0` the call waits until such a ticket exists or `wait` seconds pass (long-poll). |
| `GET /api/gate/tickets/{id}` | header token (own ticket) or human | `200 ticket` |
| `POST /api/gate/tickets/{id}/answer` | heart token or human; `{answer}` | `200 ticket` with `status: answered` |
| `POST /api/brain/gate-setting` | human; `{project, enabled}` | `200 {project, enabled}` |

**Ticket:** `{ticketId, seq, sessionId, kind, body, status: queued | answered, answer, answeredBy, createdAt,
answeredAt}`.

**Handlers.** The table `determinism/kinds.py` maps each kind to its body check and handler (H1c):
- A **deterministic handler** answers in the same request (`status: answered`, `answeredBy: "gate"`); such tickets stay
  for the audit but do not appear in the inbox. `ask` and `change` have none: they stay `queued` until the heart or a
  human answers them.
- The first work kinds (`next`, `report`) were a stub and then a task queue; the ticket of work replaced them in PR 5c.

**Events.** Creating and answering a ticket emits `opora_events` with kind `gate.ticket` and payload
`{ticketId, kind, status}`. Later this event wakes the heart (H2).

**Errors.**
- Every 4xx carries `code` and `hint`, as in #139.
- An unknown `kind` gets 422 with `hint` listing the allowed kinds.
- A body over 64 KB gets 413.

## 5. Storage (new tables in `project.sqlite`, approved 2026-10-28)

```sql
CREATE TABLE IF NOT EXISTS gate_sessions(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('heart','worker')), worker_name TEXT NOT NULL, worker_meta TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS gate_tickets(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, session_id TEXT NOT NULL,
    kind TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','answered')),
    answer TEXT, answered_by TEXT, created_at TEXT NOT NULL, answered_at TEXT, answered_seq INTEGER);
CREATE INDEX IF NOT EXISTS gate_tickets_session ON gate_tickets(session_id, seq);
CREATE INDEX IF NOT EXISTS gate_tickets_inbox ON gate_tickets(session_id, answered_seq);
CREATE INDEX IF NOT EXISTS gate_tickets_queue ON gate_tickets(project_id, workspace_id, status, seq);
```

The task table `heart_tasks` of H1b was replaced by the ticket of work in PR 5c; `drop_retired_tables` drops it.

## 6. Steps

| Step | Content | Done when |
|---|---|---|
| H1a | §2 tokens, §4 sessions, tickets, inbox and answer (human only), §5 tables, `gate.ticket` events | targeted tests green: session → `ask` queued → human answers → inbox; foreign project 403, invalid token 401 |
| H1a2 | §1 switch, §3 wall, heart token as full autonomy | in a project with the gate on, a write without a token is refused and a worker token can use only the gate |
| H1b | task queue and `opora_gate.py` client for workers (replaced by the ticket of work in PR 5c) | a worker finishes eval session S2 only through the gate, using hand-written tasks |
| H1c | **A strong control API.** Everything an agent needs to drive OPORA goes through the gate as typed kinds: read state, plan request, task, report, decision, question. Each kind has a JSON schema, an example and a `hint` on every error. The OpenAPI document is complete. | an agent drives one eval session using only the gate API and its OpenAPI, without the skill references |
| H1d | **MCP server on top of the gate.** The same kinds become typed MCP tools (`mcp__opora__*`), a thin layer over the HTTP gate with no logic of its own. | the same session through MCP: no shell, no permission denials |

H1b (the task queue) is replaced by the ticket of work in PR 5c: `heart_tasks`, `/api/brain/tasks` and the kinds
`next`, `report`, `release`, `task.create`, `task.cancel` are deleted without backward compatibility. Work now flows as
a ticket (`docs/navrhy/2026-11-03-novy-zaklad.md` §3.3):
- **Kinds.** The heart issues `ticket.issue` (cancel `ticket.cancel`, answer a question with `ticket.answer` carrying
  a `feedbackId`). A worker or the office calls `ticket.request` → `ticket.claim` (optional `executionId`) →
  `ticket.feedback` (bug / idea / improvement / question; a question moves the ticket to `needs_answer`) →
  `ticket.deliver` (summary, sha). `ticket.release` gives a claimed ticket back (claimed → issued).
- **Takeover.** `ticket.claim` from another session of the same workspace takes over a held ticket when its
  `executionId` equals the ticket's `machine.executionId` (same execution after an office restart) or when the
  holder's session expired, was revoked or is gone. The state stays, the new session holds the ticket and the event
  `ticket.resumed {ticketId, fromSession, toSession}` is emitted; otherwise 409 `ticket_not_held`. `ticket.request`
  never offers a ticket held by someone else.
- **Office routing.** `machine.department` / `machine.profile` (slug `^[a-z0-9][a-z0-9-]{0,39}$` or null) are set by
  the heart in `ticket.issue` (`opora_heart.py task|ticket-issue --department D --profile P`).
- **States.** draft, issued, claimed, in_progress, needs_answer, delivered, verified, closed, failed, cancelled.
- **Reading.** `GET /api/brain/tickets?project&workspace&status?` and `GET /api/brain/tickets/{id}?project=`.
- **Failure.** When the execution is cancelled, `ticket_lifecycle.follow` moves the ticket to `failed` and emits the
  outbox event `ticket.failed {ticketId, status, reason}`; the heart turns it into the input `workFailed`.
- **Client** `backend/brain/seed/opora-control-center/skills/opora-control-center/scripts/opora_gate.py`, stdlib only:
  - commands: `session`, `request`, `claim --ticket [--execution]`, `feedback --ticket --kind TEXT`,
    `deliver --ticket --summary [--sha]`, `release --ticket`, `ask`, `change --reason`, `inbox`, `tell`;
  - the token is kept in `<cwd>/.opora/gate.json`.

H1a2 in detail:
- **Switch.** `settings.brain = {gate: bool, since?, by?}` lives in `project.json` next to `agentAutonomy`. Reading and
  writing mirror `project_hub.agent_autonomy` / `set_agent_autonomy`. `POST /api/brain/gate-setting` takes
  `{project, enabled}` and is human only.
- **Wall.** A pure function `wall.decide(method, path, actor, gate_on, token)` returns allow, or a refusal with
  status, `code` and `hint`. The `boundary` middleware calls it after `_authority`, and only for projects with the gate
  on. Projects with the gate off keep exactly today's behaviour.
- **Heart token.** A request carrying a valid heart token for the request's project gets `authority = resolve(actor,
  True)`, the same as full autonomy, but only in that project. A worker token outside `/api/gate/*` gets 403
  `gate_required`.
