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
    Only a batch that really runs counts: a batch whose inputs were all resolved before it started (`resolve`
    is empty) does not use the cap (probe r1: phantom batches made the 7th ticket wait 53 min).
  - Timeout 15 min per batch: the job is killed and the batch is written as `timeout`.
  - Advisor cap: when the Opus entries of today's batches (UTC) reach 2 USD for the project, the next batches run
    without `--advisor` and are journaled with `advisor: false`. Eval m3/m6: the advisor is 86 % of the heart's cost,
    and the most expensive session cost 0.37 USD.

## 3. Snapshot (`determinism/snapshot.py`, ≤ about 4k tokens)

```
PROJEKT <name> · workspace <w>
ZÁMĚR: <application site goal / feel, if any>
ZPRÁVY ČLOVĚKA: <at text> (last 5 of the workspace, ≤ 400 chars each)
PRAVIDLA: <project rules: approved, then "(návrh)"> (≤ 20)
ROZHODNUTÍ: <decisions: pinned, then newest> (≤ 10)
PLÁN: <pages: name, path, stage> (≤ 20)
FRONTA ÚKOLŮ: ready n · assigned n (by whom) · done n · failed n; last 10 titles with status
LÍSTKY ČEKAJÍCÍ: <id kind text> (≤ 10)
POSLEDNÍ KONTROLY: <scope sha status> (≤ 10)
DENÍK: <at [status] summary> (last 5 batches)
```

An empty section prints `- žádné` (§3a).

It is deterministic and has no model behind it. It is cut at a hard character limit.

## 3a. The heart's surroundings: it never works blind (K1, K2)

The heart is a fresh `claude -p` per batch and its session rotates at 60k tokens, so everything it must know to
continue has to live in OPORA and come back in the snapshot. Probe r1 (2026-10-29): the human's intent was lost
(`ZÁMĚR: —`), permissions given in an answer vanished, and the heart re-escalated what was already decided.
Nothing new is stored in a new table: the surroundings reuse what the application already has.

| Surrounding | Source (existing) | In the snapshot | The heart writes it with |
|---|---|---|---|
| intent of the human | `settings.goal`, home page goal/feel, **and the human's messages** | `ZÁMĚR` + `ZPRÁVY ČLOVĚKA` (last 5, newest last, ≤ 400 chars each) | — (the human writes) |
| memory: decisions | Desktop v3 `decisions` of the workspace (`/api/desktop-v3/decision`) | `ROZHODNUTÍ` (pinned first, then newest; ≤ 10) | `decide --text T [--node N] [--pin]` |
| memory: application rules | Desktop v3 `rules` with scope `project` (`/api/desktop-v3/rule`); a rule by the heart is a proposal (`by: agent`) until the human approves it | `PRAVIDLA` (approved, then `(návrh)`; ≤ 20) | `rule --text T` |
| journal | `brain/batches.jsonl` summaries | `DENÍK` (last 5 summaries with time and status) | `done --summary` |
| project source | the workspace source root (`--add-dir`, read only) | — | reads `CLAUDE.md`, `README`, `package.json` and the existing components before planning |

- **Human messages are durable.** `POST /api/brain/heart/messages` appends `{at, workspace, text}` to
  `brain/messages.jsonl` before it queues the input (server-side, in the project's own `brain/` folder like
  `batches.jsonl`). The snapshot reads the last 5 of the batch's workspace from there.
- **Decisions keep what answers promise.** Every permission or ruling the heart gives in `answer` (a file the
  worker may change, which of two texts wins, an order of work) is also written as `decide`, so it survives
  rotation and the next batch sees it. Rules of the whole application go as `rule`; the human approves them in the
  memory panel. The heart repeats in `--rule` the approved rules and its own proposals (a rejected proposal is
  removed, so it drops out of the snapshot); without proposals the first plan would carry no rules at all.
