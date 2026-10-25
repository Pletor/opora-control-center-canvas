# Měření použití nástrojů Harness

## Paired evaluation evidence

Read accepted result metadata through `GET /api/oporahub/harness-paired-evaluations`
with required `project` and `workspace`, optional `nodeId`, `resource` (baseline or
candidate ID), `problem` (the descriptive target problem), and `limit` (1–100,
default 20 newest paired receipts). Resource/problem filters apply after selecting
the receipt window and reconciling conflicting identities; they do not search all
history. `receiptWindowLimited`, `invalidReceipts`, and `conflictingEvaluations`
expose omitted or unusable evidence. An empty result does not prove no failures.

Each `evaluations[]` item returns `sourceReceipt` and the validated report without
duplicated invocation metadata. Identical replays count once per execution/evaluation
ID; conflicting validated historical claims exclude both variants in the selected
window. Different evaluation IDs are not evidence of independent trials. Reads
revalidate accepted plan/content and recompute summaries, so legacy arbitrary claims
do not become usable simply because they were stored before validation existed.
No raw stdout, script content, expected output, arguments or credentials are returned.
Independent review remains available through the native exact-head review gate;
this endpoint does not project that gate or independently verify paired stdout.

With the accepted-kit integration and the Office `--evaluate-pair` adapter installed,
submit its `harness.paired-result/1` report as `result.harnessPairedEvaluation`.
Also submit the report's observations as top-level `result.harnessInvocations`.
The nested observations may be omitted to save space; when present, they must match
the linked top-level observations in trial order. Existing result size limits apply.

Validation runs inside the native result transaction after authentication and current
execution checks. It requires the exact accepted plan digest, two distinct pinned
Node scripts and all 1–8 declared cases in alternating order. Counts, coverage,
improvements, regressions and the conclusion are recomputed from linked trials.
Unknown trials retain their planned denominator. Authority or cleanup interruption
stops subsequent observations. A positive net pass difference cannot hide a regression.
Duration metadata must be finite, between zero and one hour; this is a receipt bound,
not permission to extend the adapter's launch or execution budgets.

The kit's sole problem must be `evaluation:paired-node`; the target problem stays
descriptive in the pinned plan. Experiment completion therefore does not increase
production-problem success counts. `evaluationId` is a canonical UUID: reuse with
different reconciled evidence is rejected within the same project/workspace/execution.
At most 128 previous paired receipts are inspected; exceeding this window fails closed.
Native request replay retains its existing semantics. Invalid historical claims do
not establish an evaluation identity.

This checks consistency, not independently observed stdout. Process success and
output-quality success are distinct: a successful exit may still have a reported
output mismatch. Evidence remains `worker-observed`, with independent verification,
causal contribution and promotion disabled; costs and tokens remain unknown.
No raw output, expected output or arguments belong in the report. This extension
does not promote a resource, approve a card or write verified memory on its own.
Older servers may store this field without validation; deploy the server and client
together and verify the paired validation tests before relying on this contract.

Agent-office může k závěrečnému výsledku úkolu připojit `result.harnessInvocations`.
Každá položka je pouze `observation` z příkazu `office-harness --invoke-node`;
neposílejte celý lokální receipt obsahující stdout/stderr ani argumenty příkazu.
Výsledek odešlete existujícím result helperem uvedeným v neměnném zadání.
Jedno spuštění nástroje samo neukončuje úkol.

Canvas validuje metadata ve stejné transakci jako nativní result receipt, po
ověření identity a platnosti běhu. Není potřeba další databáze nebo zapisovací API.
Výsledky bez `harnessInvocations` zůstávají kompatibilní. Rozšíření vyžaduje
context protocol v2 a přijatý `harness.kit/1` v cílovém dokumentu zadání.
Samotná instalace tohoto modulu nevytváří ani nepřijímá kit: jeho vydání zajišťuje
samostatná integrace přijaté výbavy.

## Kontrakt

Nejvýše 32 pozorování na výsledek; celkový nativní limit výsledku 64 000 bajtů platí
i nadále. Položka `harness.invocation-metadata/1` obsahuje přesně:

- `invocationId`: kanonické UUID stejné i při opakovaném doručení.
- `execution`: executionId, epoch, project, workspace, nodeId, acceptedRevision,
  assignmentDigest; vše musí odpovídat neměnnému běhu.
- `resource`: id a SHA-256 digest přesného UTF-8 skriptu z přijaté výbavy.
- `adapter: node-readonly/1`, `nodeVersion`, `exitCode`, `reason`, `durationMs`,
  `outputBytes`, `outcome`, `authorityCurrentAtCompletion`, `cleanupComplete`.
- `evidence: worker-observed`, `independentlyVerified: false`,
  `causalContribution: false`, `promotionAllowed: false`, `tokens: null`, `cost: null`.

