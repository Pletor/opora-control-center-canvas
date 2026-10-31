# Kroky plánu (`spec.steps`)

Kroky plánu jsou verzované pole přijatého zadání karty. Leží v `fields` zadání vedle `goal`,
`non_goals` a `acceptance`, takže se mění jen návrhem změny zadání (changeset) a přijetím člověkem.
Průběh práce (které kroky jsou hotové) do zadání nepatří; nese ho výsledek běhu (`stepResults`)
a průběžná hlášení kroků (`POST /executions/{id}/steps`).

## Tvar a validace

```json
"steps": [
  {"id": "s1", "order": 1, "title": "Datový model", "acceptance": ["migrace projde"], "dependsOn": []},
  {"id": "s2", "order": 2, "title": "API", "acceptance": ["test API zelený"], "dependsOn": ["s1"],
   "kind": "code", "files": ["backend/**/*.py"]}
]
```

| Pole | Pravidlo |
|---|---|
| `id` | 1–40 znaků `A-Z a-z 0-9 _ -`, jedinečné v kartě |
| `order` | celé číslo 1–10000, jedinečné; větší než `order` všech závislostí |
| `title` | neprázdný text do 200 znaků |
| `acceptance` | 1–20 neprázdných podmínek do 1000 znaků |
| `dependsOn` | ID existujících kroků karty, bez sebe sama; závislosti tvoří acyklický graf |
| `kind` | volitelně `code`, `test`, `docs`, `design`, `research` |
| `files` | volitelně nejvýše 50 globů do 300 znaků |

Nejvýše 50 kroků. Pole `steps` je nepovinné: starší zadání bez něj zůstávají platná a čtou se jako
plán bez kroků. Validaci dělá `backend/canvas/opora_plan_steps.py` (`validate_steps`) a volá ji
`validate_payload` zadání, takže platí pro uložení pracovního zadání, návrh, přijetí, obnovu verze
i SQL kontext.

## Návrh, přijetí a převod

Kroky se mění stejně jako ostatní pole zadání: `POST /api/oporahub/changesets` s úplnými `fields`
(včetně `steps`), přijetí člověkem, výslovný `rebase`. Automatický převod zastaralého návrhu
([auto-rebase](oporahub-auto-rebase.md)) rozhoduje `steps` po jednotlivých krocích podle ID
pravidlem `merge_field` dokázaným v Leanu: změna jiného kroku, než který změnila přijatá linie, se
sloučí; změna téhož kroku na obou stranách je konflikt `spec:<karta>:steps:<krok>`. Když jsou obě
strany platné, ale sloučený plán ne (například závislost na kroku, který druhá strana odebrala),
vznikne konflikt s důvodem `steps_invalid_after_merge`.

`GET/POST /api/node-spec` vrací navíc `plan: {working, accepted, acceptedHead, workingDiffers}`:
kroky pracovního a přijatého zadání karty (`accepted` je `null`, dokud karta v přijatém zadání není).

## Neměnný snímek běhu

Převzetí běhu ukládá do snímku `assignment.steps`: přijaté kroky převzaté karty seřazené podle
`order` (u kontextu v2 po redakci jako ostatní snímek). Kontext v2 nese kroky i v zadání karet
SQL projekce. Snímek se po převzetí nemění; změna kroků vyžaduje nový běh.

## Výsledky kroků (`stepResults`)

Výsledek běhu může nést:

```json
"stepResults": [{"stepId": "s1", "status": "done", "evidence": {"notes": "…", "checks": ["pytest"], "commits": ["abc1234"]}}]
```

`stepId` musí patřit ke krokům ve snímku běhu a opakovat se nesmí; `status` je `done`, `failed`
nebo `skipped`; `evidence.notes` je povinný text do 4000 znaků, `checks` nejvýše 50 textů,
`commits` nejvýše 50 SHA (7–40 hex). Výsledky se ukládají v potvrzení výsledku běhu, takže jsou
idempotentní podle `requestId` (stejný obsah vrací stejné potvrzení, jiný obsah se odmítne).