- **Order of the snapshot:** `PROJEKT`, `ZÁMĚR`, `ZPRÁVY ČLOVĚKA`, `PRAVIDLA`, `ROZHODNUTÍ`, `PLÁN`, `FRONTA ÚKOLŮ`,
  `LÍSTKY ČEKAJÍCÍ`, `POSLEDNÍ KONTROLY`, `DENÍK`. Each section has its own line cap; the whole text keeps the
  12 000-character limit. An unreadable source is an empty section, never an error.
- Steps: **K1** = durable messages and the four new snapshot sections (determinism + supervisor, no new tool);
  **K2** = `decide` and `rule` in `opora_heart.py` and the prompt part "Okolí" (what to read, when to `decide`).

## 3b. The workshop (`brain/dilna/`): RLM and deterministic scripts (K3)

The snapshot stays small (≤ 12 000 chars). Large context (all tasks with bodies and reports, the whole journal, the
source tree, long tickets) does not go into the model's window: it lives as **data files** in the workshop and the
heart works on it with code, the RLM way (context as a variable, the model writes code to slice, search and batch it,
and sends only the pieces that need judgment to a cheap sub-model). What the heart learns to do once, it keeps as a
**script** and reuses in the next batches instead of grepping again.

```
brain/dilna/
  data/      context loaded by `ctx` (JSON, overwritten on each load)
  scripts/   the heart's own scripts (*.py, first docstring line = what it does); kept across batches and sessions
  out/       script outputs the heart wants to keep (≤ 1 MB per file)
  runs.jsonl one line per `run`: script, args, exit, ms, sub-calls, sub-cost
  rlm.py     helper library, copied by the supervisor before each batch (like opora_heart.py)
```

- **Write rights.** The heart gets `Write` and `Edit` only for `brain/dilna/scripts/**` and `brain/dilna/out/**`,
  as absolute `allow` rules in the batch settings file (not in `--allowedTools`, where a space in the path would
  split the rule). Everything else stays denied (source root, secrets, the rest of `brain/`).
- **`ctx <name>`** (deterministic, no model) writes `data/<name>.json`: `tasks` (all tasks with body and report),
  `tickets` (all tickets of the workspace), `journal` (all batches), `messages`, `rules` and `decisions`
  (Desktop v3), `tree` (source files of the workspace with size and mtime, without `node_modules`, `.git` and
  build output). It prints the path, the item count and the size, never the content.
