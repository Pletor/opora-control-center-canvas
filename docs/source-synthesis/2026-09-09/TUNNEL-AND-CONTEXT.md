# Kontrakt uzlu, kontextu, supervizora a terminálu

Datum 2026-09-09. **NÁVRH — rozhraní níže dosud nejsou implementována.** Nadřazený produktový dokument: `EDITOR-SPEC.md`.

## 1. Co tunel znamená

`Node → WorkUnitRevision → ContextBundle → ApprovalGrant → RunBinding → TerminalSession → Evidence`.

Uzel je trvalé místo ve stromu. WorkUnit je jeden konkrétní změnový řez. Bundle je obsah. Grant je oprávnění. Binding je nezaměnitelná korelace. Session je skutečná relace CLI, pokud ji adapter umí prokázat. Evidence je návrat do modelu projektu — nikoli automatické přepsání autoritativního lifecycle.

Přenosné zdrojové kontrakty: P013 ř. 773–812 (scope není sandbox), P023 ř. 3366–3384 (runtime autorita), P025 ř. 4445–4495 (stav a cursory), P026 ř. 5064–5100 (stdio), P027 ř. 5426–5583 (druhy důkazu a limity).[1]

## 2. Tři oddělené roviny

1. **Sémantická rovina:** editor, goaly, model projektu, podklady a paměť. Zde člověk a LLM připravují práci.
2. **Řídicí rovina:** politiky, explicitní schválení, scope binding, úzké commands a status. Zde se rozhoduje, co se smí stát.
3. **Vykonávací rovina:** podporovaný LLM CLI proces v konkrétním workspace a jeho nástroje. Zde vzniká kód.

MCP není obecný shell. Kontextový MCP server nabízí úzké read operations a předání návrhů; start/decision/stop se autorizují samostatně. Zákaz obecných `execute`, libovolných URL nebo shell příkazů platí pro control API, nikoli pro skutečnou práci coding CLI uvnitř schváleného workspace.

VS Code extension není podmínka prvního řezu. První adapter může využít standardní MCP konfiguraci podporovaného CLI a lokální launcher. Extension lze přidat pro pohodlí až po prokázaném end-to-end kontraktu; nevkládat instrukce do náhodného aktivního terminálu přes simulovanou klávesnici.

## 3. Návrh identit a rozhraní

### Scope binding

```text
project_id + node_id + work_unit_id + work_unit_revision
semantic_revision + spec_digest + policy_digest + bundle_digest
workspace_id + base_sha + allowed_path_set
supervisor_binding_id + run_owner + adapter_id
correlation_id + execution_epoch + lease_id
```

Model nesmí sám určovat `actor`, runtime `run_id`, skutečnou session identitu, sekvenci nebo potvrzení execution. Tyto údaje dodá a ověří příslušná autorita.

`semantic_revision` se odděluje od `layout_revision`: pouhé posunutí kartičky neruší bundle. Změna goalu, scope, DoD, povinného podkladu, závislosti nebo zděděné politiky ho označí jako neaktuální. Běžící run zůstane dohledatelný proti starému snapshotu; nesmí dostat nový význam potichu.

### Návrhový seznam operací (ne existující API)

| Surface | Operace | Podmínka |
|---|---|---|
| context read | get_manifest, read_resource, get_dependencies | schválený project/scope + resource revision; stránkování a limity |
| editor proposal | propose_spec_change, propose_checkpoint, request_context | návrh proti expected revision; nezakládá přijetí |
| run control | create_run, get_run, get_events, decide, request_stop | oprávnění a přesný RunBinding; RunOwner potvrzuje účinek |
| editor-only authority | approve_bundle, approve_run, accept_proposal | autentizovaný actor; nikdy text z modelu |
| memory | retrieve, propose_lesson, approve_lesson | retrieval není write; přijetí vyžaduje policy a evidence |

