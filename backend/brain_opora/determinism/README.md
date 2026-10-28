# determinism: layer 1 of the brain

This is the first layer of the brain. It answers without a model, at once and for free. It serves the gate for worker
sessions, the wall, and the facts the heart wakes up to.

Planned modules (H1):
- `gate.py`: worker sessions, requests (`next` | `ask` | `report` | `change`) and the inbox. The router is in
  `backend/api/brain_opora/`.
- `tokens.py`: role tokens for human, heart and worker, and the wall middleware.
- `task_queue.py`: the task queue. `next` reads from the queue, and `report` triggers checks on the reported sha.
- `snapshot.py`: a deterministic project snapshot for the heart (at most about 4k tokens).
- `events.py`: reads `opora_events` and `PROCESS_SIGNAL` and turns them into wake-up candidates.
- `tool_policy.py`: tool classification for the heart (moved from `claude_code/assistant/approvals.py`).

Rule: nothing here calls a model, and nothing imports `decision` or `heart`.