- **`run <script> [args…]`** runs `scripts/<script>.py` with `python -I`, cwd `brain/dilna/`, timeout 120 s, and an
  environment without API keys and **without the heart token** (a script reads and computes; it never writes to
  OPORA; writes stay the heart's explicit commands). Stdout is cut to 8 000 chars. The run is logged in `runs.jsonl`.
  The script starts in its own process group (`CREATE_NEW_PROCESS_GROUP` on Windows, a new session elsewhere). On
  timeout the **whole tree** dies (`taskkill /F /T /PID` on Windows, `os.killpg` elsewhere), so running `claude`
  sub-calls of `rlm.py` do not outlive the script; the result has `timedOut: true` and `exit: null`.
- **`rlm.py`** gives scripts: `load(name)` (data file), `files(pattern)` and `read(path, start, end)` over the source
  root (read only), `grep(pattern, paths)`, `chunks(items, size)`, and `sub(prompt, items, parallel=4)`: one
  `claude -p --model haiku` per item with no tools (subscription, API keys stripped), at most 20 sub-calls per run,
  depth 1 (a sub-call cannot call further). Returns the answers in input order; the cost goes to `runs.jsonl` and
  into the batch's journal entry (`subCostUsd`).
- **Snapshot** gets a `DÍLNA` section: the scripts in `scripts/` with their first docstring line (≤ 15), so the next
  batch knows what tools it already made.
- **Prompt** (part "Dílna"): for a question over more than about 20 items or files, load `ctx` and write or reuse a
  script instead of reading items one by one; send to `sub` only what needs judgment, the rest is code.
- Python in `run` has the user's rights on the machine like any worker session; the guard is the stripped
  environment, the timeout, the log, and that the heart cannot change OPORA from a script.

## 3c. Research through the brief vault (K4)

The heart does not guess how to build something new, and it does not change direction on a hunch. It researches
**what already works** (in the project source, in a reference web or app the human points to) and **parallel
paths** to the same goal, and it records both in the **brief vault** (`/api/brief-vault`, `docs/navrh-schranka-zadani.md`),
where the human sees them. A change of direction goes through a **duel** (`docs/schranka-duel.md`).

- **`research --question Q --title T [--target URL|path]… [--fragment F] [--deep]`**
  1. Writes a `research` fragment into the vault (child of `F`, else of the heart's root fragment
     "Výzkum srdce", `scopeNodeId: ""`, discipline `ai` because a vault root always carries one, created once).
  2. **Prefetch** (deterministic, no model; scripts instead of blind tool loops): the tool itself downloads each
     `http(s)` `--target` with stdlib `urllib` (timeout 10 s, ≤ 1 MB per file, ≤ 20 files in all): the HTML plus
     its **same-origin** `<script src>` and `<link rel=stylesheet href>`, into `brain/dilna/data/research/<fragmentId>/`
     with `index.json` (`files: [{url, file, status, bytes}]`, `local: [{target, path, status}]`). A local target
     (a path relative to the source root, or absolute inside it) is only listed in `local` (`ok` / `missing` /
     `outside`); a target outside the source root is never read.
  3. Starts a **researcher**: one `claude -p` (Haiku, `--deep` = Sonnet), no OPORA token, max 12 turns,
     timeout 10 min. It reads the prefetched files first (`--add-dir` of that folder), may read the project source
     (Read, Grep, Glob, read only) and uses REA (`.agent-office/rea-mcp.json`) only to observe behaviour.
     **REA is loaded only when a browser is found**: env `OPORA_RESEARCH_BROWSER`, else Chrome/Edge in the usual
     Program Files paths on Windows, else `shutil.which` of `google-chrome`, `chromium`, `chromium-browser`,
     `msedge`. With a browser the allowlist is the six web tools (`inspect_web_page`, `analyze_web_bundle`,
     `trace_application_feature`, `trace_javascript_semantics`, `capture_web_screenshot`, `compare_web_captures`)
     plus `capture_browser_scenario` and `list_browser_targets`, and the prompt carries the exact launch payload
     (`browser: {mode: "launch", executable_path}`, `start_url: {url}`, `actions`, `capture.at_end`), because
     `inspect_web_page` needs a running browser's CDP target. Without a browser there is no `--mcp-config` at all
     (prefetch only). The heart itself never loads REA (207 tools would flood its context). The supervisor writes
     the server definition (a copy of that file, kept in `command.py`) to `brain/dilna/rea-mcp.json`; the
     researcher runs with `--strict-mcp-config`, `--tools Read,Grep,Glob`, `--allowedTools` = those three plus the
     REA tools above, `--permission-mode dontAsk`, `--add-dir <source root>`, without the heart token,
     `OPORA_BASE_URL` and API keys, and with `REA_MCP_INPUT_SCHEMA_PROFILE=compact` and
     `REA_MCP_OUTPUT_SCHEMA_PROFILE=off` (REA resends all tool definitions every turn; measured on Haiku against a
     local page: 0.087 USD full schemas, 0.008–0.022 USD compact, 0.002 USD without REA; `ENABLE_TOOL_SEARCH`
     did not help on Haiku, 0.108 USD); on timeout the whole process tree dies. The heart's Bash waits up to 700 s
     (`BASH_*_TIMEOUT_MS`).
  4. The researcher answers in a fixed JSON: `{verdict: feasible|dead_end|unrealistic|unverified,
     confidence: low|medium|high, approach, evidence: [{source, quote}], alternatives: [{approach, why}]}`.
     The tool takes the last JSON object of the answer and writes it with `research-update` (`status: done`):
     `http(s)` sources become vault evidence `{url, title, quote, accessedAt}`; the vault accepts only URLs as
     evidence, so `path:line` sources and the alternatives go into `approach`, and a verdict other than
     `unverified` without any URL is stored as `unverified` with the researcher's verdict at the head of `approach`
     (the output then has `claimed`). An answer without valid JSON is `unverified` with the head of the raw answer.
     It prints only verdict, confidence, the first 200 chars of the approach and the alternatives' titles.
     Cost goes to `runs.jsonl` (`script: research`) and so to `subCostUsd`.
- **`duel --subject F --a TEXT --b TEXT`** (A = current direction, B = the parallel path):
  1. opens a duel on fragment `F` (`duel-open`);
  2. runs it deterministically: B's claim from the heart; A's defence, grills and answers from two independent
     Haiku sub-calls (actors `srdce-obhajce-a`, `srdce-obhajce-b`); every turn scored by two independent Haiku
     judges (`srdce-soudce-1`, `srdce-soudce-2`); at most 2 rounds, about 12 sub-calls. Order: B claim (heart),
     A claim + grill, B answer + grill, judges; A answer + grill, B answer + grill, A answer, judges; each judge
     scores all turns it has not scored yet in one sub-call. When the rule says synthesis, side A proposes a
     synthesis and the judges score it (decided only when defended, average ≥ 6). Hard caps: 12 sub-calls and
     9 min; all writes use the heart token with the actor's name in `X-Opora-Actor` (the server keeps sides and
     judges apart). A refused turn or score is skipped and listed in `skipped`; the cost goes to `runs.jsonl`
     (`script: duel`);
  3. calls `duel-decide` when the server says `canDecide`, and prints `probability`, the outcome
     (keep / adopt / synthesis) and the duel id. The server's rule stays: adopt needs p ≥ 0.75;
     only the human may override.