Finální názvy, schema a tool inventory musí projít implementačním capability testem. Historický počet pěti tools se nepřenáší jako věčný produktový limit; přenáší se princip minimálních explicitních oprávnění.[1]

## 4. Context compiler

### Povinné části balíčku

1. Podstata projektu a příslušné zděděné invariants.
2. Přesný aktivní WorkUnit: výsledek, non-goals, allowed paths, DoD, test commands z důvěryhodného kontraktu.
3. NodeSpec a přímá vstupní/výstupní rozhraní; schválené závislosti a jejich revize.
4. Relevantní podklady a paměť se zdrojem, hash/revision, scope, citlivostí a stavem aktuálnosti.
5. Git base SHA, workspace identity, aktuální checkpoint pro navázání.
6. Workflow/routing/execution policy a limity; předepsaný tvar návratu.
7. Manifest zahrnutých, vynechaných a chybějících zdrojů s důvodem, odhadem/měřením tokenů a vazbou na parser/model capability.

### Algoritmus

- Vyhodnotit oprávnění **před** retrieval i před otevřením původního resource. Hrana grafu sama přístup neuděluje.
- Načíst povinné zdroje z konkrétních revizí. Přenést všechny platné kritické invariants; souhrn je nesmí sám přepsat.
- Kandidáty paměti/retrieval zmrazit do seznamu identit a revizí. Vyhledávání může být přibližné; deterministický je compiler nad tímto konkrétním snapshotem, ne příslib stejného výsledku libovolného budoucího vector search.
- Deduplikovat podle originálního evidence/resource ID a dependency group. Stejná událost shrnutá třemi agenty není trojí důkaz.
- Řadit povinné podklady, přesná rozhraní a relevantní lessons podle verzované policy; tie-break stabilním ID.
- Volit L0 → L1 → L2 podle potřeby a budgetu. L0/L1 jsou odvozeniny; současné OpenViking dokumenty popisují také coverage a pending changes, které je třeba respektovat.[18]
- Pokud se povinný kontext nevejde nebo chybí kritický zdroj, vrátit `BLOCKED_CONTEXT`, konkrétní důvod a možnosti; nikdy ho potichu zkrátit a tvářit se READY.
- Hashovat kanonický obsah a binding manifest. Transportní timestamp a náhodné request ID nejsou součástí identity obsahu. Autorizace/expirace jsou kontrolovány zvlášť a neztrácejí se kvůli idempotenci.
- Výsledný immutable bundle dostane čitelný preview. `read_resource` smí v existujícím grantu doručit jen resource/revision/hash už uvedený v jeho schváleném manifestu; kontrola přístupu se opakuje při doručení a událost se audituje. Tím se bundle nemění.
- Nový resource nebo změna obsahu mimo tento manifest zůstává pouze návrhem. Po rozšíření dependency/context plánu se znovu ověří celý výsledný scope, citlivost a budget. **Změněný ContextBundle se do běžícího runu nepředá bez nového ApprovalGrant a nového immutable RunBinding s novým bundle_digest a execution_epoch.** Staré záznamy zůstanou zachované.
- Převázání na stejnou session je možné pouze v ověřeném čekajícím checkpointu, pokud adapter prokáže rebind a převzetí přesné nové revize; jinak se starý běh nejprve prokazatelně zastaví a nový se spustí samostatně. Žádost o context nikdy sama nerozšiřuje write scope ani nenahrazuje schválení.

### Multimodální vstupy

Screenshot, diagram nebo dokument má originál, hash, povolený projekt a bezpečný preview. Text vytěžený OCR/VLM zůstává odvozený a případné instrukce uvnitř obrázku jsou nedůvěryhodná data. Vybraný model musí mít prokazatelnou schopnost přílohu přečíst; jinak dostane označenou textovou projekci nebo je explicitně vyžádána jiná surface. Žádné vymyšlené „model viděl screenshot“.

