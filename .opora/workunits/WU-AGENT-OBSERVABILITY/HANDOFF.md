# WU-AGENT-OBSERVABILITY — handoff (Sonnet, 2026-09-10)

## Vlastněné cesty (tato větev, tento writer)
- `backend/agent_sources.py` — read-only adaptéry: `PlatnoSource` (klient na `127.0.0.1:8738` status API) a `LocalOrchestratorSource` (čte `state.json`/`events.jsonl`/`result.json` pod jedním nakonfigurovaným kořenem Hermes handoffs), sdílená `redact()` a `_default_pid_probe`.
- `backend/agent_bindings.py` — `AgentBindings`: explicitní vazba `{project, workspace, layer, nodeId, sourceId, runId, sessionId}` s CAS (`expectedRevision`), validací uzlu proti aktuálnímu grafu, sektorovou agregací přes `parentId` topologii a `filter_unbound`.
- `backend/agent_activity.py` — `AgentActivityJournal`: append-only žurnál klíčovaný `(source_id, run_id, source_event_id)`, dedupe, `sourceTimestamp` vs `ingestTimestamp` odděleně.
- `backend/agent_catalog.py` — `AgentCatalog`: agreguje oba zdroje do jednotného seznamu běhů + detailu se 4 úrovněmi „mozku pro LLM“; chybějící pole harness poctivě označuje `"unavailable"`, nic nevymýšlí.
- `backend/agent_routes.py` — **jediný router factory** `create_agent_router(service, *, platno_base_url=None, orchestrator_root=None) -> APIRouter`.
- `tests/test_agent_sources.py`, `tests/test_agent_bindings.py`, `tests/test_agent_activity.py`.
- `src/agent-types.ts`, `src/AgentsWorkspace.tsx`, `src/NodeActivity.tsx`, `src/agents.css`.
- `.opora/workunits/WU-AGENT-OBSERVABILITY/` (tento adresář).

Nedotčeno (dle zadání): `backend/app.py`, `service.py`, `gitio.py`, `node_text.py`, `node_links.py`, `node_journal.py`, `src/App.tsx`, `types.ts`, TextWorkspace/NodeTextEditor/Board/ProjectMap.

## Kontrakt pro integraci rodičem

### Backend
V `backend/app.py`, po vytvoření `service` a `app`, přidat:
```python
from .agent_routes import create_agent_router
app.include_router(create_agent_router(service))
```
Nic víc — router si sám vytváří vlastní SQLite tabulky (`agent_bindings`, `agent_binding_scopes`, `agent_activity_entries`) přes `service.db` při prvním volání factory, analogicky k `ProjectHub`. Žádná migrace `service.py` není potřeba.

Konfigurace (volitelná, env proměnné, výchozí odpovídají ověřenému živému stavu):
- `OPORA_AGENT_PLATNO_URL` (výchozí `http://127.0.0.1:8738`)
- `OPORA_AGENT_ORCHESTRATOR_ROOT` (výchozí `C:\Users\Admin\AppData\Local\hermes\handoffs\canvas-orchestration`)

### Endpointy (schéma pro UI i pro nástroje agentů — stejné JSON API)
- `GET /api/agents/sources` → zdravotní stav zdrojů (`{sourceId: {available, status|error, lanes?}}`).
- `GET /api/agents/runs?source=&limit=&cursor=` → `{items:[RunSummary], nextCursor, total}` (dedupe podle `(sourceId, runId)`, bounded `limit<=100`).
- `GET /api/agents/runs/{sourceId}/{runId}` → `RunDetail` + `brain` (4 úrovně); `404 {"error":...}` pro neznámý `sourceId` nebo neplatný/neexistující `runId` (chráněno proti path escape — `runId` musí projít `[A-Za-z0-9_-]{1,64}`).
- `GET /api/agents/unbound?source=&limit=` → kandidáti dosud nepřiřazení k žádnému uzlu.
- `POST /api/agents/bindings` `{project,workspace,layer,nodeId,sourceId,runId,sessionId,expectedRevision,confirmed:true}` → CAS vazba; `ValueError` (409 přes stávající `app.py` handler) při cizím uzlu/neznámém zdroji/neshodě revize/chybějícím potvrzení.
- `GET /api/agents/bindings?project=&workspace=&nodeId=` → `{revision, items:[Binding]}`.
- `GET /api/agents/bindings/sector?project=&workspace=&nodeId=` → agregace přes potomky (`parentId`), deduplikovaná.
- `POST /api/agents/activity` `{project,workspace,nodeId,sourceId,runId,sourceEventId,sourceTimestamp,kind,summary}` → append-only capture, idempotentní podle `sourceEventId`.
- `GET /api/agents/activity?project=&workspace=&nodeId=` → seznam žurnálu (jen čtení).

