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
- `GET /api/pletor/voices` → `{available: [{id, label, gender: male | female}], default}` (P3b): jen skutečně stažené
  hlasy Piperu, výchozí Jirka (jinak první stažený, jinak `null`). Zároveň na pozadí načte výchozí hlas do paměti.
- `POST /api/pletor/tts {text, voice?}` → `audio/wav` (P3b, `backend/pletor/tts.py`). Text 1–600 znaků, prázdný nebo
  cizí klíč 422; nestažený či neznámý hlas 404 „Hlas není stažen.“ (`voice_missing`), chybějící `piper-tts` 503.

Instance `Pletor` žije v `app.state.pletor` (`backend/app/factory.py`); testy jí vyměňují `runner`, `find`
a `transport` (Ollama).
