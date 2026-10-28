# determinism: layer 1 of the brain

This is the first layer of the brain. It answers without a model, at once and for free. It serves the gate for worker
sessions, the wall, and the facts the heart wakes up to.

Modules (H1a, contract `docs/brain-gate.md`):
- `gate.py`: worker sessions, requests (`next` | `ask` | `report` | `change`), the handler registry `kind -> handler`
  (`next` and `report` answer with the stub `{"pending": "H1b"}`), the human answer, the inbox with long-poll and
  the `gate.ticket` event. The router is in `backend/api/brain_opora/gate_routes.py`.
- `gate_payloads.py`: body checks of the gate and `GateError` (every refusal carries `code` and `hint`).
- `tokens.py`: worker and heart tokens (only `sha256` is stored, a worker token lives 8 h), verify and revoke.

Still planned:
- `wall.py` and the wall in the middleware, `gate_setting.py` (`settings.brain.gate`): the rest of H1a.
- `task_queue.py`: the task queue. `next` reads from the queue, and `report` triggers checks on the reported sha (H1b).
- `snapshot.py`: a deterministic project snapshot for the heart (at most about 4k tokens).
- `events.py`: reads `opora_events` and `PROCESS_SIGNAL` and turns them into wake-up candidates.
- `tool_policy.py`: tool classification for the heart (moved from `claude_code/assistant/approvals.py`).

Rule: nothing here calls a model, and nothing imports `decision` or `heart`.
