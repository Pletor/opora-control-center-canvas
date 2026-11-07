# api/pletor: routy Pletora

Tenký router pro `backend/agi_pletor/` (docs/navrhy/2026-11-04-pletor-jarvis.md, P1). Jen člověk v UI
(`require_human`, jinak 403) a jen z tohoto počítače (`/api/pletor` v `backend/app/remote_access.py`).

- `POST /api/pletor/messages {project, workspace, text, voice?}` → `{reply, actions: [{type, text, ok, detail?}]}`.
  `voice: true` (P3, hlas) přidá do vstupu modelu řádek `service.VOICE`: krátká odpověď ke čtení nahlas.
  Cizí klíč nebo prázdný text 422, neznámý projekt 404 `project_not_found`.
- `POST /api/pletor/messages/stream` (stejné tělo i kontroly) → `application/x-ndjson`, objekt JSON na řádek:
  `{"type": "delta", "text"}` nula a víckrát (složené kousky = `reply`), nakonec vždy `{"type": "done", reply,
  actions}` ve tvaru `/messages`. Chyba modelu i neočekávaná výjimka tahu = jen `done` s textem chyby, přepínací věta
  mozku = jen `done`. Tah běží ve vlákně a předává kousky frontou; odpojený klient tah nezastaví, zpráva se uloží.
- `GET /api/pletor/state?project&workspace` → `{messages: [{role, text, at}], heart: {running, pending, sleeping,
  error, idleReason, lastSummary}, escalations: [{ticketId, text, createdAt}], brain: {brain: claude | ollama, model,
  available: [modely Ollamy]}}`. `available` jde z `/api/tags` při každém čtení; neběžící Ollama = `[]`.
- `POST /api/pletor/brain {brain: claude | ollama, model?}` → `{ok, reply, brain}` (P2). Neběžící Ollama nebo
  neznámý model = `ok: false` s důvodem v `reply`, mozek zůstane. V UI se přepíná větou v chatu (`backend/agi_pletor/brains.py`).
- `GET /api/pletor/voices?warm=<id>` → `{voices: [{id, label, gender, engine: xtts | elevenlabs | edge | piper,
  available, reason, quota}]}` (P3b, `backend/agi_pletor/speech.py`): všechny známé hlasy v pořadí XTTS → ElevenLabs → Edge → Piper, nedostupné
  s důvodem (nestažený model, málo VRAM, chybějící balíček, tarif ElevenLabs); `quota` `{tier, character_count, character_limit}` jen u ElevenLabs (cache 60 s). ElevenLabs má samostatné položky `elevenlabs:brian`, `elevenlabs:bill` a `elevenlabs:custom` (jen z `.env`), každá s vlastní dostupností a společnou kvótou účtu; neznámý `elevenlabs:<klíč>` v `POST /tts` je 404. Na pozadí načte dopředu `warm` (jinak nejlepší dostupný).
- `POST /api/pletor/tts {text, voice?}` (P3b): engine je v id hlasu. Piper `audio/wav`, Edge a ElevenLabs `audio/mpeg`
  (streamovaně, **cloud Microsoftu: text odchází z počítače**), XTTS `audio/pcm;rate=24000` (PCM 16 bit LE po
  kouscích). Odpověď přijde až s prvním kouskem zvuku. Text 1–600 znaků, prázdný nebo cizí klíč 422; nestažený či
  neznámý hlas 404 „Hlas není stažen.“ (`voice_missing`, `hint` = příkaz ke stažení), nedostupný engine 503.
- `GET /api/pletor/llm` → `{claude, codex, ollama, cswap}` (M1 nastavení LLM, jen ke čtení,
  `backend/agi_pletor/llm_settings/`). Sekce se čtou souběžně a každá selže zvlášť jako `{available: false, reason}`, route
  nikdy 500. Žádné parametry, cesty jen z `Path.home()`; tokeny ani úplné e-maily v odpovědi nejsou.
- Velín, jen čtení (`dashboard_routes.py`, logika `backend/agi_pletor/dashboard/`): `GET /heart?project&workspace` → `{status, queue:
  [{workspace, pending}], batches (20), gate, brain: {version, activatedAt} | null}`; `GET /context` → `{text, sections:
  [{title, chars, cap, truncated}]}`; `GET /messages?project&workspace&limit=50&q=` → `{messages, total}`; `GET /monitoring?project`
  → `{hosts, events (50), enabled}`. Sekce, jejíž zdroj selže, je `{error}`.
- Dílna D0 (`workshop_routes.py`, logika `backend/agi_pletor/pletor_opora_settings/`): `GET /api/pletor/workshop/tools`
  → `{tools}`, `POST …/tools/{name}/measure` (tělo `{}`) → měření funkce; neznámá 404, špatný název 422.
- Žádosti srdci (`pletor_requests_routes.py`, logika `backend/agi_pletor/linie/requests.py`, docs/navrhy/2026-11-06-linie-rebrand.md
  §4a): `POST /api/pletor/requests?project {text, idempotencyKey}` → `{id, text, steps: [{k: accepted, at, by}]}`;
  `POST …/{id}/steps {k, evidence}` nebo `{k, failed: true, why}` jen agent / token brány (člověk 403 `agent_only`),
  důkaz povinný (422); `GET …?open=1` → `{requests, open}`. Operace Linie L7e (attempt, revert, rebase-note, unblock,
  `GET /api/pletor/linie/journal?after=`) popisuje hlavička `linie_work_routes.py`.

Instance `Pletor` žije v `app.state.pletor` (`backend/app/factory.py`); testy jí vyměňují `runner`, `find`
a `transport` (Ollama).
