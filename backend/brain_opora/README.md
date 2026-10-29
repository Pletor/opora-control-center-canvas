# brain_opora: the brain of OPORA

`brain_opora` is OPORA's brain: one resident model per project, and the gate it sits behind. It works for all environments
(project, editor, canvas). Worker sessions, for example from agent-office, enter only through the gate. The canvas
has a single writer, the heart. The contract is in `docs/navrhy/2026-10-28-srdce-opory.md`.

## Three layers, three folders

An event flows downwards and stops at the first layer that can handle it:

| Layer | Folder | What it does | Never |
|---|---|---|---|
| 1. Determinism | `determinism/` | Answers at once and for free: the gate (sessions, the table of request kinds `kinds.py`, inbox), role tokens and the wall, the task queue, the project snapshot, the event feed, tool classification. | calls a model |
| 2. Decision model | `decision/` | Asks JEV (TypeSafe) for typed answers (`choice` / `score` / `noul`): should an event wake the heart, a human, or nobody; which card a commit belongs to; which sources to use. | writes text |
| 3. Heart | `heart/` | Claude Code under the subscription, Haiku with an Opus advisor. It sleeps on localhost and wakes for a batch of events or a human message. It writes the canvas, plans, tasks and answers. | writes application code, approves a change of intent |

Imports only go downwards. `heart` may use `decision` and `determinism`, and `decision` may use `determinism`.
Lower layers never import higher ones, which `test_layer_boundaries.py` enforces. Routers live in `backend/api/brain_opora/`.

## Where the brain keeps its data

Every OPORA project, which is a downloaded repository, has its own folder on the server: `<data>/projects/<id>/`. The
important things about the project live there, and so do the brain's:

- `project.sqlite`: the gate tables (`gate_sessions`, `gate_tickets`, `heart_tasks`) next to the plan, journal and
  decisions;
- `project.json`: the switch `settings.brain`;
- `brain/`: the heart's own folder, which is also its working directory. It holds the current session id and rotation
  (`session.json`), the heart's journal of batches (`batches.jsonl`), the last snapshot it was given
  (`snapshot.txt`), the summary of the last `done` (`last_done.json`) and the batch settings written before each run.

Nothing about a project's brain is stored outside its folder, so the folder can be moved or backed up as a whole.

## Step by step

The brain is built in small steps. A step goes on only after the previous one is measured as successful:

| Step | Folder | Done when |
|---|---|---|
| H0 | skeleton | the folders, READMEs and the layer boundary test are in place |
| H1 | `determinism/` | a worker finishes a session only through the gate, without the heart, using hand-written tasks |
| H2 | `heart/` | a failing check becomes a task in the queue within 2 min |
| H2b | `heart/` | the assistant panel talks to the heart, and the old `claude_code/assistant/` is deleted |
| H3 | `decision/` | the heart wakes only for events that need judgement, and advisor calls are measured |
| H4 | eval | quality and cost compared with a bare terminal on the multi-session eval |

## What the old assistant got wrong

These are the acceptance criteria for H2b, as reported by the user on 2026-10-28:
- **Too generic.** The heart gets a project snapshot and a fixed role, not a general chat.
- **Slow on the canvas.** Each intent is one call to `opora_heart.py`, not a sequence of API steps.
- **Poor task hand-off.** A task has a fixed shape: why, do, files, done-when checks, do-not-touch, commit trailer.
- **Too few tokens for descriptions.** The snapshot is kept small, so a task description has room.
- **No results.** Every task ends with checks on a sha, and the heart is measured on the eval before it grows.
