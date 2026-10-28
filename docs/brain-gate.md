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
| anything else that writes | 403 `{error, code: "gate_required", hint: "Write through the gate: POST /api/gate/requests"}` |

## 4. Gate API (`backend/api/brain_opora/gate_routes.py`)

| Call | Body / query | Answer |
|---|---|---|
| `POST /api/gate/sessions` | `{project, workspace, worker: {name, office?, floor?}}` | `201 {sessionId, token, expiresAt}` |
| `POST /api/gate/requests` | header token; `{kind, body}` with `kind ∈ next \| ask \| report \| change` | `201 {ticketId, seq, kind, status, answer?}` |
| `GET /api/gate/inbox` | header token; `?after=<answeredSeq>&wait=<0..30>` | `200 {tickets: [...], last}`: answered tickets of **this session** with `answeredSeq > after`, in answer order (`answeredSeq` grows per project on every answer, so a ticket answered late is never lost behind the cursor). With `wait > 0` the call waits until such a ticket exists or `wait` seconds pass (long-poll). |
| `GET /api/gate/tickets/{id}` | header token (own ticket) or human | `200 ticket` |
| `POST /api/gate/tickets/{id}/answer` | heart token or human; `{answer}` | `200 ticket` with `status: answered` |
| `POST /api/brain/gate-setting` | human; `{project, enabled}` | `200 {project, enabled}` |

**Ticket:** `{ticketId, seq, sessionId, kind, body, status: queued | answered, answer, answeredBy, createdAt,
answeredAt}`.

**Handlers.** `gate.py` keeps a registry `kind → handler`:
- A **deterministic handler** answers in the same request (`status: answered`). `ask` and `change` have none: they stay
  `queued` until the heart or a human answers them.
- In H1a, `next` and `report` answer with the stub `{"pending": "H1b"}`.
- H1b replaces the stub with the task queue (`heart_tasks`) and checks on a sha.

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

`heart_tasks` is added in H1b. No existing table changes.

## 6. Steps

| Step | Content | Done when |
|---|---|---|
| H1a | §2 tokens, §4 sessions, tickets, inbox and answer (human only), §5 tables, `gate.ticket` events | targeted tests green: session → `ask` queued → human answers → inbox; foreign project 403, invalid token 401 |
| H1a2 | §1 switch, §3 wall, heart token as full autonomy | in a project with the gate on, a write without a token is refused and a worker token can use only the gate |
| H1b | `heart_tasks`, `next` from the queue with a fallback to the plan, `report` → checks on the sha, `opora_gate.py` client for workers | a worker finishes eval session S2 only through the gate, using hand-written tasks |