Soukromé podklady se neposílají do externí inference ani embedding služby bez příslušné zvolené datové politiky. Import nedovoluje libovolné filesystem čtení; traversal, junction, symlink/hardlink race a čtení mimo spravované hranice vyžadují skutečné enforcement testy, ne jen string prefix.

## 5. Supervizoři a souběh

- Supervisor binding patří projektu a uzlu. Scope dítěte nemůže překročit rodičovský grant; effective permissions jsou průnik, ne sjednocení přes vazby.
- Jeden writer na konkrétní workspace a přidělené cesty. Souběh je možný až v disjunktních workspaces/scopes; leases a fencing epoch zabraňují pozdnímu zápisu původního vlastníka.
- Worktree odděluje větev a pracovní soubory, **není OS sandbox**. LLM CLI s běžným uživatelským filesystem oprávněním může mít širší reálná práva než povolené cesty v promptu.[1]
- Vyžadují se dvě zřetelné hodnoty: `declared_scope` a `enforcement_level`. Obecný attached CLI bez prokázané izolace se nesmí zobrazovat jako bezpečně izolovaný ani dostat unattended produkční režim.
- Na jeden aktivní grant nejvýše jeden aktivní execution binding. Další role mohou nezávisle read-only kritizovat; nemají současně writer oprávnění.
- Rodičovský supervizor dostává kompaktní checkpoint a změněná rozhraní, nikoli celou konverzaci všech potomků.
- Člověk může předem schválit malý workflow včetně několika kroků. Není nutný nový klik pro každé deterministické pokračování uvnitř přesného scope a budgetu. Změna cíle, oprávnění nebo hranic vyžaduje nové schválení.

## 6. Deterministické gates a stav

Editorová příprava:

```text
DRAFT → VALIDATED → APPROVED_BUNDLE
              ↘ BLOCKED_CONTEXT / NEEDS_DECISION
```

Run lifecycle vlastní zvolený runtime. Normalizovaná projekce musí rozlišovat přinejmenším:

```text
PENDING → STARTING → RUNNING → WAITING_FOR_REVIEW
                       ↘ STOP_REQUESTED → STOPPED (jen s důkazem)
                       ↘ FAILED / BLOCKED / UNKNOWN
WAITING_FOR_REVIEW → autorizované pokračování NEBO terminální výsledek
```

Žádný přechod nevzniká pouhým volným textem modelu. Terminální běh se neoživuje pozdní událostí. Zvlášť se rozlišují `decision_issued`, `decision_delivered` a ověřený účinek — doručení není dokončení.

Pořadí start gate:

1. identita actoru a projektové oprávnění;
2. aktuální WorkUnit/spec/policy snapshot a splněné preconditions;
3. validní bundle a explicitní run grant;
4. workspace/revision/scope kontrola a lease;
5. prokázané capability adapteru, budget a timeouty;
6. atomický záznam start intent / idempotency key;
7. adapter start, skutečná identita a následné read-back potvrzení.

Lost acknowledgement po startu znamená `DELIVERY_UNCERTAIN`: nejprve query/reconcile přes idempotency key a RunOwner. Nesmí následovat slepé opakované spuštění. Nelze-li zjistit výsledek, UI řekne UNKNOWN a další start blokuje.

## 7. STOP, disconnect a restart

- STOP je ihned dostupný autorizovanému člověku a bezpečnostnímu gate; nesmí čekat na model nebo vyčerpaný rozpočet. Nepožaduje schválení kritika.
- Managed process lze označit STOPPED jen po ověření ukončení příslušného procesního stromu nebo prokazatelného terminálního stavu runtime.
- U ručně připojené session bez stop capability znamená klik jen požadavek. OporaCC nesmí tvrdit, že vypnul cizí terminál; zobrazí neověřený stav a ruční postup.
- Disconnect není úspěšný stop. Vypršení grantu revokuje další control capability; bez skutečného process enforcementu nemůže samo zastavit již běžící libovolný kód.
- Při restartu se načte stav RunOwner, ověří session/workspace/epoch a dohraje audit od potvrzeného cursoru. Poškozený pointer nesmí vytvořit nový běh.
- Stale packet, jiná větev, nejasný vlastník, neplatný lease nebo nedostupná autorita znamená reconcile conflict. Obnova není automatické CONTINUE.
- Inbox je deduplikovaný a restart-safe. Notifikace nesmějí samy spouštět model, coding ani rozhodnutí.