Čtený model karty `{total, done, current}` (`backend/canvas/opora_step_results.py`) se skládá
ze **všech běhů** karty, ne jen z posledního. Hlášení kroku platí, jen pokud se definice kroku ve
snímku běhu rovná aktuálně přijaté definici (změněný krok začíná znovu). Krok, který některý běh
nahlásil `done`, zůstává hotový i když pozdější běh tentýž krok nahlásí `failed` nebo `skipped`;
krok bez `done` nese nejnovější platné hlášení. `current` je první nehotový krok v topologickém
pořadí, `null` když je vše hotové nebo karta kroky nemá. Process-sync a agent-state k tomu vydávají
seznam po krocích `[{id, status, executionId}]` (`stepItems`, resp. `cards[].steps.items`;
`status` = `done`/`failed`/`skipped`/`current`/`waiting`, `executionId` = běh, jehož hlášení platí).

## Průběžné hlášení kroku (`POST /executions/{id}/steps`)

Běžící běh smí ohlásit krok hned, jak ho dokončí, ještě před výsledkem:

```json
{"project": "P", "workspace": "W", "token": "…", "epoch": 3, "requestId": "step-s1-done",
 "stepId": "s1", "status": "done", "evidence": {"notes": "…", "checks": ["pytest"], "commits": ["abc1234"]}}
```

Oprávnění je stejné jako u výsledku (token, epocha, platný pronájem, nezměněné zadání, rozpočet);
`stepId`, `status` a `evidence` se validují stejně jako položka `stepResults`. Hlášení se ukládá do
`opora_execution_steps` (aditivní tabulka projektu) idempotentně podle `requestId`: stejný obsah
vrátí stejné potvrzení i po vypršení pronájmu, jiný obsah se odmítne (409). Hlášení je tvrzení agenta
(`verification: agent-reported`), kartu nemění.

Čtený model výše počítá průběžná hlášení stejně jako `stepResults` (výsledek běhu je novější než
jeho průběžná hlášení). Když agent spadne po dvou ze čtyř kroků, agent-state ukazuje 2/4,
`current` je třetí krok a nový běh karty začne jím: `step.started` při převzetí i `progress`
v `GET /executions/{id}/assignment` (`{total, done, current, steps: [{id, status, executionId}]}`,
živé, mimo neměnný snímek a jeho otisk). Výsledek pak smí kroky už ohlášené vynechat.

Události (tok [událostí](oporahub-events.md)): převzetí emituje `step.started` pro první nehotový
krok. Průběžné hlášení emituje `step.done` / `step.failed` (s `data.checkpoint: true`) a po `done`
`step.started` dalšího nehotového kroku. Výsledek emituje `step.done` / `step.failed` pro hlášené
kroky, které běh ještě neohlásil průběžně se stejným stavem (vše v transakci zápisu).

