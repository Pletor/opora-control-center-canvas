# api/brain_opora: routes of the OPORA brain

Routers for `backend/brain_opora/`. The logic lives in the brain layers; a router only reads the request, calls the
layer and turns `GateError` into a JSON answer with `code` and `hint`.

- `gate_routes.py`: the gate for worker sessions (`/api/gate/sessions`, `/requests`, `/inbox`, `/tickets/{id}`,
  `/tickets/{id}/answer`). Contract: `docs/brain-gate.md` §4. The gate is loopback-only and never reachable through
  the tunnel (`backend/app/remote_access.py`).

Not here yet (later steps of the contract): the wall in the middleware and `POST /api/brain/gate-setting`.