Skript musí být jednoznačný a vyžadovat přesně `command:node`. Neznámá pole se
odmítají. Trvání je konečné číslo 0–60 000 ms; výstup má celočíselnou délku
0–1 GiB. `pass` vyžaduje completed, exitCode 0, platnou autoritu při dokončení
a úspěšný úklid; ostatní případy jsou `fail`. Hodnoty hlásí worker: kontrola
kontraktu a digestu sama nedokazuje skutečné spuštění procesu.

Stejné invocationId se započítá pouze jednou v rámci běhu. Rozdílná metadata
pod stejným ID se odmítnou. Kontrola prochází nejvýše 128 předchozích receiptů
s tímto rozšířením; překročení limitu další pozorování odmítne. Nativní replay
stejného requestId zůstává beze změny. Historická nevalidní data nejsou důkaz.

## Čtení zkušeností

`GET /api/oporahub/harness-invocations?project=…&workspace=…` vrací
`harness.invocations/1`. Volitelné filtry: `nodeId`, `resource`, `limit` (1–100,
výchozí 50 nejnovějších receiptů). Filtr resource se uplatňuje uvnitř tohoto okna.

Kohorta odděluje resource, digest, adapter, verzi Node a problém z přijatého kitu.
Obsahuje počet spuštění, pass/fail a procento, průměrné trvání, počet bajtů výstupu,
počet různých běhů a karet a odkaz `latestSourceReceipt`. Odpověď nevrací výstup
skriptu, argumenty ani přístupové tokeny. Počet kohort je omezen na 100.
`receiptWindowLimited` a `cohortsLimited` přiznávají oříznutí; `invalidReceipts`
a `conflictingInvocations` uvádějí vyřazené podklady. Konfliktní historické
pozorování se nezapočte ani v jedné variantě.

Jde o **worker-reported** měření v omezeném okně, nikoli celoživotní úspěšnost
nebo nezávislé pokusy. `serverObserved`, `independentlyVerified`,
`causalContribution` a `promotionAllowed` jsou false. Náklady a tokeny zůstávají
neznámé. Tento signál nepovyšuje položku knihovny, neuzavírá kartu a nenahrazuje
testy, lidské review nebo produkční pozorování. Úspěšnost přijatých úkolů je
samostatný signál; samotné exitCode 0 není úspěchem celého úkolu.

Jmenovatel procenta tvoří pouze platná, odeslaná a deduplikovaná pozorování
v daném okně. Neodeslané pokusy jsou nepozorované: například po pádu workera
nebo zániku lease již výsledek nemusí projít nativní kontrolou běhu. Ani 100 %
tedy nedokazuje spolehlivost všech spuštění. Počet chybějících pozorování není
známý; chybějící receipt se nezapočítává jako úspěch ani jako neúspěch. Tyto
limity se neřeší obcházením kontroly platné lease.

Nasazení zahrnuje server i klienta. Před použitím nové projekce ověřte dostupnost
tohoto GET endpointu: starší Canvas mohl neznámá result pole pouze uložit bez
validace. Zpětné čtení je vždy znovu validuje vůči přijatému zadání.
## Accepted kit v2 compatibility

Native invocation ingestion, paired-plan validation and historical readback accept
kit v2 only when the full accepted-kit validator is installed. Missing or older
validators reject v2; selection metadata is never stripped to bypass validation.
The existing v1 consumer checks remain unchanged. Install the accepted-kit module
with this module and restart the server before enabling v2 writers.

Validation preserves the accepted snapshot and checks exact ordered resource and
configuration digests. Selection origins remain caller-declared claims, not
independent proof of tool benefit. Worker observations and paired fixture results
retain their existing evidence class and cannot promote tools by themselves.

## Documentation read evidence

A compatible Office returns `observation` from `--docs-accepted`. Include only this
object in `result.harnessDocumentation` (maximum 32) when reporting the actual task
result. Keep its `readId` unchanged on retries. Do not report a completed task just
because documentation was fetched. This extension is separate from Node invocations.

Native validation binds every observation to the exact current accepted target,
resource/content digest, `harness.context7/1` descriptor and resolved library ID.
The registered result validator rejects extra fields, raw queries/text/credentials,
invalid timing/digests, duplicate IDs and reuse of an ID with changed metadata.
Native result receipts persist it in their existing transaction; there is no second
queue or database. Missing extension support in older deployments does not prove
validation or measurement, even if an older endpoint accepts unknown JSON fields.

GET `/api/oporahub/harness-documentation?project=PROJECT&workspace=WORKSPACE` returns
a bounded newest-receipt projection. Optional `nodeId`, `resource` and `limit=1..100`
filter it. Results deduplicate identical reads, exclude conflicts and invalid old
receipts, and return at most 100 observations with source receipt IDs and explicit
window/truncation flags. Questions, document text and unrelated result fields are
never projected. Receipt-window limits mean this is not an all-time count.

Evidence remains `worker-reported`: agents can fabricate metadata and native storage
does not independently attest the external request. Coverage includes submitted
successful reads only; missing/failed reads are unobserved. There is deliberately no
success percentage, causal contribution, promotion or production benefit claim.
Fetching a reference is not proof that following it solved the accepted task.
