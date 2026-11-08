# heart: layer 3 of the brain

## Research map (Rešerše)

`opora_research_map.py` is copied next to the standalone command. `command.write_config` appends runtime
guidance to the active heart skill, so existing custom Brain skill versions also learn these commands:

```text
python opora_heart.py research-map ls [--archived] [--workspace W]
python opora_heart.py research-map show ID [--entity card|edge] [--revision N] [--workspace W]
python opora_heart.py research-map save --file dilna/out/map.json [--workspace W]
python opora_heart.py research-map import --file dilna/out/research/FRAGMENT.json [--workspace W]
python opora_heart.py research-map attach --file dilna/out/login.png [--workspace W]
python opora_heart.py research --question Q --title T --topic Login --topic Logic --node NODE --question-id QUESTION --ticket TICKET --session SESSION --attachment FILE
```

All context flags on `research` are repeatable. Existing workspace resolution is preserved: in `main`, use the
last active workspace. The server authenticates the heart and checks scope; JSON files cannot override it.
Headers and semantic edges are returned by `ls`; `show` includes unabridged content, sources and revision history.
Use `show EDGE --entity edge --revision N` to inspect how a progression's reason and knowledge gap changed.
`research` stores every desk fact, including failed verification and multiple findings sharing one URL. It retains
the full digest, options and original fact objects. Citation verification is not proof that an inferred claim is true.
Schránka keeps its existing short summary; this no longer limits what the research map retains.

Before network persistence, the complete result and immutable `researchBatch` are written to the research output
file. `research-map import` replays that exact batch with its original key; repeated imports cannot create duplicate
facts, and a foreign scope is refused. Paid research cost is recorded even if subsequent persistence fails.
The output includes `researchIds`: use these in `pletor-answer --ref CARD` and ticket-answer text.

`save` expects exactly `{"key":"unique-request-key","operations":[...]}`. Every operation is full replacement of
its entity, with `expectedRevision:0` for creation or the current revision from a fresh read for an update.
Use a new key for changed operations; reuse the same key only to retry unchanged payloads. Example:

```json
{
  "key": "login-visual-1",
  "operations": [{
    "op": "card", "id": "rc_login_visual", "expectedRevision": 0,
    "kind": "visual", "title": "Login form observation", "summary": "Form layout and visible error state",
    "topicPath": ["Login", "UX/UI"], "content": "Full observed behavior and analysis belong here.",
    "status": "open", "verification": {"status": "observed", "method": "REA browser observation", "at": "2026-11-08T12:00:00Z"},
    "sources": [{"ref": "https://example.com/login", "platform": "rea", "quote": "Exact observed text",
      "title": "Login page", "accessedAt": "2026-11-08T12:00:00Z"}],
    "refs": {"nodeIds": ["login_node"], "questionIds": [], "ticketIds": [], "sessionIds": [],
      "fragmentIds": [], "attachmentIds": ["research_REPLACE_WITH_UPLOADED_ID"]}
  }]
}
```

Use actual observations and source metadata, not this illustrative citation. `attach` uploads raster images to
the existing drawing store via `POST /api/drawing-file`; returned `attachmentId` goes into `refs.attachmentIds`.
`GET /api/drawing-files` reads that asset. Uploading does not place an element in a drawing scene; `refs.nodeIds`
may reference the relevant existing drawing layer/node. PNG/JPEG/WebP/GIF up to 10 MB use content-derived IDs.

Connect existing cards with an edge operation such as:

```json
{"op":"edge","id":"re_ux_logic","expectedRevision":0,"fromId":"rc_login_visual","toId":"rc_login_logic",
 "relation":"continues_to","reason":"Screen interaction does not determine identity validation or session lifetime.",
 "resolved":"Form layout and visible states are described.","missing":"Verify authentication choices and post-login behavior.",
 "evidenceIds":["rc_login_visual"]}
```

Allowed relations: `supports`, `contradicts`, `elaborates`, `option_for`, `supersedes`, `resolves`, `continues_to`.
All require a reason; progression also requires resolved/missing context. All endpoints/evidence IDs must exist
in this scope (they can be created in the same atomic batch). Archive without erasing history using
`{"op":"archive","entity":"card","id":"rc_login_visual","expectedRevision":1,"archived":true}`.

Research does not grant planning or approval authority. After an approved route, create tasks through the existing
`plan`/`task` path and cite research IDs in the task specification. After task creation, update the related cards'
`refs.nodeIds` with the actual returned task IDs. Save cards, edges, ticket/session/question references **before**
replying through question/ticket APIs; only report IDs whose persistence was confirmed. Return an office answer through
`ticket-answer --ticket TICKET --feedback FEEDBACK --text "Instructions, research CARD…"`. Existing plan gates remain.

