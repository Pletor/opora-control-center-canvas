# Tok událostí OporaHubu

[Stav pro agenty](oporahub-agent-state.md) je **snímek**; tok událostí je **delta** mezi snímky.
Živá vizualizace procesu si načte `agent-state`, vezme jeho `eventsCursor` (kurzor toku ve stejném
snímku) a dál jen přijímá události po něm. Každá událost vzniká **v místě změny** (ve službě nebo repozitáři, který změnu zapisuje)
a zapisuje se do tabulky `opora_events` ve **stejné SQLite transakci** jako změna: zrušená změna
nezanechá událost a potvrzená změna má právě jednu. Nic se neodvozuje porovnáváním snímků.

Kód: `backend/canvas/opora_events.py` (`emit_event`), `opora_event_stage.py` (etapa a brána karty),
emise `opora_lease_events.py`, `opora_changeset_events.py`, `opora_card_events.py` a v repozitářích
review, ověření a auto-rebase; schéma `database/schema/opora_event_schema.py`, čtení
`database/repositories/opora_events.py`, router `backend/api/editor/opora_event_routes.py`.

## Tvar události

```json
{"id": 42, "at": "2026-10-22T01:02:03.456Z", "kind": "stage.changed",
 "projectId": "p1", "workspaceId": "w1", "nodeId": "card-a", "executionId": "9f…",
 "stepId": null, "prNumber": null, "stage": "work", "health": "ok",
 "actor": {"kind": "agent", "name": "agent:worker"},
 "data": {"reason": "runs_active", "previous": {"stage": "plan", "health": "ok", "reason": "card_in_plan"}}}
```

| Pole | Význam |
|---|---|
| `id` | Monotónní kurzor (celé číslo, v rámci projektu; `AUTOINCREMENT`, nikdy se neopakuje) |
| `at` | Čas zápisu, ISO 8601 UTC s milisekundami |
| `kind` | Druh (tabulka níže) |
| `projectId`, `workspaceId` | Rozsah |
| `nodeId`, `executionId`, `stepId`, `prNumber`, `stage`, `health` | Vždy přítomné, `null` když se netýkají |
| `actor` | `{kind: "human" \| "agent" \| "system", name}`; serverové kroky jsou `{system, "opora"}` |
| `data` | Podrobnosti druhu (objekt, klíče seřazené) |

## Druhy

