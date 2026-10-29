# Brain heart: contract of `brain_opora/heart` (H2)

Status: contract for H2. Background is `docs/navrhy/2026-10-28-srdce-opory.md` §4. The gate and task queue it builds
on are in `docs/brain-gate.md`.

The heart is the project's resident model: Claude Code under the subscription, with Haiku as the main model and Opus as
the advisor. **It turns intent into precise tasks** and answers worker questions. It never writes application code.
Workers (`opora_gate.py next → work → report`) do the coding.

## 1. Inputs that wake it

| Input | Source | Wakes |
|---|---|---|
| human message (intent, change, question) | `POST /api/brain/heart/messages {project, workspace, text}` (human only) | at once |
| queued ticket `ask` / `change` | `gate.ticket` event with `status: queued` | after a 20 s batch window |
| task `failed` (second red) | `gate.task` event with `status: failed` | after a 20 s batch window |

In H2a the supervisor wakes on **all** of these. JEV filtering is H3. The supervisor runs only while OPORA runs on
loopback and only for projects with `settings.brain.gate = true`. It never runs two batches of one project at once.
A wake that arrives during a batch is queued and becomes the next batch.

## 2. One batch = one process

H2a is **one-shot**, not a resident stream: a batch is one `claude -p` process. Continuity comes from `--resume`.

```
claude -p --output-format json --model haiku --advisor opus
  [--resume <sessionId> | --session-id <new uuid>]
  --setting-sources project --settings <json: deny rules, disableAllHooks>
  --strict-mcp-config --mcp-config {"mcpServers":{}}
  --allowedTools "Read,Grep,Glob,Bash(python <tool>:*)" --permission-mode dontAsk
  --append-system-prompt-file backend/brain_opora/heart/prompt.md
  --add-dir <project source root (read only by policy)>
  --max-turns 40
  "<batch message>"
cwd = <data>/projects/<id>/brain/       env: without ANTHROPIC_API_KEY; OPORA_BASE_URL, OPORA_HEART_TOKEN, OPORA_PROJECT, OPORA_WORKSPACE
```

- **Token.** The heart token comes from `tokens.issue_heart`, once per project. It is kept in memory and in the env
  of the process only, never on disk.
- **Batch message.** It contains a deterministic snapshot (§3), then the inputs of this batch (human messages, queued
  tickets, failed tasks), then the instruction to finish with `opora_heart.py done --summary`.
- **Output.** The JSON result gives `session_id`, `total_cost_usd`, `modelUsage`, `num_turns` and `is_error`. They
  are written to `brain/batches.jsonl` as one line per batch, together with the inputs and the cost per model.
  Advisor usage is the Opus entry in `modelUsage`.
- **Rotation.** When the last batch's `usage` input passes 60k tokens, the next batch starts a new session
  (`--session-id`) with a fresh snapshot. `brain/session.json` holds `{sessionId, batches, lastInputTokens}`.
- **Limits.**
  - `is_error` with `rate_limit`, or the text "hit your … limit", puts the supervisor to sleep for 15 min and keeps
    the inputs.
  - At most 6 automatic batches (tickets, failed tasks) per hour per project. A batch with a human message skips
    this cap (eval m2: the cap held back the human's next brief); the subscription sleep still applies.
  - Timeout 15 min per batch: the job is killed and the batch is written as `timeout`.
  - Advisor cap: when the Opus entries of today's batches (UTC) reach 2 USD for the project, the next batches run
    without `--advisor` and are journaled with `advisor: false`. Eval m3/m6: the advisor is 86 % of the heart's cost,
    and the most expensive session cost 0.37 USD.

## 3. Snapshot (`determinism/snapshot.py`, ≤ about 4k tokens)

```
PROJEKT <name> · workspace <w>
ZÁMĚR: <application site goal / feel, if any>
PLÁN: <pages: name, path, stage> (≤ 20)
FRONTA ÚKOLŮ: ready n · assigned n (by whom) · done n · failed n; last 10 titles with status
LÍSTKY ČEKAJÍCÍ: <id kind text> (≤ 10)
POSLEDNÍ KONTROLY: <scope sha status> (≤ 10)
```

It is deterministic and has no model behind it. It is cut at a hard character limit.

## 4. The heart's tool (`heart/opora_heart.py`, stdlib, one call = one intent)

| Command | Does |
|---|---|
| `snapshot` | prints the snapshot again |
| `task --title T --do D [--why] [--file F]… [--done-when C]… [--dont-touch P]… [--node N]` | `POST /api/brain/tasks` with the heart token |
| `answer --ticket ID --text T` | `POST /api/gate/tickets/{id}/answer` with the heart token |
| `cancel --task ID` | cancels a task |
| `escalate --text T` | records a question for the human: an `ask` ticket created by the heart, visible in the velín |
| `done --summary S` | ends the batch; the summary goes to `batches.jsonl` |

Errors print `code` and `hint`, and the exit code is not zero.

## 5. Gate changes needed by H2a (determinism)

- `POST /api/brain/tasks`, `/cancel` and `POST /api/gate/tickets/{id}/answer` accept the **heart token** of the same
  project as well as a human. `answeredBy` is then `"heart"`.
- The `task` body gets an optional `order` field. A lower order goes first; when orders are equal, `seq` decides.
  This lets the heart sequence its plan.

## 6. The heart's prompt (`heart/prompt.md`, Czech)

The prompt has these parts:
1. **Role.** You are the heart of the project. You turn intent into tasks for workers. You never write code.
2. **Shape of a task.** One task is a verifiable increment, a page or a section, done in 10–30 minutes of a worker's
   time. It always states:
   - `do`, concrete enough that the worker does not need the original brief;
   - `files`;
   - `doneWhen`: what `npm run build`, `npm test` and an observable behaviour must show;
   - the rules of the whole application, repeated in `context.rules`.
3. **Consult the advisor only for:**
   - breaking a new intent down into a plan;
   - a conflict between a request and the intent;
   - a task that failed twice.
4. **Conflict with intent.** Report it with `escalate`, and do not plan an element that goes against the intent.
5. **Ending.** Always finish with `done`.

## 7. Steps

| Step | Content | Done when |
|---|---|---|
| H2a | §1–§6: supervisor, one-shot batch, snapshot, tool, heart token in tasks and answers, `brain/` folder, `batches.jsonl` | **live smoke run**: a human message with a two-page intent leads to ≥ 2 well-formed tasks in the queue, at measured cost |
| H2b | the human channel (assistant panel → heart) and deletion of `claude_code/assistant/` | the panel works with the heart |
| eval E | arm E in the multi-session eval: the session prompt goes to the heart as a human message; workers get only the gate instructions | quality and cost compared with arm C of m1 |
