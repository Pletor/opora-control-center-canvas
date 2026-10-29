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
- `brain_routes.py` also carries the task queue (`docs/brain-gate.md` §6, H1b): `GET /api/brain/tasks?project&workspace&status?`
  is readable by anyone; `POST /api/brain/tasks {project, workspace, nodeId?, title, body}` and
  `POST /api/brain/tasks/{id}/cancel?project=` accept a human or the heart of the same project (`writer.py`); the
  body may carry `order`. The wall lets a human through, so a human writes tasks in a gate-on project too.
- `writer.py`: human or heart. The heart is recognised only by `request.state.heart_project`, which the `boundary`
  middleware sets after the wall verified a heart token for the request's project; it cannot be spoofed. The ticket
  answer in `gate_routes.py` uses the same marker (`answeredBy = "heart"`).
- `heart_routes.py` (H2a, `docs/brain-heart.md`, loopback-only): `POST /api/brain/heart/messages {project, workspace,
  text}` (human only, gate on, else 409 `gate_off`) queues a wake and answers `{queued: true, pending}`;
  `GET /api/brain/heart/status?project=` returns the session, the last 5 batches, sleeping and `nextAllowedAt`;
  `GET /api/brain/heart/snapshot?project&workspace` returns `{snapshot}`; `POST /api/brain/heart/escalate
  {project, workspace, text}` (heart token only) creates an `ask` ticket for the human.