## 8. Rozpočet a routing

Kritéria volby: typ úlohy, požadované tools/vision/context, riziko, izolace, známá kvalita, časový a cenový limit. Deterministické úlohy řeší nástroj bez LLM. Preferovaný model je konfigurace, ne napevno zapsaná identita ve významovém modelu projektu.

Žádná tvrzení „90 % úspory“ se nepřebírají z vloženého článku jako výsledek tohoto produktu; P048 je inspirace, nikoli benchmark OporaCC.[1] Automatické rozsáhlé ablation kampaně nejsou potřebným prvním krokem.

Supervisor, writer, kritik, retrieval/embedding a souhrny mají oddělené usage buckets. `measured`, `estimated` a `unknown` nejsou zaměnitelné; neznámá cena se nezobrazuje jako nula. Pokud adapter neumí billing hard cap, nelze garantovat finanční limit jen časovačem. Unattended režim potřebuje doloženou limitovací capability nebo zůstane zablokovaný. Idle a timeout nevyvolávají automatické nové placené probuzení.

## 9. Evidence a učení

Evidence třídy: `SPEC`, `FIXTURE`, `CONTRACT_TEST`, `TRANSPORT_INTEGRATION`, `REAL_WORKER`, `HUMAN_OBSERVED`. Fixture není předstíraný reálný worker. P027 výslovně vyžaduje jejich rozlišení.[1]

Pro claims „změna funguje“ je nutná vazba na přesný commit/diff/artefakt, skutečný test command a exit status, prostředí a review rozsah. Review před dalšími změnami není automaticky review finálního commitu. WorkUnit DONE vyhodnotí deklarovaná lifecycle autorita nad požadovanou evidence, ne věta ve zprávě.

Učení:

```text
Observed failure/result → EvidenceRecord → LessonCandidate
→ reproduction / review → accepted LessonRevision
→ retrieved for compatible scope → monitored outcome
→ superseded / invalidated when conditions change
```

Raw source, modelová interpretace a ověřená lesson jsou oddělené. U každé lesson: root evidence IDs, source revision, platné prostředí, rozsah, preconditions, doporučený regresní test, reviewer a důvod supersession. Chybějící výsledek neznamená selhání; více souhrnů neznamená více potvrzení.

## 10. Povinné negativní testy před release tunelu

- Jiný node/project/workspace/run, podvržený actor, starý epoch a revize.
- Dvojí submit, ztracené acknowledgement, event replay a dvojí doručení checkpointu.
- STOP versus start/continue/pozdní výsledek, disconnect během write, restart v pending decision.
- Nepovolené tools, generický shell/HTTP vstup, secret v chybě/logu/contextu.
- Traversal a Windows link/reparse replacement; deklarovaný versus reálně vynucený scope.
- Změna nadřazeného omezení během runu; změna layoutu nesmí zneplatnit obsah.
- Budget exhaustion, neznámá cena, nekompatibilní multimodální vstup, chybějící povinný zdroj.
- Dva skutečné omezené workery ve dvou worktrees až po single-worker důkazu; stejné cesty musí konflikt bezpečně odmítnout.

Tohle je seznam akceptací pro budoucí implementaci, nikoli seznam dnes úspěšně provedených testů.

## Sources

[1] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/prompt-opora-control-center.md — Prompty
[18] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/03.Agents-tools/OpenViking/docs/en/concepts/03-context-layers.md — OpenViking/docs/en/concepts/03-context-layers.md