This is the third layer of the brain, the resident model of a project. It is Claude Code under the subscription, with
Haiku as the main model and Opus as the advisor. While OPORA runs on localhost it sleeps, and no process runs. A batch
of events or a human message wakes it up. It turns intent into tasks for workers and answers their tickets. It never
writes application code. Contract: `docs/brain-heart.md`.

Modules (H2a):
- Waking and scheduling are not here. What wakes the heart (event outbox, human messages, git watcher, card,
  milestone, idle and brief triggers), the caps (one batch per project, 6 automatic per hour, a human message skips
  the cap, 15 min sleep after a rate limit) and `GET /api/brain/heart/status` live in the flow catalog
  `backend/flow/catalogs/heart/` (`state.py`, `wakes.py`, `git_watch.py`, `inputs.py`, see its README). The flow
  engine runs every batch as the workflow „Srdce v1“; this folder keeps the executor the batch node calls.
  It runs only when `OPORA_HEART` is not `off` and `OPORA_CANVAS_HOST` is loopback (`tools/opora.py` sets it).
  Tests set `OPORA_HEART=off` in `backend/conftest.py`.
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
- `opora_heart.py`: the heart's only tool, stdlib (`snapshot`, `task` = work only as a ticket via `ticket.issue`
  with `cardId` (no task queue), `cancel` = `ticket.cancel`, `answer`, `ticket-issue`, `ticket-answer`, `cancel`, `escalate`, `intake`, `decide`, `rule`, `done`,
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
  `dilna/rea-mcp.json` with compact schemas, with `OPORA_RESEARCH_CHROME=1` the human's Chrome read only on the
  domain allowlist of `research_browser.py` behind its PreToolUse hook, result via `research-update`) and `duel` (deterministic, Haiku sub-calls as actors
  `srdce-obhajce-a|b` and judges `srdce-soudce-1|2`, `duel-decide` by the server rule). Both log to `runs.jsonl`.
  `intent` (`opora_intent.py` beside the tool, page intent of canvas 2, `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md`
  §4): `show PAGE` (active and candidate version compact: nodes with type and params, then edges), `propose PAGE --file F
  [--dry-run]` (creates the `page_intent` workflow when missing, saves a draft and proposes it as candidate; `--dry-run`
  only `POST /api/flow/graph-check`), `diff PAGE` (candidate against active). Only a human approves.
  `library` (`opora_library.py` beside the tool, global flow library, `docs/navrhy/2026-11-04-knihovna-platna-toku.md`
  §5): `show`, `get FLOW`, `save` (graph-check, then draft with `learnedFrom` and activation in the AGENT part) and
  `propose FLOW` (draft with a note to a HUMAN flow; the human accepts or rejects it on the canvas). `nodes add|set|connect FLOW` (`opora_library_nodes.py`, process canvas
  `docs/navrhy/2026-11-04-platno-procesu.md` §1b) draws into a draft node by node: positions are automatic (lane
  order FE, BE, DB, Infra, AI, other, mirroring the frontend `flow-lanes`), the graph is checked before every save
  (an error is returned and the draft stays), each change is a new draft from the newest draft.
  A message from a canvas carries `context` that `batch.py` renders as the data block `KONTEXT PLÁTNA`.
  `research --requirement rq_…` is interrogation research: the per-requirement cap is checked before the desk runs and
  the cost is added to the requirement's brief (`docs/navrhy/2026-10-30-vyslech-srdce.md` §8).
- The system prompt and mode procedures are Brain skills (`backend/brain/`, seed `backend/brain/seed/opora-heart/`).
  `command.heart_skills` reads the active versions of `opora:brain:skill:heart` (role, task shape with a full example,
  an implementation card has 2–8 steps with `kind` and `files`, application-wide rules, when to ask the advisor) and
  `opora:brain:skill:vyslech` and `opora:brain:skill:proces-na-platne`; there is no file fallback. `write_config` writes the prompt to `brain/heart-prompt.md`
  (`--system-prompt-file`) and procedures to `brain/skills/NAME.md`, read only on demand via
  `opora_heart.py skill NAME` (`vyslech` when a batch carries `VÝSLECH`, `proces-na-platne` when a message carries `KONTEXT PLÁTNA`). The batch entry carries `brainPins`
  (`{heart, vyslech, proces-na-platne}` → `opora:brain:skill:<name>@<sha12>`), so every batch shows which heart version ran.

The heart token comes from `tokens.issue_heart` once per project and workspace; it lives only in memory and in the
environment of the process. Routes are in `backend/api/brain_opora/heart_routes.py`.

The human channel (the assistant panel talks to the heart) is in the frontend (`frontend/layout/heart-channel/`, contract
`docs/brain-heart-channel.md`); the old `claude_code/assistant/` was deleted in H2b2b.

Rule: the heart writes to OPORA only through `opora_heart.py`, with its role token.
