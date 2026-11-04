# api/pletor: routy Pletora

Tenký router pro `backend/pletor/` (docs/navrhy/2026-11-04-pletor-jarvis.md, P1). Jen člověk v UI
(`require_human`, jinak 403) a jen z tohoto počítače (`/api/pletor` v `backend/app/remote_access.py`).

- `POST /api/pletor/messages {project, workspace, text}` → `{reply, actions: [{type, text, ok, detail?}]}`.
  Cizí klíč nebo prázdný text 422, neznámý projekt 404 `project_not_found`.
- `GET /api/pletor/state?project&workspace` → `{messages: [{role, text, at}], heart: {running, pending, sleeping,
  error, idleReason, lastSummary}, escalations: [{ticketId, text, createdAt}]}`.

Instance `Pletor` žije v `app.state.pletor` (`backend/app/factory.py`); testy jí vyměňují `runner` a `find`.
