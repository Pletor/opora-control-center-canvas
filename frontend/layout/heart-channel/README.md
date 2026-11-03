Heart channel: the human's channel to the heart of OPORA (H2b1, contract `docs/brain-heart-channel.md`).

It is the only content of the assistant panel (the old assistant was deleted in H2b2b). The gate state belongs to the
panel (`assistant-panel/logic/use-gate.ts`); the channel receives only `projectId`, `workspace`, `gateOn`, `gateFailure`
and `onEnableGate`.

One column, top to bottom:

1. **Čeká na vás**: the heart's escalations (open `ask` tickets with `for: "human"` from a heart session), each with
   a reply field and **Odpovědět**. The answer goes to `POST /api/gate/tickets/{id}/answer`; the backend wakes the
   heart with `ODPOVĚĎ ČLOVĚKA na <ticketId>: <text>`.
2. **Tickety**: the workspace's work tickets (`GET /api/brain/tickets`) grouped by status (needs_answer, issued,
   claimed, in_progress, delivered, verified, failed, cancelled, closed), each row with title (first line of `build`),
   status, card and holder; a row expands to the last feedback, `essence` and `doneCriteria`. Read only.
3. **Srdce**: the status line (sleeping, working, waiting until …, error, not running on this server) and the last
   5 batches with summary and cost. While a batch runs (`status.current`, docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md
   §A) the line "Pracuje od HH:MM · probudilo: <vstup>" and the batch's live steps follow: the heart's writes from the
   activity log (`agent=heart`, `since=startedAt`), newest first, each as a sentence (`actionLabel` of the activity
   log), with card names from the canvas graph and a "selhalo" tag for non-2xx. Reads are never logged, so never
   shown. A finished batch row expands (`<details>`) to its steps, loaded once on first open for `at … at + durationMs`.
4. Composer: a message to the heart (`POST /api/brain/heart/messages`). It stays enabled while the heart works.

With the gate off the channel shows one line and **Zapnout bránu** (reported up, the panel calls
`POST /api/brain/gate-setting`). Data is polled every 4 s while the channel is visible (shared poller, stops in a
hidden tab); live steps are fetched in the same poll only while a batch runs. There is no SSE in H2b1. The panel also
passes the canvas graph nodes (`nodes`) so steps can name their cards.

Pieces (`components/`):

- `HeartChannel`: parent. Holds the loaded data (`useHeartChannel`) and the message draft, composes the pieces.
- `GateOff`: the gate-off line and button.
- `Escalations`: the list and `EscalationItem` (reply text lives only until it is sent).
- `Tickets`: groups and expandable rows (`<details>`).
- `HeartState`: status line with a dot, the `live` slot and the batch list; a batch row expands to its steps and
  reports the first open up (`onOpenBatch`).
- `HeartLive`: the running batch: since when, what woke it, its live steps.
- `StepList`: the heart's steps as sentences (shared by `HeartLive` and an expanded batch).
- `HeartComposer`: message field, `Enter` sends, `Shift+Enter` breaks the line.

Logic (`logic/`), pure functions with a test beside:

- `tickets.ts`: grouping of tickets in reading order, title, holder label, last feedback.
- `heart-status.ts`: status line and tone from `GET /api/brain/heart/status`, local `HH:MM` clock.
- `batch-cost.ts`: cost of a batch in Czech format (`0,12 USD`, `< 0,01 USD`, `—`) and batch rows, newest first,
  each with the step range of the batch.
- `heart-live.ts`: wake reason from batch `inputs`, the "Pracuje od" line, step range and activity-log query, step
  sentences and rows (reads skipped, newest first, card names, failure).

Network and React binding (no test): `heart-api.ts` (all calls and response types), `use-heart-channel.ts`
(polling, live steps, answer, send), `use-batch-steps.ts` (steps of a finished batch, loaded once on expand). Style: `styles/heart-channel.css` (block `heart-channel`).
