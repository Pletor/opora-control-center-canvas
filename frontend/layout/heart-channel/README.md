Heart channel: the human's channel to the heart of OPORA (H2b1, contract `docs/brain-heart-channel.md`).

It is the only content of the assistant panel (the old assistant was deleted in H2b2b). The gate state belongs to the
panel (`assistant-panel/logic/use-gate.ts`); the channel receives only `projectId`, `workspace`, `gateOn`, `gateFailure`
and `onEnableGate`.

One column, top to bottom:

1. **Čeká na vás**: the heart's escalations (open `ask` tickets with `for: "human"` from a heart session), each with
   a reply field and **Odpovědět**. The answer goes to `POST /api/gate/tickets/{id}/answer`; the backend wakes the
   heart with `ODPOVĚĎ ČLOVĚKA na <ticketId>: <text>`.
2. **Fronta**: the workspace's tasks grouped ready / assigned / done / failed / cancelled, each row with title,
   status and holder; a row expands to `do` and `doneWhen`. Read only.
3. **Srdce**: the status line (sleeping, working, waiting until …, error, not running on this server) and the last
   5 batches with summary and cost.
4. Composer: a message to the heart (`POST /api/brain/heart/messages`). It stays enabled while the heart works.

With the gate off the channel shows one line and **Zapnout bránu** (reported up, the panel calls
`POST /api/brain/gate-setting`). Data is polled every 4 s while the channel is visible (shared poller, stops in a
hidden tab); there is no SSE in H2b1.

Pieces (`components/`):

- `HeartChannel`: parent. Holds the loaded data (`useHeartChannel`) and the message draft, composes the pieces.
- `GateOff`: the gate-off line and button.
- `Escalations`: the list and `EscalationItem` (reply text lives only until it is sent).
- `Queue`: groups and expandable rows (`<details>`).
- `HeartState`: status line with a dot and the batch list.
- `HeartComposer`: message field, `Enter` sends, `Shift+Enter` breaks the line.

Logic (`logic/`), pure functions with a test beside:

- `queue.ts`: grouping of the queue in contract order, holder label.
- `heart-status.ts`: status line and tone from `GET /api/brain/heart/status`, local `HH:MM` clock.
- `batch-cost.ts`: cost of a batch in Czech format (`0,12 USD`, `< 0,01 USD`, `—`) and batch rows, newest first.

Network and React binding (no test): `heart-api.ts` (all calls and response types), `use-heart-channel.ts`
(polling, answer, send). Style: `styles/heart-channel.css` (block `heart-channel`).
