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
- `GET /api/pletor/voices?warm=<id>` → `{voices: [{id, label, gender, engine: xtts | elevenlabs | edge | piper,
  available, reason, quota}]}` (P3b, `backend/pletor/speech.py`): všechny známé hlasy v pořadí XTTS → ElevenLabs → Edge → Piper, nedostupné
  s důvodem (nestažený model, málo VRAM, chybějící balíček, tarif ElevenLabs); `quota` `{tier, character_count, character_limit}` jen u ElevenLabs (cache 60 s). Na pozadí načte dopředu `warm` (jinak nejlepší dostupný).
- `POST /api/pletor/tts {text, voice?}` (P3b): engine je v id hlasu. Piper `audio/wav`, Edge a ElevenLabs `audio/mpeg`
  (streamovaně, **cloud Microsoftu: text odchází z počítače**), XTTS `audio/pcm;rate=24000` (PCM 16 bit LE po
  kouscích). Odpověď přijde až s prvním kouskem zvuku. Text 1–600 znaků, prázdný nebo cizí klíč 422; nestažený či
  neznámý hlas 404 „Hlas není stažen.“ (`voice_missing`, `hint` = příkaz ke stažení), nedostupný engine 503.

Instance `Pletor` žije v `app.state.pletor` (`backend/app/factory.py`); testy jí vyměňují `runner`, `find`
a `transport` (Ollama).
