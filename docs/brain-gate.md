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
| H1c | **A strong control API.** Everything an agent needs to drive OPORA goes through the gate as typed kinds: read state, plan request, task, report, decision, question. Each kind has a JSON schema, an example and a `hint` on every error. The OpenAPI document is complete. | an agent drives one eval session using only the gate API and its OpenAPI, without the skill references |
| H1d | **MCP server on top of the gate.** The same kinds become typed MCP tools (`mcp__opora__*`), a thin layer over the HTTP gate with no logic of its own. | the same session through MCP: no shell, no permission denials |

H1b in detail (the task queue):
- **Table** in `project.sqlite`. It is new; no existing table changes.
  ```sql
  CREATE TABLE IF NOT EXISTS heart_tasks(
      seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
      project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT, title TEXT NOT NULL, body TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('ready','assigned','done','failed','cancelled')),
      session_id TEXT, attempts INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL, report TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
  CREATE INDEX IF NOT EXISTS heart_tasks_queue ON heart_tasks(project_id, workspace_id, status, seq);
  ```
- **Task body**, the fixed shape a worker gets:
  `{why, do, files[], doneWhen[], dontTouch[{path, heldBy}], context{intent?, rules[]?, pattern?}, commit, model}`.
  `model` is the worker's model (`sonnet` | `opus` | `haiku` | `fable`), default `sonnet` (eval m6: the same quality as
  Opus at about 55 % of the cost). The launcher (agent-office) starts the worker session with it. Tasks stored before
  the field existed read as `sonnet`.
  `title` and `do` are required.
- **Writing tasks.** Only a human, or later the heart, writes tasks:
  - `POST /api/brain/tasks {project, workspace, nodeId?, title, body}` → `201 task`;
  - `GET /api/brain/tasks?project&workspace&status?` lists tasks, reading is free;
  - `POST /api/brain/tasks/{id}/cancel?project=` cancels a task.
- **`next`** (gate kind, deterministic). Body `{}`.
  - If the session already holds an `assigned` task, it gets the same task again (idempotent).
  - Otherwise it gets the oldest `ready` task, which becomes `assigned` to the session.
  - With an empty queue it gets `{task: null, plan}`. `plan` lists the open cards with `{id, name, stage}` from the
    existing agent state, at most 20.
  - A worker session whose token has expired loses its `assigned` task, which goes back to `ready` the next time
    anyone calls `next`.
- **`report`** (gate kind, deterministic). Body `{taskId, sha, summary, checks: [{name, status: "green" | "red", output?}]}`.
  - The task must be `assigned` to this session.
  - `sha` must be 7–40 hex characters.
  - All checks green (a `done` report): the sha must exist as a commit in the workspace source repo
    (`WorkspaceSources.root(project, workspace)`, then `git -C <root> cat-file -e <sha>^{commit}`, 10 s timeout, run
    outside the project lock). An unknown sha is 422 `sha_unknown` with the hint "Commitni práci a nahlas sha z
    `git rev-parse HEAD`.". When the workspace has no source root, the root is unavailable, it is not a git repo, or
    git cannot run, the sha is accepted as before. A report with a red check skips this (the work may not be
    committed).
  - `checks` must not be empty.
  - Every check is written to `check_runs` (`CheckRuns.record`, scope `node_id`, otherwise the task id).
  - All checks green: the task becomes `done`.
  - Any check red: `attempts += 1`, and the task goes back to `ready`. On the second red it becomes `failed`.
  - The answer is `{task: {id, status, attempts}}`.
- **`release`** (gate kind, deterministic). Body `{taskId, reason}`; `reason` is a short required text (≤ 400
  chars). The worker gives a task back instead of letting it sit `assigned` until the token expires (8 h).
  - The task must be `assigned` to this session, otherwise 409 `task_not_assigned` (404 `task_not_found` for an
    unknown id).
  - The task goes back to `ready` with no session; `attempts` stay unchanged.
  - Emits `gate.task` with `{taskId, status: "ready", reason}`. The heart is **not** woken by it (it wakes only on
    `failed` and on queued tickets); it sees the reason in the event log and the task in its next snapshot.
  - The answer is `{task: {id, status, attempts}}`.
- **Event** `gate.task` with `{taskId, status}` on create, assign, done, failed, cancel and release (`reason` added).
- **Heart snapshot.** Every `assigned` task line shows its holder and since when it is held (`updated_at`, which
  `assign` sets; the table has no separate `assigned_at`).
- **Client** `.claude/skills/opora-control-center/scripts/opora_gate.py`, stdlib only:
  - commands: `session`, `next`, `ask`, `report`, `release`, `inbox`;
  - the token is kept in `<cwd>/.opora/gate.json`;
  - `report --check "npm test=green"` can be repeated.

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
