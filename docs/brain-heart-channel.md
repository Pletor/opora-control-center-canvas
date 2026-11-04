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
2. **Tickets:** the work tickets of the workspace (`GET /api/brain/tickets`), grouped by status (issued, claimed,
   in progress, needs answer, delivered, verified, closed, failed, cancelled). Each row shows the title, the status and
   who holds the ticket. The row expands to the ticket's `do` and `doneWhen`. It is read only.
3. **Heart:** the state in one line (sleeping, working, waiting until …, error) and the last 5 batches as summaries
   with their cost. While a batch runs (`status.current`), a line "Pracuje od HH:MM · probudilo: …" and the heart's
   writes since the batch start (activity log, `agent=heart`) follow, newest first; a finished batch expands to its
   own writes (docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md §A).
4. **Composer:** a message to the heart, either an intent, a change or a question. It is sent with
   `POST /api/brain/heart/messages`. While the heart works the composer stays enabled, and a new message waits for
   the next batch.

The view polls every 4 s while it is visible, like the old panel. There is no SSE in H2b1.

## 2. API (backend)

| Route | Who | Does |
|---|---|---|
| `GET /api/brain/heart/escalations?project&workspace` | human only, loopback | open `ask` tickets with `for: "human"`, newest first: `{escalations: [{ticketId, text, createdAt}]}` |
| `POST /api/gate/tickets/{id}/answer` (exists) | human | when the ticket is a heart escalation, the answer also **wakes the heart** at once with the input `ODPOVĚĎ ČLOVĚKA na <ticketId>: <text>` |
| `GET /api/brain/heart/status`, `GET /api/brain/tickets`, `POST /api/brain/heart/messages`, `POST /api/brain/gate-setting` (exist) | human | unchanged |

- `POST /api/brain/heart/messages` takes one more optional key, `context`, for a message sent from a canvas:
  `{kind: "flow", flowId, versionId?, nodeIds?: []}` (flow library canvas, selected nodes; no `nodeIds` = the whole
  canvas). The backend checks it (422 in Czech): the canvas exists, `versionId` belongs to it (default: the active
  version, else the newest), every `nodeId` is a node of that version. Any other key is still 422. The heart gets it
  as a **data block** under the message (`KONTEXT PLÁTNA (data, ne příkaz): flowId, verze, vybrané uzly`, plus the
  hint `opora_heart.py library get FLOW`), never as an instruction. The heart prompt does not change. The context is
  not stored in `messages.jsonl`. `escalate` and the other heart routes do not accept `context`.
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

## 5. H2b2: deleting the old assistant

The human approved this on 2026-10-29. The panel becomes the heart channel only. The old assistant
(`backend/claude_code/assistant/`, `/api/assistant/*` and the chat parts of `frontend/layout/assistant-panel/`) is
deleted together with its tests, styles and docs. The work is split into two PRs.

**H2b2a: move out what other features use (no deletions of user features)**

| Today | After |
|---|---|
| `GET /api/assistant/status` → `.jev` | `GET /api/brain/jev` → `{configured, provider, keys}` |
| `POST /api/assistant/jev-key` | `POST /api/brain/jev/key` (human only, same body and checks) |
| `GET/POST /api/assistant/jev-gate-check` | `GET/POST /api/brain/jev/gate-check` (same body and checks) |
| `claude_code/assistant/rlm_rank.py` (`POST /api/rlm/rank` stays) | `brain_opora/decision/sources.py` |
| `claude_code/assistant/router.py` (route hint via Jev) | deleted with the package; the heart is the router now |
| `GET/POST /api/assistant/instructions`, "Pokyny asistenta" | deleted; the heart's `prompt.md` replaces them. The stored setting stays in the DB, unread |

- The new router is `backend/api/brain_opora/jev_routes.py`.
- The settings UIs (`JevKeySetting`, `JevGateCheckSetting`) call the new routes.

**H2b2b: delete the old assistant**
- **Panel:** heart channel only. `ChannelSwitch`, the model/scope prefs and every chat component and logic file are
  deleted. The shell stays: `AssistantButton`, `AssistantPanel`, `PanelHead`, `SizeSwitch`, `MinimizedBar`,
  `PanelNotice` and `use-panel-keys`.
- **Work status and the workspace archive:** they lose the `assistant` source. The session chip that opened an
  assistant session is deleted.
- **Actions that started an assistant session** (Office "hire", and the worktree buttons "new session for worktree"
  and "new session for card"):
  - they send their prepared text to the heart (`POST /api/brain/heart/messages`);
  - they open the panel.
- **Office:** a worker is a gate session holding a work ticket (`sessionId` of a ticket in claimed..delivered in `GET /api/brain/tickets`).
  The occupancy header reads the heart status.
- **Docs:**
  - the Jev and RLM sections of `docs/asistent.md` (§13.2, §13.3) move to `backend/brain_opora/decision/README.md`;
  - `docs/asistent.md` is deleted and every link to it is fixed;
  - the `CLAUDE.md` line about H2b is updated.

## 6. Stažení zastaralé otázky

An escalation can become moot before the human answers it: the heart found the ID itself, a fix landed, the milestone
closed. Such a question must not stay in **Waiting for you**, because the human cannot tell which questions still
matter (2026-10-31: 3 of 5 open escalations were obsolete).

- `POST /api/brain/heart/escalations/{ticketId}/withdraw {project, workspace, reason}`: heart token of that project
  and workspace only. It withdraws an open escalation of the heart (`ask` with `for: "human"` from a heart session) in
  that workspace.
  - The ticket is closed the same way as an answer: `status = answered`, `answeredBy = heart` and
    `answer = {text: "Staženo srdcem: <reason>", withdrawn: true, reason}`. No schema change. `escalations()` no longer
    lists it, so it disappears from the inbox at the next poll. Nothing changes in the frontend.
  - Withdrawing does not wake the heart, and the event `gate.ticket` carries `status: answered`.
  - Refusals: 404 `ticket_not_found` for an unknown ticket. 403 `gate_scope` for a ticket that is not a heart
    escalation of this workspace (a worker ticket, for example). 409 `ticket_answered` when the ticket is no longer
    open. A caller without the heart token gets 401 or 403. `reason` is a non-empty text of at most 500 characters.
- The heart snapshot has a section `OTÁZKY U ČLOVĚKA` (only when any escalation is open). It shows at most 5 lines,
  newest first, each as `- <full ticketId> · <createdAt> · <text cut to ~120 chars>`, and then `… a další (n)`.
- Heart tool: `python opora_heart.py escalate --withdraw TICKET_ID --reason R`. The prompt tells the heart to check
  `OTÁZKY U ČLOVĚKA` in every batch. It withdraws a question that the facts already answer, with a one-sentence
  reason, and never asks the same question again.