Příklad read-only CLI (bez credentials, jen loopback GET):
```bash
curl -s http://127.0.0.1:8740/api/agents/sources
curl -s "http://127.0.0.1:8740/api/agents/runs?limit=10"
curl -s http://127.0.0.1:8740/api/agents/runs/hermes-orchestrator/agents-sonnet
```

### Frontend
- `AgentsWorkspace({ project, workspace, onOpenNode? })` — samostatný pracovní mód „Agenti“ (analogie Struktura/Kreslení/Mapa); vlastní polling (4 s, pauzuje na `document.hidden`, čistí interval při unmountu).
- `NodeActivity({ project, workspace, nodeId, isSector?, onOpenRun? })` — vložit do detailu uzlu/sektoru (`NodePanel`/`Board`, mimo tuto WU); zobrazuje přiřazené běhy, sektorový souhrn, žurnál; `onOpenRun(sourceId, runId)` je jediná navigace ven (žádné vlastní přesměrování).
- Rodič musí přidat položku do `mode-rail` a routovací stav pro nový mód a předat `onOpenNode`/`onOpenRun` propojení mezi `AgentsWorkspace` a `NodeActivity`/`Board` — to už je mimo vlastněné soubory této WU.

## RED → GREEN (přesné příkazy a exit kódy)
1. `uv run pytest tests/test_agent_bindings.py -q` před vytvořením `backend/agent_bindings.py` → **RED**: `ModuleNotFoundError: No module named 'backend.agent_bindings'`, exit 2 (collection error).
2. Po implementaci: `uv run pytest tests/test_agent_bindings.py -q` → **GREEN**: `7 passed`, exit 0.
3. `uv run pytest tests/test_agent_activity.py -q` před `backend/agent_activity.py` → **RED**: `ModuleNotFoundError`, exit 2.
4. Po implementaci: `uv run pytest tests/test_agent_activity.py -q` → **GREEN**: `5 passed`, exit 0.
5. `backend/agent_sources.py` a jeho testy (`tests/test_agent_sources.py`, 13 testů) byly navrženy společně (netestováno v čistém RED stavu modulu — přiznaná odchylka od striktního pořadí u tohoto jednoho souboru); přesto GREEN: `9 passed` u čistě zdrojové vrstvy a po doplnění route-smoke testů `13 passed`.
6. Regrese celého backendu: `uv run pytest -q` → **GREEN**: `113 passed`, exit 0 (žádný dřívější test nebyl oslaben ani smazán).
7. `uv run ruff check backend/agent_*.py tests/test_agent_*.py` → **GREEN**: `All checks passed!` (dva `except Exception` v PID probe mají zdůvodněné `# noqa: BLE001` podle konvence `coding_worker.py`/`llm_runs.py`).
8. Frontend: `npx tsc --noEmit` → GREEN (bez výstupu = bez chyb). `npm run build` → GREEN (`✓ built`), beze změny existujících bundle chyb.

