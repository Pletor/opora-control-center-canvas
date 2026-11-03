# Brain control API and MCP (H1c, H1d)

Status: contract. It builds on `docs/brain-gate.md` (gate, tokens, wall, ticket of work) and `docs/brain-heart.md`.

Goal: one strong, typed API through which any agent drives OPORA, and an MCP server on top of it. The MCP server is
a thin layer with no logic of its own. Measured problems it addresses:
- **m1:** an agent in OPORA spent about 100 calls on ceremony before its first code edit. It read references and
  minified JS to find routes, and got 4–8 permission denials per session.
- **m2smoke:** chained shell commands caused 2 denials.

## 1. Principles

1. **One verb = one call.** Every action an agent needs is a gate kind with a JSON schema. Nothing requires reading a
   reference first.
2. **Self-describing.**
   - `GET /api/gate/kinds` lists the kinds available to the caller's role. Each kind comes with its `description`,
     `input` schema, `output` schema, one complete `example` and the error `codes` with their `hint`.
   - The OpenAPI document covers every gate and brain route with request and response models.
3. **Role decides the kinds.**
   - A worker sees worker kinds.
   - The heart sees worker kinds plus heart kinds.
   - A human sees everything (UI and tests).
4. **No shell needed.** The MCP server exposes the same kinds as tools, so an agent with
   `--allowedTools mcp__opora__*` needs no Bash and no permission rules.

## 2. Kinds (H1c)

| Kind | Role | Input | Output |
|---|---|---|---|
| `ticket.request` | worker | `{}` | the ticket for the session (or `null`), in the shape of `ticket.claim` |
| `ticket.claim` | worker | `{ticketId, executionId?}` | `{ticket}` (issued → claimed) |
| `ticket.feedback` | worker | `{ticketId, kind, text}` | `{feedback}`; `kind` = bug / idea / improvement / question (a question → `needs_answer`) |
| `ticket.deliver` | worker | `{ticketId, summary, sha?}` | `{ticket}` (→ delivered) |
| `ticket.release` | worker | `{ticketId, reason}` | `{ticket}`: the claimed ticket goes back to `issued` |
| `ask` | worker | `{question}` | ticket, queued; the answer arrives in the inbox |
| `change` | worker | `{proposal, reason}` | ticket, queued for the heart |
| `state` | worker | `{}` | `{project, intent, rules[], plan[], tickets{<status>: count for all 10 statuses}, myTicket}`: a compact, deterministic view (`myTicket` = the ticket held by the session in claimed..delivered, otherwise null) |
| `inbox` | worker | `{after?, wait?}` | `{tickets, last}`, the same as `GET /api/gate/inbox` |
| `ticket.issue` | heart | the work body + `cardId` | `{ticket}` |
| `ticket.cancel` | heart | `{ticketId}` | `{ticket}` |
| `ticket.answer` | heart | `{ticketId, feedbackId, text}` | `{ticket}` |
| `escalate` | heart | `{text}` | `{ticket}` |

How the kinds are served:
- Every kind goes through `POST /api/gate/requests {kind, body}`.
- **Synchronous kinds** (`ticket.*`, `state`, `inbox`, all heart kinds) answer in the same response and still
  leave a ticket for the audit log.
- `ask` and `change` stay `queued`.
- The `/api/gate/tickets/*/answer` route stays for the UI as a thin wrapper over the same functions; the task queue
  routes `/api/brain/tasks*` were deleted in PR 5c and replaced by `GET /api/brain/tickets`.

**Validation.** Payload checks live in one table per kind: `determinism/kinds.py`. The registry and
`GET /api/gate/kinds` are generated from it, so the documentation cannot drift from the code. Each kind's
`example` is executed in a test.

## 3. MCP server (H1d)

- **Location:** `backend/api/brain_opora/mcp/opora_mcp.py`, stdlib only. It speaks JSON-RPC 2.0 over stdio
  (`initialize`, `tools/list`, `tools/call`), and the protocol version comes from the client's `initialize`.
- **Configuration:** env `OPORA_BASE_URL`, `OPORA_PROJECT`, `OPORA_WORKSPACE` and `OPORA_GATE_TOKEN` (heart) or
  `OPORA_WORKER_NAME` (worker; the server opens its own gate session at the first call and keeps the token in memory).
- **Tools:** `tools/list` = `GET /api/gate/kinds` for the role. Tool names are `opora_<kind with . → _>`, for
  example `opora_state` and `opora_ticket_issue`. The tool's `inputSchema` is the kind's input schema.
- **Calls:** `tools/call` maps to `POST /api/gate/requests`.
  - The result is `content: [{type: "text", text: <json>}]`.
  - A 4xx becomes `isError: true` with `code` and `hint`.
  - `ask` with `wait: true` long-polls the inbox for up to 30 s.
- **Launch:**
  - worker: `claude --mcp-config '{"mcpServers":{"opora":{"command":"python","args":["<abs>/opora_mcp.py"]}}}'
    --allowedTools mcp__opora__*`;
  - `--safe-mode` turns MCP servers off, so a sandboxed agent uses `--strict-mcp-config` with
    `--setting-sources` instead (live smoke 2026-10-29: the tools were missing under `--safe-mode`).
  - heart: the same with its token. The heart's Bash rule and `opora_heart.py` then go away (H2 follow-up, after
    measuring).

## 4. Steps

| Step | Content | Done when |
|---|---|---|
| H1c | `kinds.py` table, `GET /api/gate/kinds`, kinds `state`, `inbox`, heart kinds through the gate, OpenAPI models, executed examples | tests green; an agent can list the kinds and call each one with its example |
| H1d | `opora_mcp.py` + tests with a fake HTTP server; worker launch via MCP in eval arm E as a variant | eval: E-MCP against E on S1–S2 gives 0 permission denials and no fewer done tasks |
