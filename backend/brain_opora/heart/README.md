# heart: layer 3 of the brain

This is the third layer of the brain, the resident model of a project. It is Claude Code under the subscription, with
Haiku as the main model and Opus as the advisor. While OPORA runs on localhost it sleeps, and no process runs. A batch
of events or a human message wakes it up. It turns intent into tasks for workers and answers their tickets. It never
writes application code. Contract: `docs/brain-heart.md`.

Modules (H2a):
- `supervisor.py`: `HeartSupervisor`, a daemon thread started from the factory lifespan. It reads the event outbox of
  projects with the gate on: a queued `ask` / `change` ticket of a worker (`gate.ticket`, not `from: heart`) and a
  `failed` task (`gate.task`) become inputs with a 20 s batch window; a human message (`message()`) is due at once.
  At most one batch per project at a time and 6 per hour; a rate-limited batch puts the heart to sleep for 15 min
  and keeps its inputs. It runs only when `OPORA_HEART` is not `off` and `OPORA_CANVAS_HOST` is loopback
  (`tools/opora.py` sets it). Tests set `OPORA_HEART=off` in `backend/conftest.py`.
- `inputs.py`: event → input (`wake_input`) and the fresh data of each input right before a batch (`resolve`);
  a ticket answered in the meantime drops out.
- `batch.py`: one batch = one `claude -p` process. The message is the snapshot, the inputs and the instruction to end
  with `done`. Writes one line per batch to `brain/batches.jsonl` (inputs, session, cost per model from `modelUsage`,
  turns, error, duration, input tokens, summary from `done`). Detects `rate_limited` and `timeout` (15 min).
- `process.py`: runs the process with the message on stdin, inside a `WindowsJob` on Windows (killed as a tree).
- `command.py`: the CLI of §2 (`--model haiku --advisor opus`, `--resume` / `--session-id`, settings and empty MCP
  written as files in `brain/`, `dontAsk`, `--add-dir` = project source root), and the environment without API keys
  but with `OPORA_BASE_URL`, `OPORA_HEART_TOKEN`, `OPORA_PROJECT`, `OPORA_WORKSPACE`. Finds `claude.exe` /
  `claude.cmd` / `claude`.
- `session.py`: `brain/session.json = {sessionId, batches, lastInputTokens}`; a new session above 60k input tokens
  or after a failed batch.
- `opora_heart.py`: the heart's only tool, stdlib (`snapshot`, `task`, `answer`, `cancel`, `escalate`, `done`).
  It is copied into `brain/` before each batch so the Bash rule is `Bash(python opora_heart.py:*)`.
- `prompt.md`: the heart's role, task shape with a full example, application-wide rules, when to ask the advisor.

The heart token comes from `tokens.issue_heart` once per project and workspace; it lives only in memory and in the
environment of the process. Routes are in `backend/api/brain_opora/heart_routes.py`.

Still planned (H2b): `human_channel.py` (the assistant panel talks to the heart) and deleting `claude_code/assistant/`.

Rule: the heart writes to OPORA only through `opora_heart.py`, with its role token.
