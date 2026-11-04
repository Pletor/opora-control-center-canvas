# api/pletor: routy Pletora

Tenký router pro `backend/pletor/` (docs/navrhy/2026-11-04-pletor-jarvis.md, P1). Jen člověk v UI
(`require_human`, jinak 403) a jen z tohoto počítače (`/api/pletor` v `backend/app/remote_access.py`).

- `POST /api/pletor/messages {project, workspace, text, voice?}` → `{reply, actions: [{type, text, ok, detail?}]}`.
  `voice: true` (P3, hlas) přidá do vstupu modelu řádek `service.VOICE`: krátká odpověď ke čtení nahlas.
  Cizí klíč nebo prázdný text 422, neznámý projekt 404 `project_not_found`.
- `GET /api/pletor/state?project&workspace` → `{messages: [{role, text, at}], heart: {running, pending, sleeping,
  error, idleReason, lastSummary}, escalations: [{ticketId, text, createdAt}], brain: {brain: claude | ollama, model,
  available: [modely Ollamy]}}`. `available` jde z `/api/tags` při každém čtení; neběžící Ollama = `[]`.
- `POST /api/pletor/brain {brain: claude | ollama, model?}` → `{ok, reply, brain}` (P2). Neběžící Ollama nebo
  neznámý model = `ok: false` s důvodem v `reply`, mozek zůstane. V UI se přepíná větou v chatu (`backend/pletor/brains.py`).

Instance `Pletor` žije v `app.state.pletor` (`backend/app/factory.py`); testy jí vyměňují `runner`, `find`
a `transport` (Ollama).