## Ověřený živý stav zdrojů (ne fixtures)
- `GET http://127.0.0.1:8738/health` → `{"status":"degraded","bridge":{"status":"unavailable","error":"bridge_unavailable","bridge_status":503}}` — potvrzeno přímým `curl` při implementaci.
- `GET http://127.0.0.1:8738/api/status` → `bridge.ok=false`, `running=[]`, `waiting=[]`, `cost.today_usd=0.0` — **tato nula je artefakt staré implementace při nedostupném bridgi**; `PlatnoSource.status()` proto při `bridge.ok=false` vrací `cost.todayUsd=None` s `note:"cost_unreliable_source_bridge_unavailable"`, nikoli `0.0` jako fakt.
- `GET http://127.0.0.1:8738/api/platno/projekty` → 2 reálné projekty (Ample Lab, Opora velín) — parser ověřen na tomto přesném tvaru.
- `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/{ample-sonnet,natural-opus,agents-sonnet}/state.json+events.jsonl` — skutečné, právě běžící soubory (žádné `result.json` zatím neexistuje u žádné ze tří lan; `LocalOrchestratorSource` to hlásí jako `null`, ne jako vynucené `done`). Ověřený tvar Claude Code event envelope: `type` ∈ `{system, assistant, user, rate_limit_event, result}`; `assistant.message.content[]` obsahuje `thinking` (odstraněno), `text`, `tool_use`; `user.message.content[]` obsahuje `tool_result`. `result` nebyl v žádném souboru pozorován (běhy stále běží), takže `doneReason` je v praxi vždy `null` — poctivě, ne fabrikovaně.

## Přiznaná omezení / chybějící integrace
- **Nic z tohoto není zapojeno do běžící aplikace na 8740** — `app.py`, `App.tsx` a mode-rail zůstávají nedotčené dle zadání; rodič musí provést `include_router` a přidat UI mód/propojení.
- `PlatnoSource.status()` `running`/`waiting` pole byla za celou dobu implementace prázdná (bridge je nedostupný); parser pro neprázdné položky (`run_id`/`session_id` extrakce) je defenzivní, ale **tvar naplněné položky nebyl nikdy pozorován v datech** — jde o nejlepší odhad podle `models.py`/`bridge.py` schémat z handoffu, ne o ověřený reálný záznam.
- Liveness PID probe na Windows používá `OpenProcess`; protože žádný `state.json` neobsahuje čas vzniku procesu, výsledek je téměř vždy `last_reported_running_liveness_unverified` (nikdy tvrzeno jako ověřeně živé) — to je záměr, ne nedodělek.
- `AgentCatalog` čte pouze `list_lanes()` z kořenového adresáře (aktuálně 3 skutečné podadresáře); nikdo jiný v Hermes/Claude historii se nečte (žádný glob mimo tento kořen).
- Úroveň „mozku pro LLM“ (prompt/kontext/verifikace/iterace) je u obou zdrojů z větší části `"unavailable"`, protože ani `wt-cc-platno`/Bridge, ani ad-hoc Hermes orchestrace tato pole dnes neexportují — engine, který by je naplnil, je přiznaně mimo tuto WU (další WU dle zadání).
- Redakce v `agent_sources.py` je vlastní (ne import) reimplementace principu z `OporaCC/src/oporacc/security.py` (provenance okomentována v kódu); nebyla srovnávána byte-for-byte s originálem, jen funkčně (klíčová slova + vzory tajemství).
- `POST /api/agents/bindings` a `POST /api/agents/activity` samy o sobě neregistrují `ValueError` handler — spoléhají na existující globální handler v `app.py` (409). V izolovaných testech přes `TestClient` (bez `app.py`) proto testuji jen přes přímé volání tříd, ne přes HTTP POST chybové větve — to je zdokumentovaná mezera v pokrytí route vrstvy pro chybové stavy zápisu.

## Commit
`2cecf5e44bc31bbad87307d593ce8ff4d5d2ad21` na větvi `feat/agent-observability`, base `dbc19ffac783755ac06b7e7e17fc36a57f38b8c0`. Seznam souborů viz `EVIDENCE.json`.
