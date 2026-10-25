# Připnutá výbava Harness

[Zpět na README](../README.md).

Zadání karty může obsahovat volitelné `fields.harness`. Plánovač do něj vloží
konkrétní obsah vybraných prostředků; návrh projde stejným přijetím jako ostatní
zadání. Záložka Zadání a panel přijetí návrhu zobrazují celou výbavu včetně změn,
obsahu, SHA-256 a požadavků. Nepřijatý návrh neovlivní běh.

```json
{
  "schema": "harness.kit/1",
  "problems": ["ts.references"],
  "resources": [{
    "slot": "rules.quality",
    "resource": "rule:quality",
    "category": "rules",
    "digest": "<SHA-256 přesného UTF-8 obsahu>",
    "content": "Před odevzdáním ověř zadání a spusť kontroly repozitáře.",
    "requires": ["command:npm"]
  }]
}
```

Příklad digestu je zástupný text. Skutečný návrh musí uvést 64 hexadecimálních
znaků vypočtených z `content`; rozdíl jediného znaku se odmítne. Kategorie jsou
`instructions`, `skills`, `hooks`, `rules`, `commands`, `scripts`, `tools`, `mcp`,
`memory`, `plugins`, `permissions`, `testing`, `operations`.

Výbava má nejvýše 24 prostředků, každý s jedinečným slotem a ID, 1–8 typů problémů
a nejvýše 16 různých požadavků na prostředek. Celé JSON vyjádření má nejvýše 96 KiB
včetně metadat a escapování Unicode. Při změně požadavků nebo kategorie se mění
digest zadání; obsahový digest prostředku zůstává vázaný na jeho přesný obsah.
Prázdné `resources` připíná prázdnou výbavu. Chybějící `harness` zachovává starší
zadání; `null`, neznámá pole a pokus přidat například `verified: true` se odmítnou.

Kontext v2 zahrne výbavu do existujících přijatých dokumentů, privátního SQL
snímku, HMAC kontextu a digestu zadání. Nepřidává živou přípravu ani druhý zdroj
kontextu. Příprava znovu ověří obsah po redakci tajemství; změněný obsah nesmí
zachovat původní digest. Změna relevantního zadání po převzetí zneplatní starý
kontext podle stávajících pravidel. Původní přidělený snímek zůstane dohledatelný.

Karta s `harness` vyžaduje přípravu a claim s `contextProtocolVersion: 2`; v1 ji
výslovně odmítne. Přehled procesu a agent-state ji přesto hlásí jako připravenou:
`GET /executions/context` vrátí `available: true`, `contextProtocolVersion: 2` a
`contextVersion: null` a akce `claim` nese předpoklad `contextProtocolVersion: 2`.
Kancelář ve v2 si kontext připraví a kartu převezme, i autopilotem. Kancelář ve v1
takovou akci přeskočí. Pro agent-office nastavte na serveru
`AGENT_OFFICE_OPORA_CONTEXT_VERSION=2` a po sestavení restartujte server i klienta.
Výchozí starší režim kanceláře není aktivací této funkce. Karty bez výbavy mají
dosavadní kompatibilitu.

`requires` popisuje potřebné schopnosti. Samotný dokument nástroje neinstaluje,
nespouští a neuděluje oprávnění. Runner musí před použitím ověřit jejich skutečnou
dostupnost. `kit_of_assignment` čte pouze prostředky cílové karty z již ověřeného
zadání; nevybírá výbavu sousední karty. Nejde o serverem potvrzený záznam použití
ani o důkaz, že prostředek přispěl k výsledku.

Tato část zavádí přijímaný přenos verzí. Výběr z globální až karetní knihovny,
automatické doporučování, Context7 a ukládání zkušeností přes
OpenViking zůstávají navazujícími částmi autonomního učení. Přidávání výbavy je
zatím přes běžné návrhy změn API; textový editor zachovává rozšířená pole.

## Měření výsledků

`GET /api/oporahub/harness-learning?project=P&workspace=W` vrací statistiky vybraných
prostředků podle verze konfigurace, typu problému a úrovně důkazu. Volitelné filtry
jsou `nodeId`, `resource`, `limit` (1–100). `limited` upozorňuje na zkrácený seznam.
Rozsah je vždy konkrétní projekt a workspace; přenos zkušeností mezi projekty se
neprovádí automaticky. Obsah prostředků, tokeny běhu ani privátní zadání se nevracejí.

