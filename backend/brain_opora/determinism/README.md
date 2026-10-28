# determinism: layer 1 of the brain

This is the first layer of the brain. It answers without a model, at once and for free. It serves the gate for worker
sessions, the wall, and the facts the heart wakes up to.

Modules (H1a, contract `docs/brain-gate.md`):
- `gate.py`: worker sessions, requests (`next` | `ask` | `report` | `change`), the handler registry `kind -> handler`
  (`handler(service, session, body, now)`, run before the ticket is written: a refused request leaves no ticket),
  the human answer, the inbox with long-poll and the `gate.ticket` event. The router is in `backend/api/brain_opora/gate_routes.py`.
- `gate_payloads.py`: body checks of the gate and `GateError` (every refusal carries `code` and `hint`).
- `tokens.py`: worker and heart tokens (only `sha256` is stored, a worker token lives 8 h), verify and revoke.

Modules (H1a2):
- `gate_setting.py`: the per-project switch `settings.brain = {gate, since?, by?}` in `project.json`, next to
  `agentAutonomy`. Missing or corrupt value = off. Only a human flips it (`POST /api/brain/gate-setting`).
- `wall.py`: the wall of §3. `decide(method, path, actor, gate_on, token, project)` is a pure function over the
  table; `check(...)` reads the switch and verifies the token, `relevant(...)` is the cheap pre-check. The
  `boundary` middleware in `backend/app/factory.py` calls it after `_authority`. A valid heart token for the request's
  project gets `authority = resolve("agent", True)` in that project only; a request without an agent header is then
  logged as agent `heart`. Projects with the gate off never reach `decide`.

Modules (H1b):
- `task_queue.py`: the task queue `heart_tasks` (repository `database/repositories/heart_tasks.py`). `create`,
  `list_tasks`, `cancel` back `POST|GET /api/brain/tasks` and `POST /api/brain/tasks/{id}/cancel` (writes human
  only). `next_task` is the `next` handler: the held task again (idempotent), else the oldest `ready`; tasks of
  expired or revoked sessions go back to `ready` first; an empty queue answers `{task: null, plan}` with at most 20
  open cards `{id, name, stage}` from `ProcessSync` (the card overview agent-state is built from; `stage` is its
  process status), read after the queue lock is released. `report` is the `report` handler: every check goes to
  `check_runs` (`CheckRuns.record`, scope `nodeId` or the task id, sha lowercased); all green = `done`, red = back
  to `ready` with `attempts + 1`, the second red = `failed`. Event `gate.task {taskId, status}` on create, assign,
  done, failed and cancel.
- `task_payloads.py`: body checks of tasks and reports (`invalid_payload`, `invalid_sha`, `checks_required`); a task
  body is filled to the fixed shape `{why, do, files, doneWhen, dontTouch, context, commit}`.
- Worker client: `.claude/skills/opora-control-center/scripts/opora_gate.py` (reference `references/gate.md`).

Modules (H2a, contract `docs/brain-heart.md`):
- `snapshot.py`: the deterministic project snapshot for the heart (§3): project and workspace, intent (project goal,
  else the home page goal and feel), plan pages with their stage (≤ 20, else open cards), task queue counts and the
  last 10 tasks, waiting tickets (≤ 10), last checks (≤ 10). `collect` reads, `render` is pure; the text is cut at
  12 000 characters.
- `task_queue.py` / `gate.py`: tasks and ticket answers may come from the heart of the same project
  (`created_by` / `answeredBy = "heart"`, event actor `agent heart`). A task has an optional `order`: `next` takes
  the lowest `order`, then the lowest `seq` (column `task_order`, added to older tables by `ensure_order_column`).
  The `gate.ticket` event of a new ticket carries `from` (the session role), so the heart's own escalation does not
  wake it.

Still planned:
- `events.py`: reads `opora_events` and `PROCESS_SIGNAL` and turns them into wake-up candidates.
- `tool_policy.py`: tool classification for the heart (moved from `claude_code/assistant/approvals.py`).

Rule: nothing here calls a model, and nothing imports `decision` or `heart`.
