# Opora Canvas

Přijaté zadání může nést konkrétní verze nástrojů a pravidel pro agenta:
[připnutá výbava Harness](docs/harness-kit.md). Obsah se ověřuje SHA-256 a stává
se součástí neměnného zadání běhu; změny jsou viditelné při přijetí návrhu.
Výsledky běhů s výbavou se trvale promítají z outboxu do
[měření Harness](docs/harness-kit.md#měření-výsledků) se samostatnými úrovněmi důkazů.
Ověřené přiřaditelné výsledky a jejich odvolání se automaticky doručují do existující
paměti rolí OpenViking přes trvalou frontu; stav doručení je čitelný samostatně.
Přesně přiřazené incidenty a reverty z existujícího review se vracejí jako samostatné
varovné signály; nepředstírají prokázanou příčinu ani produkční úspěch bez incidentu.
Paired Harness experiments can submit `result.harnessPairedEvaluation` alongside
invocation metadata. Native validation reconciles the pinned plan, every planned
trial and regression counts before saving the receipt; output matching remains a
worker assertion. See [paired evidence](docs/harness-invocations.md#paired-evaluation-evidence).
Agents can read reconciled comparisons at `GET /api/oporahub/harness-paired-evaluations`
with exact version provenance and explicit incomplete or conflicting evidence.

Použití nástrojů Harness lze měřit přes nativní výsledky běhů:
[kontrakt a čtení zkušeností](docs/harness-invocations.md). Metadata zachovávají
vazbu na přijatý skript a rozlišují hlášení workera od nezávislého ověření.

Plátno projekt → sektor → uzel pro řízení agentů: struktura práce, zadání uzlů, podklady a běhy na jednom místě.

Změny zadání se porovnávají v kontextu konkrétní karty; nesouvisející poznámka na plátně
nezneplatňuje její výsledek. Počet rozdílů není počet přepsání zadání. Podrobnosti a
kompatibilita rozpracovaných předávek: [karta pro agenty](docs/karta-pro-agenty.md#porovnávání-zadání-bez-falešných-změn).

## Spuštění jedním příkazem

```sh
npm ci && uv sync      # jednou
uv run opora           # nebo: npm start
```

Nastavení běhu je v [opora.toml](opora.toml): port, adresář dat, sestavení frontendu, profily a integrace.
`uv run opora` sestaví frontend, když chybí nebo je starší než zdroje, spustí backend na http://127.0.0.1:8740/ a otevře prohlížeč.

- `uv run opora --profile preview` – náhled nad kopií dat (port 8790, `.data/preview`).
- `uv run opora --profile dev` – jen backend pro `npm run dev` (Vite proxuje `/api`).
- `uv run opora --check` – vypíše výslednou konfiguraci bez spuštění.
- `uv run opora --port 8791 --data .data/kopie --no-open --no-build` – jednorázové přepisy.
- `[app] embed_origins` – přesné původy, které smí Oporu zobrazit ve svém `<iframe>` (viz níže). Výchozí `[]` = rámování zakázané.
- Lokální přepisy mimo git: `opora.local.toml` se stejnou strukturou (např. `[app] data` mimo repozitář; přesun dat: `uv run python tools/move_data_root.py <starý> <nový> [--dry-run]`). Tajemství (API klíče) patří do proměnných prostředí, ne do TOML.

## Vložení do jiné lokální aplikace (`embed_origins`)

Opora se normálně nedá vložit do `<iframe>` (`X-Frame-Options: DENY`, CSP `frame-ancestors 'none'`), aby ji cizí stránka nemohla překrýt a podstrčit uživateli kliknutí (clickjacking). Chcete-li ji zobrazit ve vlastní lokální aplikaci, například v 3D kanceláři agent-office, vyjmenujte její původ v `opora.local.toml`:

```toml
[app]
embed_origins = ["http://localhost:4600"]
```

- Každá položka je přesný původ: schéma `http`/`https`, host a volitelně port. Cesta, dotaz, hvězdička ani `null` nejsou dovolené; neplatná položka zastaví start s českou hláškou (`uv run opora --check` ji ukáže hned).
- Neprázdný seznam vynechá `X-Frame-Options` a pošle `frame-ancestors 'self' <původy…>`. Ostatní CSP i hranice zůstávají: povolené Hosty, stejný Origin pro zápisy, cookie člověka `SameSite=Strict`, lease karet.
- **Bezpečnost:** nastavení uvolňuje ochranu proti clickjackingu jen pro vyjmenované původy. Uvádějte jen loopback původy (`localhost`, `127.0.0.1`) aplikací, které sami provozujete; nikdy veřejnou adresu.
- Cookie člověka je `SameSite=Strict`, takže zápisy z vložené Opory fungují jen tehdy, když je rám ze stejného webu jako rodič: z `http://localhost:4600` vkládejte `http://localhost:8740`, ne `http://127.0.0.1:8740`.
- Vložená Opora předává rodiči Escape, který sama neobsloužila (`preventDefault`): `window.parent.postMessage({ type: "opora:escape" }, <původ z document.referrer>)`. Bez referreru ani mimo rám se nic neposílá. Rodič má zprávu přijmout jen od původu Opory a sám rozhodne, co zavře. Panely Opory, které Escape zavírají bez `preventDefault`, ho předají také.

## Kde co je

- Pravidla umístění nového souboru: [docs/pravidla-struktury.md](docs/pravidla-struktury.md).
- Produktový kontrakt: [docs/PRODUCT-CONTRACT.md](docs/PRODUCT-CONTRACT.md).

## OporaHub a práce agentů

Canvas s OporaHubem drží plán, GitHub kód; agent-office je připojený vykonavatel.
V Alt+3 se otevře [OporaHub](docs/oporahub-ui.md) nad jediným dokumentem
`GET /api/oporahub/agent-state`: záložka **Přehled** (přijatá hlava, drift, riziko, nejvýše
3 rozhodnutí a smyčka deseti etap plán → kód → plán), **Karta** (otevře jednotný detail karty)
a **Pro agenty** (fronta akcí, hlavy pro CAS, kopírovatelný JSON, kontrakt `data-oh-*`).
Konkrétní položka otevře svůj detail; ✕ nebo Esc vrátí přehled. Původní formuláře jsou
v patě stránky. Přímé odkazy: `?environment=hub&ohView=agents`; detail karty `?ohCard=<nodeId>&ohTab=spec|steps|lens|run|review|history` v kterémkoli prostředí. Detail karty je jeden drawer pro celou aplikaci (dvojklik na kartu, odznak, Velín, OporaHub) se záložkami Zadání · Kroky · Lens (PR Lens: co změna dělá, [docs/cista-linie.md](docs/cista-linie.md#4-pr-lens-v-procesu-opory)) · Běh · Review & PR · Historie a definicí hotovo v hlavičce ([docs/oporahub-ui.md](docs/oporahub-ui.md#jednotný-detail-karty)). [Návrhový artefakt Claude Code](docs/design/README.md) je samostatná
klikací ukázka; aplikace používá skutečná data a stejné API jako agenti.
Editor je štíhlý ([docs/oporahub-ui.md](docs/oporahub-ui.md#editor-lean-tvář-karty-velín-a-živý-pás)): lišta
**Struktura · Velín · Text**, vzácnější Kreslení / Kancelář / Storyboard pod **⋯**, jedno **+ Přidat**
(Sektor, Uzel, Komentář, Oblast) a jedno **Srovnat** (sloupce podle vazeb, ve sloupci podle `topoIndex`).
Tvář karty ukazuje jen druh, kdo ji drží, název, jeden stavový řádek (zdraví · etapa · důvod), postup kroků
a nejvýš jednu patičku (brána / na koho čeká / rozhodnutí); okraj nese stav (tyrkysový běží s odpočtem
lease, zlatý čeká na tebe, čárkovaný blokováno). Vazby `next` z hotové karty jsou plné zelené, jinak
přerušované; vazba, která by uzavřela cyklus, se neuloží a lišta chyb vypíše cestu cyklu jmény karet.
V hlavě sektoru čip **Ke schválení: N** rozbalí návrhy uzavření od agentů a **✓ Potvrdit návrhy** je potvrdí
jedním zápisem (jen karty s hotovými důkazy bez N/A; ostatní se potvrzují na kartě).
**Velín** je projekt → vrstva → sektor → karta nad agent-state s rozhodnutími, dalšími akcemi a „Teď běží“.
Dole běží **živý pás** ze sdíleného toku `GET /api/oporahub/events/stream` (záložně polling `/events?since=`);
rozbalená **Časová osa** kreslí dráhy karet vrstvy. Detail karty se otevírá přes jediný šev
`openCardDrawer` (zatím v OporaHubu). Detail karty
ukazuje bránu review (pravidlo, které drží merge, ověření lidé, vlastní kontroly), formální důkazy
s úrovní důvěry a historii/blame. Pata OporaHubu otevírá konflikty auto-rebase, metriky review,
knihu důkazů a **Lidé v review** (jen člověk: nárok identity, řádek `Opora-Identity` k vložení na
GitHub, ověření, zrušení).

Přes **Upravit zadání karty** otevřete změny zadání, prohlédněte uložená zadání a jednou přijměte jejich
výchozí základ. Pak upravte cíl, omezení a akceptace vybrané karty v návrhu. Uložení
návrhu Canvas nemění; po prohlídce rozdílu ho může člověk výslovně přijmout do zadání.
Náhled rozlišuje přijaté, pracovní a navržené hodnoty. Přijetí není ověření kódu.

API `/api/oporahub/changesets` poskytuje kontext, neměnné návrhy a jejich přijetí;
`/api/oporahub/baselines` zakládá počáteční přijatou revizi. Zastaralá očekávání se
odmítají, agent může navrhovat, nemůže přijímat. Historické snímky uložených zadání
z `/api/oporahub/proposals` a původní Oracle dashboard zůstávají pod novým panelem.

Panel návrhů grafu vytváří nové karty, sektory, oblasti a vazby včetně prvního
plánu na prázdném plátně. Člověk před přijetím prohlédne neměnný návrh a při
prvním převzetí výslovně potvrdí základ grafu. Přijetí uloží graf i zadání v jedné
databázové transakci; agent může následně převzít přijatou kartu. Postup a omezení:
[návrhy grafu](docs/oporahub-graph-proposals.md).

Existující prvky lze upravit nebo výslovně odstranit v návrhu se zobrazením
přijatého, pracovního a navrženého stavu. Starší neprázdné plátno lze nejprve
převzít bez přidávání pomocné karty. Historie odstraněných karet a výsledků se
zachovává; nesouvisející pracovní změny se neschvalují. Postup:
[změny přijatého grafu](docs/oporahub-graph-changes.md).

Panel **Změny obsahu** na stejném přehledu otevírá přesné návrhy textů, kreseb
a konfigurace karet. Ukazuje přijatou, pracovní a navrženou hodnotu. První přijetí
vyžaduje kontrolu celého výchozího obsahu a může zneplatnit běžící úlohy založené
na revizi bez obsahového manifestu. Další návrhy mění konkrétní pole; souběh řeší
rebase s explicitními konflikty a přijetí člověkem. Postup, API a omezení:
[verzovaný obsah plánu](docs/oporahub-content-changes.md). Etapa 2b prošla závěrečným
ověřením; celý projekt OporaHub tím ještě není dokončen.

**Upgrade již používaného kontextu v2:** přidání obsahových SQL tabulek změní DDL
generaci a zneplatní dřívější sparse coverage. Historie a původní soukromé piny
zůstanou zachované, běžný kontext v1 pokračuje. V2 se automaticky neopraví ani
znovu nezařadí; tento upgrade zatím nemá API pro bezpečné obnovení coverage.
Podrobnosti: [provozní omezení](docs/oporahub-content-changes.md#upgrade-projektu-s-dřívějším-kontextem-v2).

Panel **GitHub důkazy** navíc
načítá review a kontroly přímo z GitHubu a váže je na konkrétní přijatou revizi a SHA.
Odděluje review kódu, review zadání a pozorované kontroly; neposkytuje automatické
povolení k merge. Soukromý repozitář vyžaduje token v prostředí serveru
(`OPORA_GITHUB_TOKEN`, případně `GH_TOKEN`/`GITHUB_TOKEN`). Podrobnosti a postup:
[GitHub důkazy](docs/oporahub-github.md).

**Pravidla přijetí plánů** jsou samostatný vstup na přehledu OporaHubu. U každého
návrhu zadání, přidání grafu, změny grafu nebo obsahu zobrazí review serverové
riziko, diskusi a nálezy. Člověk vypořádá blokující nález s důvodem a případně
potvrdí přesné riziko, policy a hlavu diskuse. Změna nebo rebase staré potvrzení
nepřenese. Jména agentů ani lokální session se nepočítají jako nezávislé hlasy.
Nastavení GitHub PR kontrol zůstává oddělené. [Kontrakt a API review návrhu](docs/oporahub-proposal-review.md)
popisují také legacy přijetí při neaktivní policy, doklady a bootstrap výjimku.
Etapa 3b je dokončena v rozsahu kontraktu: API, atomické přijetí a skutečný browser
ověřují přesný návrh i zneplatnění starých potvrzení. Schválený rozsah je dokončen;
volitelný izolovaný broker a podepsaná evidence spotřeby jsou implementované a
mají [skutečný provozní průchod](docs/oporahub-live-staging.md). [Audit dokončení](docs/oporahub-completion-audit.md)
mapuje všech 12 požadavků na konkrétní důkazy a meze jejich platnosti.

**Proces Control Center** propojuje přijatý plán, pipeline karty a execution
historii v jednom přehledu. U každé karty ukáže doložený stav a další krok;
výsledek starší revize se nevydává za aktuální dokončení. Agenti mají stejný
výřez přes `GET /api/oporahub/process` a odkazy v běžném `node-brief`.
Zjištění z práce se vracejí jako návrhy zlepšení do stávajícího review.
Podklady se průběžně obnovují bez spouštění modelu nebo dalšího běhu.
[Kontrakt synchronizace procesu](docs/oporahub-process-sync.md) popisuje zdroje
pravdy, API a hranice vůči starším procesům.
[Živý proces](docs/zivy-proces.md) rozšiřuje tok událostí OporaHubu o `opora.process-event/1`:
agent-office posílá své události `POST /api/oporahub/process-events` do stejného outboxu a vše
chodí jedním tokem `GET /api/oporahub/events` / SSE `/events/stream` (fáze, stav, titulek u každé
události); zdraví zdrojů ukáže `GET /api/oporahub/process-health`.
Agent místo dotazování mnoha endpointů čte jeden [stav pro agenty](docs/oporahub-agent-state.md)
(`GET /api/oporahub/agent-state`, s `ETag`): hlavy pro CAS, zdraví etap a další akce.
Změny mezi snímky nese [tok událostí](docs/oporahub-events.md) (`GET /api/oporahub/events`,
SSE `/api/oporahub/events/stream` s `Last-Event-ID`); vazby `next` mezi kartami musí tvořit DAG.
Plán karty tvoří verzované [kroky plánu](docs/oporahub-plan-steps.md) (`spec.steps`); převzít lze jen
kartu s přijatými kroky a bez nedokončených předchůdců, hotovo určuje jediná definice.
[Lens plánu](docs/plan-lens.md) (`GET /api/oporahub/plan-lens`) ukazuje plán z plátna jako graf PR Lens
(oblasti, karty, předávky a vazby v kódu z Graphify, plán proti realitě main), deterministicky a bez modelu.
[Design náhled karty](docs/design-nahled.md) drží screenshoty design karty na hlavě PR (`evidence.preview`),
lidské „Potvrdit vzhled“, režim karty `brand` / `explore` a DESIGN.md projektu z commitnuté revize
(`GET /api/oporahub/design-system`); v bráně merge je to jen doklad.
Volitelné [automatické review kódu](docs/oporahub-review-jobs.md) (trvale zapnuté přes `[app] review_jobs = true` v `opora.toml`, které přebije `OPORA_REVIEW_JOBS`) zařazuje
úlohy hledačů a ověřovatelů pro každou novou hlavu PR běhu a počítá bránu merge; pracovníci
agent-office je přebírají přes `/api/oporahub/review-jobs`. Brána navíc vyžaduje bezpečnostní review
citlivých změn (`kind: "security"`), důkaz vlastních kontrol agenta pro aktuální hlavu, hlavu postavenou
na aktuální cílové větvi (jinak `stale_against_main`) a vyplněnou [šablonu PR](.github/pull_request_template.md). [Lidé v review](docs/oporahub-review-identity.md)
doplňují ověřené lidské reviewery (identita přes komentář `Opora-Identity:` na GitHubu), metriky
review, eval sadu z revertů (`Opora-Revert-Of: #<n>`) a incidentů a povyšování opakovaných nálezů
na kontroly; konvence review jsou v [`REVIEW.md`](REVIEW.md).
Server sám převádí zastaralé návrhy na novou přijatou hlavu ([automatický rebase](docs/oporahub-auto-rebase.md),
vypnutí `OPORA_AUTO_REBASE=0`); člověk vidí jen skutečné konflikty stejného pole. Historie a blame karty
(`/api/oporahub/history/card/{id}`, `/api/oporahub/blame/card/{id}`) se odvozují z changesetů a nové karty
se samy zapisují do kontextu v2; existující doplní `uv run python -m backend.canvas.opora_sparse_backfill --dry-run`.

Člověk může nastavit verzovaná [pravidla review a kontrol](docs/oporahub-review-policy.md):
přesné aplikace a názvy povinných kontrol, účty reviewerů, počty schválení a stáří
důkazů. Změna pravidel vyžaduje nové načtení; novější nedokončený nebo neúspěšný
pokus zneplatní aktuální použitelnost starého úspěchu. Historie zůstává dostupná.

[Trvalé sledování PR](docs/oporahub-reconciliation.md) po zapnutí člověkem obnovuje
úlohy i po restartu a zaznamená merge k původní revizi plánu. Odděluje stav úlohy,
pozorovaný stav PR a review; neslouží jako automatické dokončení karty. Sledování
běží v backendu i se zavřeným prohlížečem.

Agent-office přebírá neměnné zadání přes nové execution API. Rostoucí číslo
převzetí brání starému běhu odevzdat výsledek po ztrátě rezervace; opakované
odeslání stejného výsledku se neduplikuje. Historie běhů odlišuje odevzdání od
ověření. Nasazení, API a omezení: [vykonávání zadání](docs/oporahub-executions.md).
Pravidla rezervací mají také [omezený TLA+ model](tools/formal/oporahub-execution/README.md)
s reprodukovatelnou kontrolou a záměrně porušenou variantou.

[Serverové ověření Harness](docs/harness-server-verifier.md) může po explicitním
nastavení opakovat přijaté porovnání skriptů v oddělených kontejnerech bez sítě.
Výstup měří server, pracovník žádá pouze o kontrolu; důkaz se ukládá do existující
historie verifikací. Neúplný běh zůstává neznámý a úspěch na příkladech nepovyšuje
nástroj do produkce ani nenahrazuje formální důkaz.

[Formální podklady](docs/oporahub-verification.md) uchovávají přesné vstupy,
tvrzení a výstupy TLC/Lean u přijaté revize a běhu agenta. Soubory mají ověřené
SHA256 a jsou dostupné z historie. Nahlášené `passed` zůstává tvrzením agenta;
nezávislý ověřovač, shoda s implementací a automatické schválení se tím neudělují.
CI na každé změně spouští TLC (`formal/tlc`: execution lease, review jobs, smyčka PR,
pozitivní i negativní konfigurace) a Lean důkazy čistého jádra (`formal/lean`: agregace
hlasů, CAS přijaté hlavy, 3-way merge polí; audit axiomů, žádné `sorry`, diferenciální test
proti Pythonu). `formal-trusted.yml` běží z definice základní větve a jeho výsledek má důvěru
`ci-verified`. Protipříklad založí návrh karty „Opravit formální ověření“ k lidskému přijetí;
`GET /api/oporahub/verifications/ledger` vypíše, co je už dokázáno. Lokálně:
`python tools/formal/lean/audit.py` (elan + Lean) a `python tools/formal/run.py --download`.

[Pravidla běhů](docs/oporahub-execution-budgets.md) přidávají lidsky nastavený
pevný konec oprávnění a trvalý počet pokusů a oprav pro kartu a přijatou revizi.
Změna vlastníka, restart, uvolnění rezervace ani nová pravidla nevracejí spotřebu.
Po zařazení karty musí vykonavatel používat budget protokol v2; starší Office
se zastaví při převzetí. Jde o oprávnění a počet spuštění, nikoli peněžní limit
nebo záruku ukončení všech potomků procesu.

Připomínky a politika přijetí podle rizika jsou implementované v etapě 3b.
[Izolovaný broker a podepsaná spotřeba](docs/oporahub-isolated-execution.md)
mají syntetické integrační důkazy i skutečný cloudový běh s potvrzeným ukončením
a autentickým provider usage. Nezávislé izolované spouštění Lean/TLA+ tato
přípravná vrstva netvrdí.
[Kontext podle závislostí](docs/oporahub-sparse-context.md) má výslovný protokol v2:
POST příprava → claim → heartbeat → výsledek. Soukromý pin, přijatá historie,
transakční SQL journal a registry fence kontrolují i relevantní změnu vrácenou
na původní hodnotu. Nesouvisející změna nemění původní zadání ani rozpočet.
Office jej zapne jen s `AGENT_OFFICE_OPORA_CONTEXT_VERSION=2`; běžné požadavky
nadále používají v1. Příprava může převést přijatý SQL draft na SQL authority
bez změny grafu. Git/file fallback ani externí obsah referencí nejsou pokryté.
Postup a meze: [napojení v2](docs/oporahub-context-v2-integration.md).
Historie se nemaže. Přesné API, migrace a omezení:
[kontrakt OporaHubu](docs/oporahub.md).
Pozorování izolovaných běhů v OporaHubu zobrazuje záznamy z API poskytovatele doložené brokerem pro právě vybraný projekt a workspace. U doložené session ukazuje kumulativní tokeny a ceníkovou spotřebu (nikoli fakturu); nulové sentinelské hodnoty bez session označuje jako nedoloženou spotřebu. Stav nečinný nepotvrzuje ukončení. Nejde o povolení běhu ani o důkaz tvrdého finančního limitu. Podrobnosti: [vykonávání a pozorování](docs/oporahub-executions.md).
- Kontrakt identity a logického členství v oblasti (pro Agent Office a Harness): [docs/kontrakt-identity.md](docs/kontrakt-identity.md).

Completed server fixture checks can use the same queue for [separate test experiences](docs/harness-kit.md#server-fixture-experiences). They do not count as accepted task successes; recalled memory never replaces native quarantine checks.

A live Harness execution can prepare a [same-card historical recovery proposal](docs/harness-kit.md#historical-recovery-proposals) from existing accepted snapshots. It preserves the running assignment and requires normal specification acceptance.

Intentionally shared Harness publications can deliver [public fixture lessons](docs/harness-kit.md#shared-fixture-lessons) through the existing OpenViking queue. Recall requires fresh native evidence and exact remote content; historical success never grants execution or promotion authority.

Native accepted Harness kits support an opt-in [version 2 selection provenance format](docs/harness-kit.md#accepted-selection-provenance-expand-stage), while preserving strict version 1. This reader expansion pins why resources were proposed; it does not attest those claims or enable automatic rollout to older workers.

Selection metadata uses matching JSON safe-integer rules in Python and Office, including integral decimal notation; malformed numbers do not become accepted provenance.
Harness writers can discover scoped accepted-kit formats through the
[read-only compatibility endpoint](docs/harness-kit.md#discover-accepted-formats-before-writing).
### Historical Harness origins

The read-only `/api/oporahub/harness-origin-history` endpoint compares native
outcomes by exact resource version and the origin pinned in an accepted kit.
Its bounded window, unknown origins, and overlapping cohorts are explicit;
declared origins are not verified ancestry or promotion evidence.
See [Harness kit](docs/harness-kit.md#historical-selection-origins).

Harness offers an identity-bound accepted-kit preflight preview before claiming a context-v2 task. It creates no execution and does not certify runner readiness; see [the preflight contract](docs/harness-kit.md#accepted-preflight-before-a-claim).

Preflight assignment identity includes the current predecessor handoff, matching the native claim contract.
Native Harness observations support accepted kit v2 when its full validator is
installed; see [compatibility and evidence limits](docs/harness-invocations.md#accepted-kit-v2-compatibility).

Accepted Context7 reads can be reported as `result.harnessDocumentation` and inspected through `/api/oporahub/harness-documentation`; see [documentation evidence](docs/harness-invocations.md#documentation-read-evidence). These are reported reference reads, not task-success rates.

Harness fixture history also exposes a scoped all-history quarantine projection: old failed
versions remain visible beyond pagination, with incomplete coverage explicit. See
[server verifier quarantine](docs/harness-server-verifier.md#lasting-quarantine-projection).

When the native Harness memory module is installed, completed fixture reports can queue [separate role-scoped experiences](docs/harness-server-verifier.md#optional-fixture-experience-delivery). Verification responses explicitly report integration availability; fixture success never becomes production acceptance.

Native Harness verification now requires an explicit [durable experiment ceiling](docs/harness-server-verifier.md#durable-experiment-ceiling); restarts and failed attempts cannot refresh the configured capacity.

Harness verifier history exposes remaining experiment capacity for the configured scope, so agents can inspect exhaustion without starting work. The read-only snapshot reserves no capacity.

Autonomous native Harness experiments require an explicit [nonproduction exploration policy](docs/harness-server-verifier.md#nonproduction-exploration-share) and nineteen eligible completed baseline cards per admitted experiment. Existing configurations without this policy remain readable but cannot start new experiments.

The optional [native stability assessment](docs/harness-server-verifier.md#native-stability-eligibility) combines exact-version closure evidence, regression checks and independent fixture results under server-approved plans. It reports project eligibility without publishing stable versions or granting production permission.
Its retained-evidence endpoint rechecks an existing native verification after the evaluation session ends, without restoring execution authority. Current policy and regressions are checked again; a historical stable label is insufficient.

Harness verifier, exploration and stability settings accept an optional [explicit multi-project scope list](docs/harness-server-verifier.md#multiple-explicit-project-scopes). Existing single-scope JSON remains valid; each project keeps its own budget and evidence.

Intentionally published versions can request [read-only shared fixture eligibility](docs/harness-server-verifier.md#shared-fixture-eligibility). The server rechecks explicitly approved source references across projects; private content is never copied and eligibility does not grant global promotion or production authority.
