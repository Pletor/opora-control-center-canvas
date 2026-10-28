# api/brain_opora: routes of the OPORA brain

Routers for `backend/brain_opora/`. The logic lives in the brain layers; a router only reads the request, calls the
layer and turns `GateError` into a JSON answer with `code` and `hint`.

- `gate_routes.py`: the gate for worker sessions (`/api/gate/sessions`, `/requests`, `/inbox`, `/tickets/{id}`,
  `/tickets/{id}/answer`). Contract: `docs/brain-gate.md` §4. The gate is loopback-only and never reachable through
  the tunnel (`backend/app/remote_access.py`).
- `brain_routes.py`: the gate switch. `GET /api/brain/gate-setting?project=` is readable by anyone,
  `POST /api/brain/gate-setting {project, enabled}` is human only (`require_human`, even with full agent autonomy).
  Contract: `docs/brain-gate.md` §1. The wall itself lives in `backend/brain_opora/determinism/wall.py`.
- `brain_routes.py` also carries the task queue (`docs/brain-gate.md` §6, H1b): `GET /api/brain/tasks?project&workspace&status?`
  is readable by anyone; `POST /api/brain/tasks {project, workspace, nodeId?, title, body}` and
  `POST /api/brain/tasks/{id}/cancel?project=` are human only (`require_human`). The heart token is not accepted
  here yet (H2 adds its own check). The wall lets a human through, so a human writes tasks in a gate-on project too.
