# determinism: layer 1 of the brain

This is the first layer of the brain. It answers without a model, at once and for free. It serves the gate for worker
sessions, the wall, and the facts the heart wakes up to.

Modules (H1a, contract `docs/brain-gate.md`):
- `gate.py`: sessions and their verification, writing a ticket (`record`; a synchronous kind's ticket is answered
  by `gate` for the audit), the human or heart answer, the heart's escalation (a queued `ask` `{text, for: "human"}`)
  and the inbox with long-poll (tickets answered by `gate` never reach the inbox: their answer came in the response).
  The router is in `backend/api/brain_opora/gate_routes.py`.
- `gate_payloads.py`: body checks of the gate (`shaped` for exact-key kind bodies, `inbox_body`) and `GateError`
  (every refusal carries `code` and `hint`).
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

Modules (H1c, contract `docs/brain-control-api.md`):
- `kinds.py`: the single table of request kinds (`next`, `ask`, `report`, `change`, `state`, `inbox` for workers;
  `task.create`, `task.cancel`, `ticket.answer`, `escalate` for the heart). Each kind has role, description,
  input/output schema, example, error codes with `hint`, a body check and a handler (`ask` / `change` have none and
  stay queued). `run` serves `POST /api/gate/requests`: a worker sending a heart kind gets 403 `heart_required`, a
  refused body leaves no ticket. `visible(role)` serves `GET /api/gate/kinds`.
- `kind_schemas.py`: the JSON schemas and examples of the kinds (data only).
- `snapshot.py` also builds `view`, the JSON of the `state` kind; `rules` are the approved project rules of the
  Desktop v3 memory, then the `context.rules` of the tasks (no repeats).

Modules (H2a, contract `docs/brain-heart.md`):
- `snapshot.py`: the deterministic project snapshot for the heart (§3): project and workspace, intent (project goal,
  else the home page goal and feel), plan pages with their stage (≤ 20, else open cards), task queue counts and the
  last 10 tasks, waiting tickets (≤ 10), last checks (≤ 10). `collect` reads, `render` is pure; the text is cut at
  12 000 characters.

Modules (K1, contract `docs/brain-heart.md` §3a, the heart's surroundings):
- `brain_files.py`: the project's `brain/` folder (`brain_dir`), durable human messages `brain/messages.jsonl`
  (`append_message`, `messages` = last 5 of a workspace) and the batch journal `brain/batches.jsonl` (`journal`).
  It lives here, not in `heart/`, because the snapshot reads both and determinism must not import the heart.
- `snapshot.py` adds `ZPRÁVY ČLOVĚKA`, `PRAVIDLA` (Desktop v3 rules with scope `project`: approved, then
  `(návrh)`; ≤ 20), `ROZHODNUTÍ` (pinned, then newest; ≤ 10) after `ZÁMĚR` and `DENÍK` (last 5 batch summaries) at
  the end. An unreadable source is an empty section (`- žádné`), never an error.
- `task_queue.py` / `gate.py`: tasks and ticket answers may come from the heart of the same project
  (`created_by` / `answeredBy = "heart"`, event actor `agent heart`). A task has an optional `order`: `next` takes
  the lowest `order`, then the lowest `seq` (column `task_order`, added to older tables by `ensure_order_column`).
  The `gate.ticket` event of a new ticket carries `from` (the session role), so the heart's own escalation does not
  wake it.

Modules (K3, contract `docs/brain-heart.md` §3b, the heart's workshop):
- `workshop.py`: `context(service, project, workspace, name)` = the data of `ctx <name>`: `tasks`, `tickets`,
  `journal`, `messages`, `rules`, `decisions` (all, not capped like the snapshot) and `tree` (source files
  `{path, size, mtime}` without `node_modules`, `.git`, build output and links, ≤ 20 000). Route
  `GET /api/brain/heart/context` (heart token of the same project and workspace only).
- `brain_files.scripts` + `snapshot.py`: section `DÍLNA` after `DENÍK` = the scripts in `brain/dilna/scripts/` with
  the first docstring line (≤ 15).
- `snapshot.py`: section `VÝZKUM` after `DÍLNA` = live `research` and `duel` fragments of the brief vault whose
  first revision the heart wrote (verdict or outcome and p, ≤ 10; docs/brain-heart.md §3c).

Still planned:
- `events.py`: reads `opora_events` and `PROCESS_SIGNAL` and turns them into wake-up candidates.
- `tool_policy.py`: tool classification for the heart (the old assistant's `approvals.py` was deleted in H2b2b; today
  `heart/command.py` limits the tools with `--allowedTools`).

Modules (intake gate, slice 1, contract `docs/navrhy/2026-10-30-vstupni-brana.md`):
- `intake.py`: every sentence from the heart panel (`heart_message`), a worker's `change` / `ask` ticket
  (`gate_change` / `gate_ask`, written by `gate.record`; the heart's own escalation is skipped) and a new brief vault
  fragment of kind `brief` / `question` (`brief_fragment`, revision 1 only) becomes an immutable entry `ie_…` in
  `intake_entries` (repository `database/repositories/intake_entries.py`). The fingerprint is sha256 of the
  normalized text (lower case, no diacritics or punctuation, single spaces). The same fingerprint in the same
  workspace = verdict `duplicate` (requirement, area and milestone copied from the earlier entry), else `pending`
  (layer `determinism`). Candidates are the 3 nearest earlier entries by FTS5 bm25; they are not stored and only go
  into the heart's input line. `safe_record` runs under a savepoint and never breaks the original flow.
  `overview` backs `GET /api/intake`. `snapshot.py` shows the last 8 entries the heart has not confirmed yet (layer
  `determinism` or `jev`) as `VSTUPY` with the verdict, JEV confidence and area (omitted when empty).
  `confirm` (slice 2) is the heart's verdict (`POST /api/brain/heart/intake`, `opora_heart.py intake`): one of the six
  verdicts of §3, layer `heart`, only for an entry of the token's workspace; the sentence itself never changes.
- `intake_setting.py` (slice 2, §7): `settings.brain.intake = {jev, jevPerDay}` in `project.json` next to the gate
  switch. Missing or corrupt = JEV off, 200 calls a day. Only a human changes it (`POST /api/brain/intake-setting`);
  `gate_setting.write` keeps it when the gate is flipped.

Rule: nothing here calls a model, and nothing imports `decision` or `heart`.