Projekce běží přes registr `opora_event_projections` přímo v transakci nativní
události před retencí outboxu. Měření nevytváří druhý event bus.
Pád projekce vrátí zpět i zdrojovou změnu. Odvozené tabulky nemají cizí klíč na
promazávaný outbox, uchovávají ID zdrojů a přežijí restart. Schéma se rozšiřuje
idempotentně; starší čtečka může nové tabulky ponechat bez jejich odstranění.
Při návratu ke staršímu writeru se nové události neměří: historická úplnost se
nepředstírá a automatický backfill není součástí této verze.

- `lease.claimed` zapíše vybranou výbavu s neznámým výsledkem pro každou úroveň.
- `result.reported` čte uloženou účtenku stejného běhu a digestu zadání. Úplné
  hlášení všech přidělených kroků jako `done` je úspěch úrovně `reported`; selhaný
  krok je její neúspěch. Chybějící nebo přeskočené kroky ponechávají výsledek neznámý.
- `decision.resolved` pro lidské `close_card` přidá `verified` úspěch, jen když
  existuje právě jeden propojený sloučený běh a přijatý rozsah zadání, grafu i obsahu
  zůstal po celé linii revizí shodný s připnutým snímkem (včetně změny a vrácení).
  Znamená lidské potvrzení tohoto výsledku, nikoli
  samostatné provedení testů serverem nebo důkaz odolnosti v produkci.
- Nativní `card.reopened` z lidského znovuotevření odvolá potvrzení na `unknown`.
  Pozdější nové potvrzení opraví stejný hlas. Starší doručená událost novější stav
  nepřepíše. Kancelář ani GitHub nemohou pomocí externího process-event tvrdit
  nativní lidské potvrzení.

Počítá se jeden výsledek na běh a úroveň; opakovaná účtenka nepřidává hlas.
Odpověď uvádí úspěchy, neúspěchy, neznámé výsledky, pokrytí, počet různých karet
a 95% Wilsonův interval. Neznámá úspěšnost je `null`, nikoli nula. Procento je
podmíněné známými výsledky; počet karet pomáhá odhalit opakování stejného úkolu.
Interval nepředstavuje záruku ani důkaz nezávislosti opakovaných běhů.

Prostředek je zatím doložený jako **vybraný ve výbavě**. Skutečné zavolání a příčinný
přínos se z toho neodvozují. `runner`, náklady, tokeny a časy zůstávají `null`, dokud
neexistuje měřený zdroj. `versionDigest` zahrnuje kategorii a požadavky, takže stejné
textové tělo v jiné konfiguraci nesdílí skóre. `promotionAllowed` je zatím `false`;
ověření dostupnosti, experimentální srovnání a povyšování navazují.

## Varovné signály regresí

Měřená konfigurace také vrací `guardrails`: počty různých běhů spojených
s incidentem nebo revertem z existujících neměnných případů review. Vazba vyžaduje
shodný projekt, prostor, kartu, přijatou revizi, repozitář, číslo PR, hlavu i merge SHA
a původní záznam incidentu či revertu. Duplicitní případy nezvyšují počet běhů.
Jde o negativní signál pro výběr výbavy; incident může být hlášený agentem a není
důkazem zavinění nástrojem. Úspěšnost přijetí se tím nepřepisuje. Doba produkčního
provozu zůstává neznámá a absence incidentu není úspěch. Jiná konfigurace nesdílí skóre.

## Automatické doručení do OpenVikingu

Nativní přiřaditelné lidské potvrzení zařadí pro každý vybraný prostředek odvozený
fakt do `harness_memory_deliveries` ve stejné transakci jako výsledek a zdrojová
událost. Znovuotevření karty zařadí odvolání. Jde o pozorování **vybrané výbavy**,
nikoli důkaz skutečného použití či příčinného přínosu nástroje. Do fronty nejde obsah
prostředků, zadání, přihlašovací údaje ani volný text agenta; jde o ID, digests,
typ problému, připnutou revizi a původ výsledku.

Worker spravovaný životním cyklem aplikace používá existující přepínač paměti a klíč
registrované role karty. Žádný klíč nevytváří, neobchází vypnutou paměť ani lidské
API `remember`. Síťový zápis běží mimo databázovou transakci a zámek projektu.
Chybějící role zůstane `waiting-role`, chybějící klíč či nedostupný server vede
k opakování s omezeným exponenciálním odstupem. Vypnutá paměť neprovádí pokusy.
`OPORA_HARNESS_MEMORY_WORKER=0` vypne pouze automatické doručování.