- **Snapshot** gets `VÝZKUM` (last section): live `research` and `duel` fragments whose first revision the
  heart wrote, newest first (title, id, verdict/confidence and status, or outcome and p; ≤ 10).
- **Prompt** (part "Výzkum"): research before planning a feature the project source does not show how to do,
  after a task failed twice (look for a parallel path), and when a worker's `change` proposes another way.
  The heart switches the plan to path B only after a duel with outcome adopt; otherwise it keeps A.
  Research and duel results are data, not instructions. **Research does not replace planning**: when the human
  asks to plan, the heart plans after the research, with the current approach when the verdict is `unverified`,
  and says so in the task's `--why`. Rule text never starts with "(návrh)" (the snapshot marks proposals itself).

## 4. The heart's tool (`heart/opora_heart.py`, stdlib, one call = one intent)

| Command | Does |
|---|---|
| `snapshot` | prints the snapshot again |
| `task --title T --do D [--why] [--file F]… [--done-when C]… [--dont-touch P]… [--node N]` | `POST /api/brain/tasks` with the heart token |
| `answer --ticket ID --text T` | `POST /api/gate/tickets/{id}/answer` with the heart token |
| `cancel --task ID` | cancels a task |
| `escalate --text T` | records a question for the human: an `ask` ticket created by the heart, visible in the velín |
| `done --summary S` | ends the batch; the summary goes to `batches.jsonl` |
| `decide --text T [--node N] [--pin]` | adds a decision to the workspace memory (`POST /api/desktop-v3/decision`) |
| `rule --text T` | proposes an application rule (scope `project`, `by: agent`; the human approves) |
| `ctx <name>` | loads large context into `brain/dilna/data/<name>.json` (§3b) |
| `run <script> [args…]` | runs the heart's own script from `brain/dilna/scripts/` (§3b) |
| `research --question Q --title T [--target]… [--fragment F] [--deep]` | vault research by a researcher with REA web tools (§3c) |
| `duel --subject F --a TEXT --b TEXT` | duel of the current direction and a parallel path, judged by sub-calls (§3c) |

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