Brána merge ukazuje doklady po krocích (stav, kontroly, commity, poznámka a kroky bez dokladu)
v `evidence.steps`, viz [Doklady kroků](oporahub-review-jobs.md#doklady-kroků-evidencesteps).

## Připravenost k převzetí

Karta je připravená (`process-sync` stav `ready`, akce `claim` v agent-state), když má přijaté
zadání s alespoň jedním krokem, rozpočet ji připouští a nemá `blockedBy` (nedokončené předchůdce
v [grafu karet](oporahub-agent-state.md#graf-karet-dag)). Bez kroků je stav `needs-steps`.
Desktop-v3 `stages` (stará pipeline) se jen zobrazují v `pipeline`, nikdy neblokují.

Totéž vynucuje endpoint `POST /api/oporahub/executions/claim`: odmítne `409` s kódem
`plan_steps_missing` (přijaté zadání karty nemá kroky) nebo `blocked_by_predecessor`.

## Jediná definice hotovo

`card_done_state(card) -> {done, missing}` (`backend/canvas/opora_card_done.py`) je čistá funkce.
Hotovo = všechny kroky `done` (alespoň jeden) + přijetí karty doložené během nad aktuálním přijatým
zadáním (`card_acceptance`) + brána review `ready` (`gate_ready`) + PR `merged` + plán zapsán zpět
(`plan_written_back`) + každá cesta zákazníka, na které karta leží, ověřená prošlým čerstvým dokladem
(`journeys`, `docs/brana-cesty.md` §5) + uzavření karty (`human_close`, název požadavku zůstává). `missing` vypisuje chybějící části
v tomto pořadí. Agent-state ji vydává u každé karty jako `cards[].dod`: boolean pod jménem každého
požadavku (`steps`, `card_acceptance`, `gate_ready`, `merged`, `plan_written_back`, `journeys`, `human_close`),
druh brány `gate` (`review` / `external` / `local`), `done`, `missing` a při nesplněné bráně cesty `blockingJourneys`. Detail karty kreslí dílky z něj.

- **Uzavření karty je deterministické** (rozhodnutí člověka 2026-10-31): jakmile jsou splněné všechny ostatní
  požadavky definice hotovo (`steps`, `card_acceptance`, `gate_ready`, `merged`, `plan_written_back`, `journeys`),
  server kartu uzavře sám (`done.confirmed`, `by: "opora"`) při zápisu plánu zpět / přepočtu stavu karty.
  Člověk nic nepotvrzuje; ruční uzavření v UI zůstává jako možnost, ne podmínka. Přepočet dělá smyčka vazeb PR
  (`opora_execution_pr_manager`, krok `opora_card_auto_close`) u každé sloučené vazby se značkou
  `awaitingHumanClose` a odevzdání `deliver`; zápis jde interní cestou stavu (`save_node` → `closure_gate`, bez
  HTTP), je idempotentní a v záznamu činnosti nese `agent: "opora"` s `nodeIds` karty. Bez modelu, bez agenta.
  `human_close` tak nikdy nezůstane jediným chybějícím požadavkem déle než do dalšího kroku smyčky.
- Akce `close_card` v agent-state je `blocked/server_closes`, když chybí jen `human_close` (server ji uzavře sám,
  žádné rozhodnutí pro člověka); jinak `blocked/done_state_incomplete` s `preconditions.missing`.
- Ruční potvrzení `done.confirmed` karty s přijatými kroky projde jen při splnění všeho kromě
  `human_close`; starší brána uzavření (doložené testy, `checks_passed`, hotová pipeline, scénář)
  pro takovou kartu neplatí. Karty bez kroků se dál uzavírají po staru a stará data zůstávají čitelná.
- `gate_ready` má dva režimy a výstup je nese v poli `gate`: se zapnutými úlohami review
  (`OPORA_REVIEW_JOBS`) je to `"review"` a platí jen brána OporaHubu `ready` (čte se pro všechny
  vazby PR, i sloučené); s vypnutými úlohami review je to `"external"` a branou je ochrana větve
  na GitHubu, takže `gate_ready` = PR je sloučený. Akce `close_card` nese `preconditions.gate`.
- U **sloučené** vazby v režimu `review` se nepočítá svěžest hlavy vůči main z fronty merge
  (`base_freshness_unobserved`, `stale_against_main`): pozorování základu běží jen nad otevřenými PR, po sloučení
  zamrzne a stárne, a main po sloučení vždy obsahuje commit sloučení. Brána sloučené vazby, kterou drží jen tyto dva
  důvody, je pro `gate_ready` `ready`. Totéž platí pro `human_approvals_missing` a `github_evidence_missing`
  (rozhodnutí 2026-10-31: u sloučeného PR je předslučovací podmínka schválení bezpředmětná; konfigurace schválení
  před sloučením platí dál). Od 2026-10-31 večer („zavři to a jdi dál“) platí obecně: u sloučené vazby je
  **každá čekající** brána (`pending`, např. `security_review_in_progress`, `review_not_enqueued`,
  `self_checks_missing`) pro `gate_ready` `ready`. Sloučení rozhodlo a review, které doběhne až po něm, už kartu
  nedrží. Blokující brána (`blocked`: otevřený důležitý nález, selhané kontroly) drží kartu dál i po sloučení.
- Třetí režim `"local"` má projekt bez vazby na GitHub ([lokální sloučení](lokalni-slouceni.md)): `merged`
  a `plan_written_back` vznikají z `POST /api/oporahub/executions/{executionId}/local-merge` a `gate_ready` =
  sloučeno + poslední běh kontrol karty na sloučeném commitu je zelený (karta bez kontrol: jen sloučeno).

### Kroky přidané po sloučení

Rozhodnutí člověka 2026-10-31 (Ample #22, „verze B“): krok plánu nebo akceptace karty přidaná do přijatého zadání
**až po sloučení** PR nemůže mít hlášení žádného běhu, protože ji sloučený běh nikdy neměl v zadání. Taková karta by
jinak zůstala otevřená navždy. Platí jen pro kartu, jejíž započítaná vazba (`link_for`) je `merged`:

- Přijatý krok, který sloučený běh (`executionId` vazby) neměl připnutý ve svém zadání (chybí, nebo má jinou definici)
  a nemá žádné platné hlášení (`reports`), je splněný sloučením: stav kroku `after_merge` (ne `done`), doklad =
  `mergeSha` + číslo PR. Krok, který sloučený běh připnutý **měl** a nenahlásil nebo nahlásil `failed`, drží
  kartu dál přesně jako dřív.
- `card_acceptance` bez dokladu proti aktuálnímu zadání je splněná sloučením, když se přijaté zadání karty liší
  od dokumentu, který sloučený běh připnul, a žádný novější běh než sloučený nic nenahlásil (nový běh = karta je
  zase ve standardním procesu).
- Výstup `card_done_state` (a `cards[].dod`) nese při splnění touto cestou `afterMerge: [požadavek, …]` (např.
  `["steps", "card_acceptance"]`) a `afterMergeEvidence: {executionId, number, mergeSha, steps: [{id, title}]}`;
  `cards[].steps.items` mají u takových kroků `status: "after_merge"`. Pořadí `missing` ani význam `closable` se
  nemění, takže server takovou kartu uzavře sám (`opora_card_auto_close`). U nesloučené vazby se nic nepovoluje.
- Dohledatelnost: poznámka uzavření (`done.note`) a stopa práce karty (`GET /api/oporahub/card-trail`, pole
  `afterMerge`) nesou větu „Kroky přibyly po sloučení PR #N (sha) – uznány sloučením, mimo standardní proces“ se
  seznamem kroků, aby šlo pozdější problém dohledat k místu vzniku.
- UI to nikdy neukáže jako zelené „hotovo“: krok má jantarový štítek „po sloučení“ a karta jednořádkové upozornění
  „Mimo standardní proces: kroky přibyly po sloučení PR #N“ (definice hotovo v detailu karty, záložka Kroky,
  panel karty / bloku).

## Migrace

```
uv run python -m backend.canvas.opora_plan_steps_migration --data <data> --project <p> --workspace <w> [--apply]
```

Bez `--apply` jen vypíše plán (nic nezapisuje). Pro každou kartu bez kroků (v pracovním i přijatém
zadání) složí z podmínek bloků (podle čísla bloku), ze starých `steps` a `criteria` lineární
kroky (`s1` → `s2` → …; kritéria karty doplní podmínky posledního kroku) a s `--apply` založí jeden
**návrh** změny zadání na kartu (autor `orchestrator`). Návrh se nikdy nepřijímá automaticky;
vyžaduje přijaté výchozí zadání.

## Omezení

- Spuštěné běhy založené před nasazením mají jiný otisk snímku (nové pole `steps`) a při dalším
  heartbeatu se odvolají; stačí nový claim.
- Testy napsané před kroky plánu vypínají v `backend/conftest.py` povinnost kroků při claimu;
  testy kroků ji zapínají značkou `plan_steps_claim`.