Jedna doručovací lease platí pět minut. Po pádu nebo ztracené odpovědi se stejný fakt
zapíše na stejnou adresu znovu. Každá zdrojová událost má vlastní neměnnou adresu
`harness-<SHA-256>.md` pod projektovou kartou příslušné role. Pozdní starý zápis tak
nepřepíše odvolání; stará zpráva zůstává historickým pozorováním. Před použitím
vzpomínky ověřte aktuální stav přes nativní `/harness-learning`. Paměť není zdrojem
pravomoci pro povýšení nástroje. Starý nedoručený fakt, který už není aktuální,
worker označí `superseded`.

`GET /api/oporahub/harness-memory?project=P&workspace=W&limit=100` ukáže stav,
počet pokusů o doručení, kód chyby a adresu přijatého zápisu. `submitted` znamená
potvrzené přijetí obsahu serverem OpenViking; nepředstírá dokončené indexování ani
extrakci paměti. Duplicitní doručení nemění počet hlasů. Fronta i její potvrzení
přežijí restart a retenci outboxu. Historická data se zpětně automaticky nedoplňují.

Regresní test `backend/library/test_harness_memory_precedence.py` vkládá do skutečného
node-briefu rozpornou starou vzpomínku. Přijatý cíl, omezení a acceptance zůstanou
nezměněné; heartbeat zachová původní assignment digest i připnutou výbavu. Jde
o ověření oddělení dat s náhradní pamětí, nikoli o důkaz poslušnosti LLM nebo
izolace živého OpenVikingu. Vzpomínka zůstává referencí v `context.roleMemory`.


## Server fixture experiences

When the native Harness verifier and its memory bridge are installed, complete
independent observations use the existing queue and registered role credentials.
The quiet `harness.fixture.observed` event and queue entry join the native report
transaction. Replaying a request creates neither a duplicate experience nor a new run.
A `harness.fixture-memory/1` document binds the exact candidate version, problem,
plan and baseline references, and native request/report digests. It contains no
source code, arguments, expected or raw outputs, or credentials.

Before delivery, the worker revalidates the stored native source and its content.
Incomplete, interrupted or stale-at-completion tests cannot become successful
experiences. Missing or altered source evidence is superseded before delivery.
The existing retry and lease recovery behavior applies when memory is unavailable.

`passed`/`failed` describes only the predeclared fixtures; `productionOutcome` is
`unknown` and `promotionAllowed` remains `false`. The `kind=harness-fixture` tag
separates this evidence from task acceptance and production success rates.
A later successful memory does not clear native quarantine for a failing version.
Agents must check current native recommendations before reuse; accepted and pinned
instructions take precedence over historical `context.roleMemory`. `submitted`
means only an acknowledged content write, not verified OpenViking indexing or extraction.


An isolated live pilot on 2026-10-23 exercised a real native container report,
transactional fixture queue, registered role delivery to OpenViking, exact content
readback, and subsequent `MemoryService.recall`. A different role could not read
the document; another project's recall excluded it. The pilot used a distinct
project in a separate Canvas data root and explicitly simulated plan acceptance.
It proves that transport and retrieval path, not production task acceptance,
semantic memory extraction, autonomous promotion, or correctness beyond its fixtures.


## Historical recovery proposals

`POST /api/oporahub/harness-recovery` takes `project`, `workspace`, `executionId`, `token`, `epoch`, `sourceExecutionId`, and `resource`. An identified actor and the currently active execution credential are required. The source must be an earlier execution of the same card in the same project/workspace; its assignment and kit must match their retained native enrollment. The selected resource must have the same identity, category and requirements, and both kits must address the same problems.

The response contains `harness.recovery-proposal/1`, a proposed kit with exactly that historical content version restored to the current slot, source digests and the current native outcome. No new archive is created: existing immutable execution assignments hold the bytes. Known verified failures and native incident/revert associations are refused. If the independent verifier module is installed, its retained quarantine is checked too; absent integration is explicitly unavailable.

A recovered version is a candidate, not a certified stable release. Unknown or withdrawn acceptance stays unknown; absence of a recorded incident is not production proof. The response always requires acceptance and denies promotion authority. Submit the proposed kit through the existing specification changeset flow, review it, and let normal acceptance and a new claim produce a new immutable assignment. This endpoint does not edit source files, restore a live profile, accept a plan, or replace a running agent's snapshot. Repeating the preview does not create another execution or specification. Worker CLI wiring and the evidence-gated automatic lifecycle are separate unfinished parts of the Harness goal.

