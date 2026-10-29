# heart: layer 3 of the brain

This is the third layer of the brain, the resident model of a project. It is Claude Code under the subscription, with
Haiku as the main model and Opus as the advisor. While OPORA runs on localhost it sleeps, and no process runs. A batch
of events or a human message wakes it up. It turns intent into tasks for workers and answers their tickets. It never
writes application code. Contract: `docs/brain-heart.md`.

Modules (H2a):
- `supervisor.py`: `HeartSupervisor`, a daemon thread started from the factory lifespan. It reads the event outbox of
  projects with the gate on: a queued `ask` / `change` ticket of a worker (`gate.ticket`, not `from: heart`) and a
  `failed` task (`gate.task`) become inputs with a 20 s batch window; a human message (`message()`) is first
  appended to `brain/messages.jsonl` (`determinism/brain_files.py`, read by the snapshot) and is due at once.
  At most one batch per project at a time and 6 automatic per hour (a human message skips the cap); a rate-limited batch puts the heart to sleep for 15 min
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
- `opora_heart.py`: the heart's only tool, stdlib (`snapshot`, `task`, `answer`, `cancel`, `escalate`, `decide`, `rule`, `done`,
  and the workshop's `ctx`, `run`). It is copied into `brain/` before each batch so the Bash rule is
  `Bash(python opora_heart.py:*)`.
- Workshop (K3, `docs/brain-heart.md` §3b): `write_config` creates `brain/dilna/{data,scripts,out}` and copies
  `rlm.py` there. `ctx <name>` writes `GET /api/brain/heart/context` (`determinism/workshop.py`) to
  `dilna/data/<name>.json`; `run <script>` runs `dilna/scripts/<script>.py` with `python -I` (a `-c` loader puts
  `dilna/` on `sys.path` for `import rlm`), cwd `dilna/`, 120 s, without the heart token, base URL and API keys,
  and appends `{at, script, args, exit, ms, subCalls, subCostUsd}` to `dilna/runs.jsonl`. `rlm.py` (stdlib):
  `load`, `files`, `read`, `grep` (read only, inside `OPORA_SOURCE_ROOT`), `chunks`, `sub` (one tool-less
  `claude -p --model haiku` per item, ≤ 20 per run counted in `OPORA_RLM_LOG`, depth 1). Write/Edit are allowed only
  by the settings `allow` rules for `dilna/scripts/**` and `dilna/out/**`; `batch.py` sums the run costs into
  `subCostUsd` of the journal entry.
- Research (K4, §3c): `opora_research.py` (stdlib, copied next to the tool) runs `research` (a `research` fragment
  in the brief vault, deterministic `prefetch` of the targets into `dilna/data/research/<id>/`, one researcher
  `claude -p` with Read/Grep/Glob and, only when a Chrome/Edge is found, REA web tools plus browser launch from
  `dilna/rea-mcp.json` with compact schemas, result via `research-update`) and `duel` (deterministic, Haiku sub-calls as actors
  `srdce-obhajce-a|b` and judges `srdce-soudce-1|2`, `duel-decide` by the server rule). Both log to `runs.jsonl`.
- `prompt.md`: the heart's role, task shape with a full example, application-wide rules, when to ask the advisor.

The heart token comes from `tokens.issue_heart` once per project and workspace; it lives only in memory and in the
environment of the process. Routes are in `backend/api/brain_opora/heart_routes.py`.

The human channel (the assistant panel talks to the heart) is in the frontend (`frontend/layout/heart-channel/`, contract
`docs/brain-heart-channel.md`); the old `claude_code/assistant/` was deleted in H2b2b.

Rule: the heart writes to OPORA only through `opora_heart.py`, with its role token.
