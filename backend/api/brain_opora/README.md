# api/brain_opora: routes of the OPORA brain

Routers for `backend/brain_opora/`. The logic lives in the brain layers; a router only reads the request, calls the
layer and turns `GateError` into a JSON answer with `code` and `hint`.

- `gate_routes.py`: the gate for worker sessions and the heart (`/api/gate/sessions`, `/kinds`, `/requests`,
  `/inbox`, `/tickets/{id}`, `/tickets/{id}/answer`). `/kinds` lists the kinds of the caller's role, `/requests`
  serves every kind of `backend/brain_opora/determinism/kinds.py`. Contract: `docs/brain-gate.md` §4,
  `docs/brain-control-api.md` §1–§2.
- `models.py`: pydantic models for the OpenAPI document of the gate, brain and heart routes (documentation only; the
  routes read the body themselves so that every refusal keeps `code` and `hint`). The gate is loopback-only and never reachable through
  the tunnel (`backend/app/remote_access.py`).
- `brain_routes.py`: the gate switch. `GET /api/brain/gate-setting?project=` is readable by anyone,
  `POST /api/brain/gate-setting {project, enabled}` is human only (`require_human`, even with full agent autonomy).
  Contract: `docs/brain-gate.md` §1. The wall itself lives in `backend/brain_opora/determinism/wall.py`.
  `GET /api/brain/intake-setting?project=` (anyone) and `POST /api/brain/intake-setting {project, jev, jevPerDay?}`
  (human only) hold the JEV permission and daily cap of the intake gate (`determinism/intake_setting.py`,
  `docs/navrhy/2026-10-30-vstupni-brana.md` §7).
- `brain_routes.py` also carries the task queue (`docs/brain-gate.md` §6, H1b): `GET /api/brain/tasks?project&workspace&status?`
  is readable by anyone; `POST /api/brain/tasks {project, workspace, nodeId?, title, body}` and
  `POST /api/brain/tasks/{id}/cancel?project=` accept a human or the heart of the same project (`writer.py`); the
  body may carry `order`. The wall lets a human through, so a human writes tasks in a gate-on project too.
- `writer.py`: human or heart. The heart is recognised only by `request.state.heart_project`, which the `boundary`
  middleware sets after the wall verified a heart token for the request's project; it cannot be spoofed. The ticket
  answer in `gate_routes.py` uses the same marker (`answeredBy = "heart"`).
- `heart_routes.py` (H2a, `docs/brain-heart.md`, loopback-only): `POST /api/brain/heart/messages {project, workspace,
  text}` (human, or a worker gate token of the same project relaying intent with `via` = session name,
  `docs/brain-heart-orchestrator.md` §8; gate on, else 409 `gate_off`) queues a wake and answers `{queued: true, pending}`;
  `GET /api/brain/heart/status?project=` returns the session, the last 5 batches, sleeping and `nextAllowedAt`;
  `GET /api/brain/heart/snapshot?project&workspace` returns `{snapshot}`; `POST /api/brain/heart/escalate
  {project, workspace, text}` (heart token only) creates an `ask` ticket for the human; `POST /api/brain/heart/intake
  {project, workspace, entry, verdict, reason?, requirement?, title?, openCondition?}` (heart token of that workspace
  only, else 401 / 403) confirms or corrects an intake verdict (`intake.confirm`, layer `heart`; unknown entry 404
  `intake_entry_not_found`) and links the entry to a requirement (`new` or `rq_…`, `determinism/requirements.py`);
  `POST /api/brain/heart/milestone {project, workspace, area, title, criteria: [{text, cards}]}` (heart token only,
  201) proposes a milestone (`proposed`, `determinism/milestones.py`; unknown area 404 `area_not_found`, card
  404 `card_not_found`).
- Human channel to the heart (H2b1, `docs/brain-heart-channel.md` §2): `GET /api/brain/heart/escalations?project&workspace`
  (human only, loopback) lists the heart's open questions for the human (`ask` tickets with `for: "human"` from a
  heart session), newest first: `{escalations: [{ticketId, text, createdAt, taskId?}]}`. When a human answers such a
  ticket through `POST /api/gate/tickets/{id}/answer`, `gate_routes.py` wakes the heart at once through
  `supervisor.message()` with `ODPOVĚĎ ČLOVĚKA na <ticketId>: <text>` (skips the hourly cap, gate must be on). An
  answer to a worker ticket, or an answer given by the heart, wakes nothing. `create_gate_router(service, supervisor)`
  gets the same supervisor as the heart router (`backend/app/factory.py`).
- `jev_routes.py` (H2b2a, `docs/brain-heart-channel.md` §5, loopback-only): settings of the decision model JEV.
  `GET /api/brain/jev` → `{configured, provider, keys}` (booleans only, the key never comes back);
  `POST /api/brain/jev/key {key: text | null, provider?}` (human only, `require_human` even with full autonomy);
  `GET /api/brain/jev/gate-check?project=` and `POST /api/brain/jev/gate-check {project, provider, allowed}` (write
  human only): consent to the external gate check of the brief vault (`docs/schranka-neurony.md` §7).

## MCP server (H1d)

`mcp/opora_mcp.py` (stdlib only, contract `docs/brain-control-api.md` §3) exposes the gate kinds as MCP tools over
stdio: `tools/list` = `GET /api/gate/kinds` for the role, tool `opora_<kind with . → _>` (`opora_next`,
`opora_task_create`), `tools/call` = `POST /api/gate/requests`. A refusal comes back as `isError: true` with
`code`, `hint` and `status`; `opora_ask` with `wait: true` long-polls the inbox up to 30 s for its answer. Env:
`OPORA_BASE_URL` (default `http://127.0.0.1:8740`), `OPORA_PROJECT`, `OPORA_WORKSPACE`, plus `OPORA_WORKER_NAME`
(worker: the server opens its gate session at the first call and keeps the token in memory only) or
`OPORA_GATE_TOKEN` / `OPORA_HEART_TOKEN` (heart). Only JSON-RPC goes to stdout, logs go to stderr.

- worker: `claude --mcp-config '{"mcpServers":{"opora":{"command":"python","args":["<abs>/opora_mcp.py"]}}}'
  --allowedTools mcp__opora__*` with `OPORA_PROJECT`, `OPORA_WORKSPACE`, `OPORA_WORKER_NAME` in the environment;
- heart: the same with `OPORA_GATE_TOKEN` (or `OPORA_HEART_TOKEN`) instead of `OPORA_WORKER_NAME`.

- `intake_routes.py` (intake gate, `docs/navrhy/2026-10-30-vstupni-brana.md` §6 and
  `docs/navrhy/2026-10-30-metriky-a-spoustece.md` §5): `GET /api/intake?project&workspace` is readable by anyone and
  returns the "Požadavky a plán" view `{areas: [{id, name, milestone, proposed, requirements, deferred}], unassigned,
  entries (latest 50), pending, duplicates}`; areas are the canvas nodes with `kind: "area"`, `milestone` is the active
  one with computed criteria (`done` per card and criterion) and `progress`, `requirements` are open, `deferred`
  carry `openCondition`, `unassigned` = open / deferred requirements without a known area. Entries have no public
  write, the server records them itself. `POST /api/intake/milestone {project, workspace, milestoneId,
  action: activate|reject}` is human only (`require_human`, 403 for agents and the heart): activation supersedes the
  area's active milestone; not a proposal 409 `milestone_not_proposed`. Logic: `determinism/intake.py`, `milestones.py`.

Tests: `mcp/test_opora_mcp.py` runs the server as a subprocess against a fake gate.
