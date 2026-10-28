# determinism: layer 1 of the brain

This is the first layer of the brain. It answers without a model, at once and for free. It serves the gate for worker
sessions, the wall, and the facts the heart wakes up to.

Modules (H1a, contract `docs/brain-gate.md`):
- `gate.py`: worker sessions, requests (`next` | `ask` | `report` | `change`), the handler registry `kind -> handler`
  (`next` and `report` answer with the stub `{"pending": "H1b"}`), the human answer, the inbox with long-poll and
  the `gate.ticket` event. The router is in `backend/api/brain_opora/gate_routes.py`.
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

Still planned:
- `task_queue.py`: the task queue. `next` reads from the queue, and `report` triggers checks on the reported sha (H1b).
- `snapshot.py`: a deterministic project snapshot for the heart (at most about 4k tokens).
- `events.py`: reads `opora_events` and `PROCESS_SIGNAL` and turns them into wake-up candidates.
- `tool_policy.py`: tool classification for the heart (moved from `claude_code/assistant/approvals.py`).

Rule: nothing here calls a model, and nothing imports `decision` or `heart`.