Verification exercises real accepted kits and execution leases, exact historical content, repeated preview, credential/epoch/scope rejection, changed-card and incompatible-resource rejection, damaged enrollment, known failure/incident refusal and bounded HTTP input.

## Shared fixture lessons

With the optional native shared-evidence assessor installed, agents can call
`POST /api/oporahub/harness-shared-memory/publish` with only
`{"publication":"reviewed-publication-id"}`. The publication must already be
intentionally shared in the server's transfer policy and currently eligible.
The server generates a bounded `harness.shared-memory/1` lesson from the public
candidate/problem, policy and evidence digests, and approved source references.
Caller text, private card context, tool output, destination URIs and credentials
are not accepted. This is a fixture-based reuse suggestion, not stable promotion.

The first declared source owns delivery in its existing project database, through
its source card's registered role and the existing memory worker. No second queue,
administrative credential, global writable directory or source-success aggregation
is created. Assign a registered role to that source card and enable normal memory
delivery. The same publication/evidence snapshot queues once; changed evidence
creates another immutable lesson. Cross-project evidence is rechecked outside SQL
locks before and after writing. Withdrawal marks pending/affected delivery as
superseded. Restoring eligible evidence can requeue the same immutable lesson.

`POST /api/oporahub/harness-shared-memory/recall` accepts the same publication-only
body. It exposes only this intentionally public lesson, regardless of the caller's
target project. It checks fresh eligibility, requires a submitted queue record,
verifies the server-derived URI and exact remote OpenViking content, then checks
eligibility again. `verified-readback` confirms those bytes, not semantic indexing,
LLM correctness or future validity. Disabled memory, missing role/delivery, changed
proof, mismatched bytes and absent native support never yield an eligible lesson.
Existing private project/role recall and source records remain unchanged.

Agents must treat the result as evidence to inspect, verify the tool in their own
accepted assignment, and respect current recommendations. A shared lesson cannot
increase target success rates, clear quarantine or grant execution authority.
Older workers do not recognize this optional schema and will supersede its jobs;
rollback preserves prior outcome/fixture delivery. After reinstalling support,
republish an eligible reference to retry its existing immutable lesson.

## Accepted selection provenance (expand stage)

Native specification validation accepts `harness.kit/2` in addition to strict
`harness.kit/1`. Version 2 adds exactly one top-level field, `selection`:

```json
{
  "schema": "harness.selection/1",
  "policy": "harness.recommendation/1",
  "problem": "ts.references",
  "profileRevision": 3,
  "declaredCapabilities": ["command:npm"],
  "evidence": "caller-declared-selection",
  "entries": [{
    "resource": "rule:quality",
    "digest": "<same content digest as the kit resource>",
    "versionDigest": "<SHA-256 of canonical resource configuration>",
    "order": 0,
    "reason": "explicit-assignment",
    "assignments": [{"slot": "work", "scope": "task", "node": "opora:p:w:card"}]
  }]
}
```

The placeholder digests must be replaced with actual values. Configuration digest
uses compact JSON with sorted `category`, `digest`, `requires`, `resource` keys,
preserving requirement order. Entries cover every kit resource in the same order,
with exact ID, content digest and configuration digest. Metadata counts toward the
existing 96 KiB total. Each entry has at most 32 unique effective assignment slots;
scopes are global, repository, page, layer, area, sector or task. Unknown node
identity is `null`; global/repository origins cannot name a node. Profile revision
is a nonnegative safe integer or `null` when there are no explicit choices.
Declared capabilities contain at most 32 distinct identifiers and grant nothing.

Reasons are `explicit-assignment`, `baseline-policy`, `native-stable`,
`observed-outcomes`, `shared-fixture-exploration`, `unknown-exploration`, or
`inherited-settings`. Only explicit choices carry assignment origins. Generated
`profile:settings` has its own final entry and `inherited-settings` reason.
The policy identifies the recommendation contract, not an attested code revision.
The captured reason, origins and capability claims remain caller declarations;
validation never certifies that the decision was justified. Native outcome
projection does not award successful outcomes from these claims.

Existing acceptance pins the complete provenance in the immutable assignment.
A provenance-only change therefore changes prepared context identity. Historical
recovery changes a resource and consequently proposes a **new v1 kit** without
stale selection claims, through normal acceptance; neither existing kit changes.