| `kind` | Kdy vzniká (místo změny) | `data` |
|---|---|---|
| `lease.claimed` | Nový claim běhu (`OporaExecutions.claim`, ne replay) | `epoch`, `acceptedRevision`, `expiresAt` |
| `lease.heartbeat` | Prodloužení pronájmu, které je vidět (viz [Heartbeat v toku](#heartbeat-v-toku)) | `epoch`, `expiresAt`, `ttlSeconds`, `capped`, `reason` |
| `lease.expired` | Prošlý pronájem karty je nahrazen novým claimem (viz níže) | `expiredAt`, `previousOwner`, `replacedBy` |
| `result.reported` | Nový výsledek běhu (ne replay `requestId`) | `receiptId`, `acceptedRevision` |
| `step.started` / `step.done` / `step.failed` | Postup kroků plánu (modul plánu kroků, volitelný) | dle modulu kroků |
| `pr.linked` | Nová vazba běh → PR | `repository`, `headSha`, `headRef` |
| `review.round` | Nové kolo review (vložená úloha) a každá změna jeho fáze nebo čísla kola | `reviewJobId`, `kind`, `round`, `phase`, `headSha`, `riskTier`, `repository` |
| `review.finding` | Nový nález review a každá změna jeho stavu | `findingId`, `severity`, `status`, `round`, `headSha`, `repository` |
| `gate.changed` | Brána merge karty se po zápisu změnila (odvozené, viz níže) | `gate {status, rule}` nebo `null`, `previous` |
| `harness.fixture.observed` | Complete native Harness fixture observation queued for role memory; quiet event does not change card stage or acceptance | `verificationId`, `outcome` |
| `formal.result` | Zapsaná zpráva ověření (`formal/*`, ruční i z CI) | `verificationId`, `outcome` |
| `decision.created` | Vzniklo rozhodnutí člověka: návrh k přijetí (`accept`), merge čekající na uzavření (`close_card`), ověření `verification_counterexample` / `verification_failed` | `decision`, + kontext |
| `decision.resolved` | Rozhodnutí vyřízeno: přijetí návrhu (`accept`), uzavření karty po merge (`close_card`), rozhodnutí na stropu kol review (`review_round_cap`) | `decision`, + kontext |
| `changeset.proposed` | Nový návrh zadání (i přenesený a auto-rebase) | `proposalId`, `subject`, `parentRevision`, `supersedes`, `nodeIds` |
| `changeset.accepted` | Přijatá hlava se posunula na revizi, která přijímá návrh (zadání, graf i obsah) | `proposalId`, `acceptedHead` |
| `autorebase.done` | Auto-rebase návrhu skončil `rebased` nebo `redundant` (jednou na návrh a hlavu) | `proposalKind`, `proposalId`, `acceptedHead`, `outcome`, `resultId`, `reason` |
| `autorebase.conflict` | Auto-rebase otevřel konflikt | stejné jako výše |
| `merge.done` | Uzavření smyčky zapsalo merge PR | `repository`, `mergeSha`, `mergedAt` |
| `writeback.done` | Zápis merge zpět do plánu (stejný krok jako merge, `planWrittenBack: true`) | `repository`, `mergeSha`, `planWrittenBack` |
| `card.closed` | Člověk potvrdil uzavření karty (`done.confirmed` false → true) | `by`, `at` |
| `guard.alert` / `guard.resolved` | Strážce našel nový nález / nález zmizel ([strážci](strazci.md)); tiché (`QUIET`), actor `{system, "strazce:<id>"}`, fáze `mapa` → plan, `prace` → work, ostatní → checks, `block` → stav blocked; první běh strážce v projektu / dávka >20 nových nálezů = jedna souhrnná `guard.alert` bez `nodeId` (`rule: "baseline"` / `"batch"`) | `key`, `guard`, `rule`, `severity`, `message`, `journeyId?`; souhrn: `guard`, `rule`, `count`, `bySeverity`, `severity`, `message` |
| `worker.message` | Srdce poslalo pokyn běžícímu dělníkovi (`ticket.direct`, plátno 3 F2); tiché, actor `{agent, "heart"}`, `nodeId` = karta ticketu | `ticketId`, `feedbackId`, `severity` (`hint`/`course`/`stop`), `text` |
| `card.signal` | Spouštěč karty vzbudil srdce (`determinism/triggers.py`); tiché, actor `{system, "hlídač"}` u `card.stalled`/`card.failing`/`card.drift`, jinak `{system, "trigger"}` | `signal`, `detail`, `state` |
| `stage.changed` | Etapa karty se po zápisu změnila (odvozené, viz níže); nese `stage` a `health` | `reason`, `previous` nebo `null` |

### `stage.changed` a `gate.changed`

Po každé zdrojové události, která nese `nodeId`, a po zápisech bez vlastního druhu, které etapu
mění (uvolnění běhu, zavření či znovuotevření PR, nová hlava PR, vlastní kontroly agenta,
pozorování cílové větve, lidské review, znovuotevření karty, posun přijaté hlavy), spustí se
deterministická funkce `refresh_card`. Ta ve stejné transakci přepočítá etapu jedné karty
pravidlem [etapy karty](oporahub-agent-state.md#etapa-karty-cards) a bránu jejího otevřeného PR,
porovná je s posledně vydanou hodnotou v `opora_event_card_state` a událost vydá **jen při změně**
(první výpočet karty má `previous: null`). Selhání přepočtu se vrátí na savepoint a nikdy nezruší
změnu, která ho spustila.

Rozdíl proti snímku: připravenost ke claimu (`claim`) se zde nepočítá (potřebuje celé zadání),
karta bez faktů běhu je `plan`. Pravidla závislá jen na čase (`lease_past_deadline`) událost
nevyvolají; prošlý pronájem se zapíše jako `lease.expired`, když ho nahradí nový claim
(server nemá úklidovou smyčku pronájmů). Čtení (`agent-state`, `process`, historie, výpisy)
nikdy událost nevytváří.

## API (jen čtení, pro agenty i lidi)

`GET /api/oporahub/events?project=<id>&workspace=<id>&since=<cursor>&limit=<1–500>[&nodeId=<id>]`

```json
{"events": [...], "cursor": 57, "head": 60, "gap": false}
```

- `since` (výchozí `0`) je výlučný kurzor; `cursor` je `id` poslední vrácené události, bez událostí
  zůstává `since`. Další stránka: `since=cursor`.
- `workspace` je volitelný filtr; bez něj jdou události všech prostorů projektu.
- `nodeId` je volitelný filtr na jednu kartu (dráha karty; včetně odvozených `stage.changed` /
  `gate.changed`). Neplatné ID (`[A-Za-z0-9_-]{1,80}`) → `409`, `code: "events_unavailable"`.
  `cursor` se posouvá jen po vrácených událostech; `head` a `gap` platí pro celý outbox.
- `head` je nejvyšší `id` v outboxu. Konzument, který právě načetl `agent-state`, začne sledovat od
  jeho `eventsCursor` (přečteného ve stejném snímku); `head` z pozdějšího čtení by mohl přeskočit
  událost zapsanou mezi oběma čteními.
- `gap: true` znamená, že retence smazala události po `since`; konzument znovu načte `agent-state`
  a pokračuje od `head`.

`GET /api/oporahub/events/stream?project=<id>&workspace=<id>[&since=<cursor>][&nodeId=<id>]` (SSE, filtr `nodeId` jako výše)

- Obnova: hlavička `Last-Event-ID` (prohlížečový `EventSource` ji posílá sám), jinak `since`, jinak `0`.
  Hlavička má přednost i před `since` v URL: `EventSource` se po výpadku připojuje na tutéž adresu.
- Rámec: `id: <id>` + `data: <událost JSON>`; pole `event:` se neposílá, vše chodí do `onmessage`.
- Na začátku `retry: 2000`, každých 15 s komentář `: heartbeat`.
- Omezení: nejvýš 200 událostí na jedno čtení, spojení končí po `OPORA_EVENTS_STREAM_SECONDS`
  (výchozí 300 s; klient se připojí znovu s `Last-Event-ID`) a souběžně nejvýš 8 proudů na proces
  (jinak `429`, `code: "events_busy"`).

## Heartbeat v toku

Pronájem se prodlužuje při každém heartbeatu (`expiresAt`, epocha i autorita beze změny), ale
`lease.heartbeat` vzniká jen tehdy, když se na pronájmu něco viditelně změní, jinak nanejvýš jednou
za `OPORA_LEASE_HEARTBEAT_EVENT_MINUTES` (výchozí 15 min, `0` = každý heartbeat) na běh.
Kancelář totiž prodlužuje každou třetinu TTL a běh čekající na obnovu limitu by jinak tok zaplavil
stovkami řádků za hodinu. `data.reason` říká proč:

| `reason` | Kdy |
|---|---|
| `first` | První heartbeat běhu po claimu |
| `epoch` | Epocha se liší od posledního ohlášeného heartbeatu |
| `ttl` | Požadované `ttlSeconds` se změnilo |
| `capped` | `expiresAt` začal (nebo přestal) být omezen termínem rozpočtu běhu |
| `late` | Prodlouženo s méně než třetinou TTL v záloze: heartbeaty vypadly a běh se zotavil |
| `keepalive` | Od posledního ohlášeného heartbeatu běhu uplynul interval |

Tichý heartbeat přepočte kartu stejně jako dřív událost (`refresh`), takže `stage.changed` /
`gate.changed` vznikají beze změny. `cards[].lastEventAt` a stáří zdroje Opora v `process-health`
se u čekajícího běhu posouvají po intervalu, ne po každém heartbeatu; čerstvost pronájmu nese
`lease.expiresAt` ve snímku.

## Retence

Každá 256. událost spustí ve stejné transakci úklid: smaže události starší než
`OPORA_EVENTS_RETENTION_DAYS` (výchozí 14) a vše nad nejnovějších `OPORA_EVENTS_MAX_ROWS`
(výchozí 50 000). Kurzory se nerecyklují, takže zastaralý kurzor se pozná podle `gap`.

## `emit_event` pro další moduly

```python
from backend.canvas.opora_events import emit_event

emit_event(conn_or_service, *, project_id, workspace_id, kind, node_id=None, execution_id=None,
           step_id=None, pr_number=None, stage=None, health=None, actor=None, data=None) -> int
```

- `conn_or_service`: spojení SQLite, objekt s `.db` (repozitář) nebo služba plátna (`db_for(project_id)`).
- V otevřené transakci se řádek připojí k ní; mimo transakci se potvrdí samostatně.
- `kind` musí být z tabulky výše (jinak `ValueError`); `actor` je `{kind, name}`, řetězec
  (`"human"`, `"system"`, jinak jméno agenta) nebo `None` (systém).
- Událost s `node_id`, která není `stage.changed`, `gate.changed` ani `step.*`, spustí přepočet
  etapy karty. `refresh(conn, project, workspace, node)` přepočítá kartu bez vlastní události.

## Živý proces (`opora.process-event/1`)

Outbox nese i [živý proces](zivy-proces.md). Tabulka má nullable sloupce `source`, `phase`, `state`,
`title`, `detail`, `refs` (JSON), `tool` (JSON) a `external_id` (aditivní migrace
`ensure_process_columns`). Každá událost toku proto za původními poli nese navíc `source`,
`phase`, `state`, `title`, `detail`, `refs`, `tool`, `externalId`, `schema` a `eventId`; u událostí
Opory (sloupce NULL) je čtení dopočítá z `kind` (`backend/canvas/opora_event_process.py`).
Kancelář (agent-office) zapisuje přes `POST /api/oporahub/process-events` vlastní druhy
(`tool.use`, `worker.status` …) se `source: "office"`; ty nikdy nespouštějí přepočet etapy.
Druhy `memory.recall`, `memory.write` a `plan.commit` přidává most ze záznamu činnosti, protože
paměť role a starý commit zadání vlastní událost nemají. `emit_event` i příjem budí SSE proud
signálem, takže nová událost odchází hned, ne po dalším pollu.

## Ověření

`uv run pytest backend/canvas/test_opora_events.py backend/canvas/test_opora_events_pull_requests.py backend/canvas/test_card_dag.py backend/api/editor/test_opora_event_routes.py backend/canvas/test_opora_agent_state_events.py`
pokrývá právě jednu událost na změnu (i při replay), `stage.changed` jen při změně, žádné události
při čtení, návrat s transakcí, retenci, stránkování kurzorem, mezeru po retenci, obnovu SSE
přes `Last-Event-ID`, heartbeat, limit proudů, odmítnutí cyklu a `blockedBy` / `topoIndex`,
filtr `nodeId`, `eventsCursor` ve stejném snímku jako agent-state (i proti souběžnému zápisu)
a `cards[].lastEventAt`.
