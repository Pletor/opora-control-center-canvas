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
  Before that it is recorded by the intake gate (`determinism/intake.py`): the same sentence again (`duplicate`) is
  kept in `messages.jsonl` with `duplicate: ie_…` but never queued, not even by the catch-up after a restart. An input
  with an intake entry (message, `change` / `ask` ticket via `inputs.resolve`) ends its batch line with
  `[vstup ie_… · <verdict> · jev 0.82 · oblast <area> · podobné: ie_…]`; a duplicate ticket still wakes the heart.
  Right before the message is built, `_batch` lets `decision/intake.py` classify `pending` entries through JEV
  (constructor argument `jev`: a callable returning `evaluate(state, questions)` with the app key, or None; the factory
  passes it, tests inject a fake). It never blocks a message, ticket or fragment and a JEV error never stops the batch.
  The `milestone.done` trigger (`docs/navrhy/2026-10-30-metriky-a-spoustece.md` §4) needs no new outbox event: after a
  `card.closed` event (and on the first read of a project) `inputs.milestone_wakes` adds a `milestoneDone` input
  (20 s window) for each met active milestone not woken yet (`heart_triggers`); the batch line is
  `- MILNÍK SPLNĚN ms_… „…“ (oblast …): odložené požadavky k otevření: rq_… „…“`.
  Card triggers (`determinism/triggers.py`) go the same way: `inputs.card_wakes` runs on the first read, after run
  or plan events (`inputs.TRIGGER_EVENTS`) at most once per `CARD_GAP` (60 s) per project, and every `CARD_POLL`
  (10 min, a stalled run sends no event); line `- SPOUŠTĚČ card.retry · <id> „…“: 2× selhal, doporučeno effort high`.
  `inputs.human_changes` turns a human acceptance of a plan (`changeset.accepted`) into `humanChange`, once per
  revision: `- SPOUŠTĚČ graph.human_change: člověk změnil plán (revize N)`. The prompt's section `Spouštěče` says
  what to do with each kind.
  At most one batch per project at a time and 6 automatic per hour (a human message skips the cap); a rate-limited batch puts the heart to sleep for 15 min
  and keeps its inputs. It runs only when `OPORA_HEART` is not `off` and `OPORA_CANVAS_HOST` is loopback
  (`tools/opora.py` sets it). Tests set `OPORA_HEART=off` in `backend/conftest.py`.
- `inputs.py`: event → input (`wake_input`) and the fresh data of each input right before a batch (`resolve`);
  a ticket answered in the meantime drops out.
- `batch.py`: one batch = one `claude -p` process. The message is the snapshot, the inputs and the instruction to end
  with `done`. Writes one line per batch to `brain/batches.jsonl` (inputs, session, cost per model from `modelUsage`,
  turns, error, duration, input tokens, summary from `done`). Detects `rate_limited` and `timeout` (15 min).
  Tokens: `inputTokens` = input summed over all turns (unchanged), `contextTokens` = context of the last turn,
  and the batch `usage` split as `fresh`, `cacheRead`, `cacheCreation`, `output` (additive fields). `parse` takes
  the `result` line of the stream and skips `system` / `assistant` / `user` events.
- `process.py`: runs the process with the message on stdin, inside a `WindowsJob` on Windows (killed as a tree).
- `command.py`: the CLI of §2 (`--output-format stream-json --verbose` for per-turn `usage`, `--model haiku --advisor opus`, `--resume` / `--session-id`, settings and empty MCP
  written as files in `brain/`, `dontAsk`, `--add-dir` = project source root), and the environment without API keys
  but with `OPORA_BASE_URL`, `OPORA_HEART_TOKEN`, `OPORA_PROJECT`, `OPORA_WORKSPACE`. Finds `claude.exe` /
  `claude.cmd` / `claude`.
- `session.py`: `brain/session.json = {sessionId, batches, lastInputTokens}`; `lastInputTokens` is the context of the
  last main-thread turn (`context_tokens`: `usage` of the last `assistant` event without `parent_tool_use_id`), not the
  sum over the batch. A new session when it passes 60k or after a failed batch. Without stream events it is estimated
  from the cumulative `usage`: cache writes + fresh input + cache reads / `num_turns`.
- `opora_heart.py`: the heart's only tool, stdlib (`snapshot`, `task`, `answer`, `cancel`, `escalate`, `intake`, `decide`, `rule`, `done`,
  and the workshop's `ctx`, `run`). `member --area <area>|none --nodes id1,id2 [--dry-run]` proposes area membership of
  existing cards and sectors as a graph proposal with `updateNodes` that change only `memberOf`; it never accepts it,
  the human does (`docs/brain-heart-orchestrator.md` O2d, test `backend/api/brain_opora/test_heart_member.py`). `steps --node ID --file F [--dry-run]` gives an existing
  card 2–8 steps with `kind` and `files` (short card grilling) as a spec changeset (`/api/oporahub/changesets`) and accepts
  it only under `autonomy.full` (test `backend/api/brain_opora/test_heart_steps.py`). It is copied into `brain/` before each batch so the Bash rule is
  `Bash(python opora_heart.py:*)`.
- Workshop (K3, `docs/brain-heart.md` §3b): `write_config` creates `brain/dilna/{data,scripts,out}` and copies
  `rlm.py` there. `ctx <name>` writes `GET /api/brain/heart/context` (`determinism/workshop.py`) to
  `dilna/data/<name>.json`; `ctx plan-of --project P` writes `plan-of-P.txt`, one line per node
  `id · path · name · stage` (`plan_lines`), `--full` the compact JSON for `rlm.load`, `--node N` the subtree JSON;
  `run <script>` runs `dilna/scripts/<script>.py` with `python -I` (a `-c` loader puts
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
  `research --requirement rq_…` is interrogation research: the per-requirement cap is checked before the desk runs and
  the cost is added to the requirement's brief (`docs/navrhy/2026-10-30-vyslech-srdce.md` §8).
- `skills/*.md`: mode procedures copied to `brain/skills/`, read only on demand via `opora_heart.py skill NAME`
  (`vyslech.md` when a batch carries `VÝSLECH`); never part of the system prompt.
- `prompt.md`: the heart's role, task shape with a full example (an implementation card has 2–8 steps, each with `kind`
  and `files`, so the card gauge can size it), application-wide rules, when to ask the advisor.

The heart token comes from `tokens.issue_heart` once per project and workspace; it lives only in memory and in the
environment of the process. Routes are in `backend/api/brain_opora/heart_routes.py`.

The human channel (the assistant panel talks to the heart) is in the frontend (`frontend/layout/heart-channel/`, contract
`docs/brain-heart-channel.md`); the old `claude_code/assistant/` was deleted in H2b2b.

Rule: the heart writes to OPORA only through `opora_heart.py`, with its role token.