This is a reader expansion, not automatic v2 rollout. Office writers and all
invocation/paired adapters must gain dual-version support before v2 is emitted to
workers. Older readers may explicitly reject v2. Do not downgrade an existing
accepted snapshot in place; roll back by proposing and accepting a new v1 kit.
All existing v1 fields, validation and historical reads remain unchanged.

Selection numeric fields follow JSON safe-integer semantics in both Python and
JavaScript: `3` and `3.0` have the same validity. Validation preserves the supplied
value and rejects booleans, fractions, nonfinite numbers and values above 2^53−1.
## Discover accepted formats before writing

`GET /api/oporahub/harness-kit-capabilities?project=PROJECT&workspace=WORKSPACE`
returns a scoped, non-cacheable `harness.kit-capabilities/1` response. It advertises
the installed acceptance validator's v1/v2 formats, selection format, context
protocol 2 and whole-kit limits. Writers must verify the linked peer and returned
scope before explicitly opting into v2. Missing endpoints on older installations
do not establish v2 support; never silently strip selection metadata or downgrade
an explicit v2 request.

This endpoint does not attest installed execution adapters, tool capabilities,
permissions, outcome verification or deployment readiness. Existing runtime
checks remain necessary. Restart the server after updating the installed modules.
## Historical selection origins

`GET /api/oporahub/harness-origin-history?project=P&workspace=W` groups native
reported and human-closed outcomes by exact resource version, problem, tier, and
the `(scope, node)` origin pinned in each immutable accepted kit. All seven scopes
are supported. This describes **caller-declared selection origins**, not independent
proof that a particular ancestor supplied the resource. Current graph/profile
changes never rewrite this historical dimension.

The reader checks the execution scope, assignment digest and native kit enrollment,
then strictly validates the target kit. Missing or corrupt historical records are
excluded and counted in `window.excluded`. Version-1 kits and selections without
explicit origins use `unknown`; the reader does not guess an ancestor. Multiple
slots from the same origin count once per execution/resource/problem/tier. A
resource with multiple different origins contributes once to each matching cohort;
**these cohorts overlap and must not be summed as independent executions**.

Optional `nodeId` limits the target card before the window is selected. `resource`,
`originScope` and `originNode` filter within that window; `originNode` requires a
node-bearing scope. `limit` (1–100, default 100) selects the newest enrolled
executions, not an all-time sample. The response contains at most 100 cohorts and
reports truncation through `limited` and `omittedCohortContributions`. Rates and
Wilson intervals apply only to included native outcomes in that window. Do not
compare them as whole-population rates when histories differ or are truncated.

The endpoint is non-cacheable and read-only. It returns no resource contents,
private execution credentials, or raw assignments. It creates no database table,
learning event, memory write, or recommendation update. Existing task projections
and recommendation policies remain unchanged. Invocation, causal contribution and
promotion authority remain false; consult native incident and verifier evidence
before reuse. This endpoint supplies historical comparisons, not production proof.


## Accepted preflight before a claim

After negotiating context protocol 2 through the existing execution context endpoint,
POST `/api/oporahub/harness-preflight` with `project`, `workspace`, `nodeId`,
`expectedAcceptedHead` and `expectedContextVersion` from that negotiation. An identified
human or agent is required. The request is limited to 4096 bytes and responses use
`Cache-Control: no-store`. A missing/stale context or invalid request returns 409;
missing identity returns 428 and excessive input 413.

The response (`harness.preflight/1`) contains only the target card's validated accepted
kit, its digest, the assignment digest and the exact context identities. A legacy card
without a kit returns null kit/digest; explicit malformed kit content is refused.
No live Harness profile, sibling documents, private context pin or execution token is
returned. This endpoint does not negotiate or initialize a missing sparse context.

The orchestrator must compare these identities again at claim and compare the claimed
immutable assignment/kit with its preview before seating. Previewing does not acquire
an execution, renew a lease, activate a tool or authorize a worker. Its evidence is
`accepted-context-preview`; `runnerReadinessVerified`, `executionAuthority` and
`permissionsGranted` are false. Runtime checks still belong to the intended worker
runner/environment. A probe on the Office host is not evidence for a different worker
identity, working directory or environment. Office pre-claim gating remains a separate
integration step; merely installing this endpoint does not enable it.

The preview assignment digest includes the predecessor handoff assembled by the same native helper used at claim. If that handoff changes between preview and claim, Office must reject the mismatch and refresh; it must not ignore the digest check. The handoff content itself is not exposed by the preview.
