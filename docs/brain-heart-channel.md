# Human channel to the heart (H2b1)

Status: contract. It builds on `docs/brain-heart.md` and `docs/brain-control-api.md`. H2b is split into two steps:
- **H2b1:** the channel to the heart, beside the old assistant. This document.
- **H2b2:** deleting `backend/claude_code/assistant/` and the old panel. It needs the human's approval after H2b1 has
  been used.

Measured basis (eval E, m3–m6): the heart plans precise tasks for 0.01–0.23 USD per session. With those tasks a Sonnet
worker matches Opus quality at 0.53 USD per session. The old assistant's flaws (`backend/brain_opora/README.md`:
generic, slow on the canvas, poor task assignment) are the criteria H2b1 must beat.

## 1. What the human sees

The assistant panel gets a switch at the top: **Srdce** | **Asistent** (the old one).
- The switch is stored once for the application, in the existing `assistant-prefs.ts`.
- The default is **Srdce** for a project whose gate is on, and **Asistent** otherwise.
- With the gate off, Srdce shows one line saying the gate is off, and a button that turns it on through
  `POST /api/brain/gate-setting`.

The Srdce view is one column, in this order from the top:
1. **Waiting for you:** the heart's escalations (open `ask` tickets with `for: "human"`). Each one shows its text, a
   reply field and the button **Odpovědět**. This list is the reason the channel exists, because without an answer
   the heart's plan stays blocked (eval m2).
2. **Queue:** the tasks of the workspace, grouped `ready` / `assigned` / `done` / `failed` / `cancelled`. Each row
   shows the title, the status and who holds the task. The row expands to the task's `do` and `doneWhen`. It is read
   only.
3. **Heart:** the state in one line (sleeping, working, waiting until …, error) and the last 5 batches as summaries
   with their cost.
4. **Composer:** a message to the heart, either an intent, a change or a question. It is sent with
   `POST /api/brain/heart/messages`. While the heart works the composer stays enabled, and a new message waits for
   the next batch.

The view polls every 4 s while it is visible, like the old panel. There is no SSE in H2b1.

## 2. API (backend)

| Route | Who | Does |
|---|---|---|
| `GET /api/brain/heart/escalations?project&workspace` | human only, loopback | open `ask` tickets with `for: "human"`, newest first: `{escalations: [{ticketId, text, createdAt, taskId?}]}` |
| `POST /api/gate/tickets/{id}/answer` (exists) | human | when the ticket is a heart escalation, the answer also **wakes the heart** at once with the input `ODPOVĚĎ ČLOVĚKA na <ticketId>: <text>` |
| `GET /api/brain/heart/status`, `GET /api/brain/tasks`, `POST /api/brain/heart/messages`, `POST /api/brain/gate-setting` (exist) | human | unchanged |

- The wake-up goes through the supervisor's `message()`, so a human answer also skips the hourly cap (#149).
- The heart's batch message shows the answer as a human message.

## 3. Frontend placement

- New feature folder `frontend/layout/heart-channel/` with `components/`, `logic/`, `styles/heart-channel.css` and
  `README.md`.
- `AssistantPanel` composes it through the switch. Neither panel reads the other's state.
- Logic without React goes in `logic/*.ts`, with a test beside it:
  - grouping of the queue;
  - the status line from `status`;
  - formatting of batch cost.
- Network calls go in `logic/heart-api.ts`.

## 4. Done when

- Backend tests:
  - escalations are listed for the human only;
  - an answer to an escalation wakes the heart;
  - an answer to a worker ticket does not.
- `npm test`, `npx tsc --noEmit -p .` and `npm run build` pass.
- **Browser** (isolated OPORA, not 8740): a project with the gate on shows the Srdce view, all of these work, and the
  console has no errors:
  - a message reaches `status.pending`;
  - an escalation created through `POST /api/brain/heart/escalate` with the heart token appears;
  - the answer sent from the UI closes the escalation and wakes the heart.
