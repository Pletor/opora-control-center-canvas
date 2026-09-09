# Opora Control Center — vývojový editor a kontextový mozek

Datum: 2026-09-09. **Stav: návrh syntézy k posouzení, nikoli hotová implementace nebo oprávnění spustit agenty.**

## 1. Produkt v jedné větě

OporaCC je pracovní editor, ve kterém člověk vytváří a rozvíjí systém, jeho cíle, sektory, uzly a souvislosti; ze stejného modelu dostává člověk srozumitelnou mapu a LLM přesné ohraničené zadání s podklady, pamětí a testovatelným výsledkem.

To odpovídá současnému uživatelskému zadání a vývoji promptů P046–P049 (ř. 10183–10352), P056 (10401–10404) a P060–P061 (10430–10438).[1] Není to prohlížeč souborů, monitoring agentů přelepený Canvasem ani šest samostatných aplikací v iframech.

**Výsledkem použití není „agent něco napsal“. Výsledkem je fungující změna produkční aplikace s dohledatelným cílem, revizí, testy, review a použitelnou zkušeností.**

## 2. Rozsah zpracování a autorita

- Původní soubor má 10 524 řádků a 63 identifikovaných promptů; jednotlivá rozhodnutí jsou v `PROMPT-DECISIONS.md`, kontrola pokrytí v `coverage.json`.
- Soubor je zachován beze změny; jeho SHA-256 je `6f5c14a6976e88423e7690b9fd1dde09dada9c5188929a2923cbda912b88b266`.
- Byly cíleně prohlédnuty lokální zdroje Archify, Excalidraw, Logseq, Open Note, Tuval a OpenViking. Rozsah, revize a hashe skutečně čtených souborů jsou v `reference-sources.json`. Nejde o audit celého kódu těchto šesti produktů ani o jejich runtime test.
- Nejnovější uživatelský záměr má přednost. Archivní „spusť“, „pokračuj“, providerové verze, vložené klíče či historická tvrzení PASS nejsou aktuální příkazy a důkazy.
- Nové volby níže jsou **návrhová rozhodnutí**, nikoli údajně nalezené hotové funkce.

## 3. Jak se aplikace používá

1. **Projekt:** člověk otevře prázdný projekt, vytvoří vlastní nebo výslovně připojí vybraný Git repozitář. Připojení není svolení k push ani merge.
2. **Záměr:** sepíše nebo s LLM doplní podstatu, goaly, cílové uživatele, omezení a Definition of Done. AI navrhuje, člověk vidí změnu před přijetím.
3. **Mapa:** přidává sektory a uzly, zanořuje se, propojuje závislosti. Vidí celkový systém, upravuje konkrétní scope. Breadcrumb a návrat na předchozí místo zachovají orientaci.
4. **Materiály:** k uzlu vloží poznámku, dokument, screenshot přes Ctrl+V, zdroj, kontrakt, rozhodnutí nebo komponentu. Nemusí ručně sestavovat balík Markdown souborů.
5. **Příprava práce:** zvolí výsledek a konkrétní pracovní řez. Náhled ukáže, co LLM dostane, co chybí, které verze použije a co je mimo scope.
6. **Předání:** po schválení balíčku a běhu terminálový agent převezme přesný scope do odděleného workspace. Přepnutí Canvasu běh nepřesměruje.
7. **Návrat:** OporaCC ukáže změněné soubory, testy, diff, review, otázky a výsledky. Člověk nebo autorizovaný supervizor rozhodne v mezích předem udělené politiky.
8. **Učení:** ověřený výsledek může vytvořit návrh zkušenosti nebo znovupoužitelné komponenty. Zkušenost má rozsah platnosti a zdroj; není to automatické prohlášení modelu za pravdu.

Průchod realizuje požadavek na systematické podklady, paměť a přenos práce z P047, P049 a P056, nikoli pouze přehled procesu.[1]

### Připojení existující codebase není jen clone

Onboarding R00 má samostatnou read-only cestu: výslovně zvolený repozitář a přesný SHA → bezpečný inventář souborů → citované SourceRef/AssetRef → návrh rozdělení do sektorů/uzlů → diff a lidské přijetí. Originální repo se nemění a import nespouští jeho kód, build, hooks, filtry ani automatické submodule procesy. Citlivé soubory a nepovolené cesty se nevkládají do LLM kontextu.

Každý importovaný podklad má repo/SHA/path/blob hash a známé pokrytí parseru. Extrahované symboly a vztahy mají zdroj, odhadnuté goaly či hranice modulů jsou pouze návrhy. Nečitelný formát, binary, velikostní limit nebo neanalyzovaná část se zobrazí jako chybějící/nepodporované, ne jako hotová analýza celého projektu.

Refresh vůči novému SHA porovná původní snapshot, zachová ID a lidská rozhodnutí a nabídne změny/konflikty před přijetím. Import nového commitu neaktualizuje existující ContextBundle ani grant potichu. Prázdný projekt R00 nepotřebuje; pro práci s existující codebase je to povinná vstupní brána. OporaCC tím naplňuje i P061 ř. 10438, ne jen ruční tvorbu nové mapy.[1]

## 4. Jedna skutečnost, několik pohledů

**Doporučení:** zachovat Python/FastAPI a React shell; React Flow použít pro sémantické sektory/uzly, Excalidraw jako lazy-loaded editor kresby u uzlu, Archify jako odvozenou čitelnou architektonickou projekci. Excalidraw skutečně poskytuje React knihovnu, nikoli jen hotový web.[4][5] Archify odděluje typed JSON, renderery, validaci a viewer.[2]

Čtyři pohledy nad stejnými identitami a revizemi:

- **Canvas:** vztahy, prostorové uspořádání, sektor a zanoření.
- **Strom / outliner:** rychlá klávesnicová práce, vyhledávání a hierarchie.
- **Dokument uzlu:** podstata, goaly, specifikace, materiály, rozhodnutí a kontext.
- **Pracovní průchod:** konkrétní WorkUnit, supervizor, terminálový běh a evidence.

Kresba může být volná. Sémantický vztah však vzniká explicitním propojením na Node ID nebo přijatým návrhem, ne odhadem z toho, že šipka leží blízko obdélníku. Tuval ukazuje hodnotu sémantické struktury, traversal pořadí a vazby exportů na zdrojové elementy; jeho vlastní snapshoty přitom nemusejí obsahovat neuložené lokální úpravy.[14][15]

### Fraktální zanořování

- Každý sektor i uzel může mít vlastní podplátno; typ určuje roli, ne umělý konec zanoření.
- `contains` určuje jednoho strukturálního rodiče; strom nesmí mít cyklus. Dependency je samostatná typovaná vazba a může vést mezi sektory i úrovněmi.
- Děti dědí platné nadřazené cíle a omezení; permissions se samy nerozšiřují podle kreslených vazeb.
- Načítá se vybraná vrstva, její souhrny a potřebné sousední rozhraní, ne celý strom. „Nekonečný“ znamená žádný produktový limit počtu úrovní, nikoli neomezenou RAM nebo odpověď API.
- Přesun uzlu zachová identitu, podklady a historii. Změněné dědění označí dopad na kontexty a vyžádá novou validaci dotčených balíčků.

## 5. Doporučená modulová mapa

| ID | Modul | Vstup → výstup | Vlastnictví / hranice |
|---|---|---|---|
| M01 | Editor a navigace | uživatelská editace → typovaná změna, projekce | UI vlastní selection a viewport, ne vlastní kopii pravdy |
| M02 | Sémantický model projektu | cíle, uzly, vazby, revize → ověřený graph snapshot | jediný writer pracovní revize; containment, typy a CAS |
| M03 | Dokumenty a materiály | text, image, source → Document/AssetRef | originál, MIME, hash, citlivost a provenance |
| M04 | Context compiler | node + WorkUnit + policy → immutable ContextBundle | deterministický výběr a manifest; žádné execution |
| M05 | Paměť a zkušenosti | citované zdroje/evidence → kandidát a schválená knowledge revision | scope, freshness, deduplikace a supersession |
| M06 | Supervizor a schválení | cíl + checkpoint + policy → proposal/decision | význam a approval, nikoli druhý runtime orchestrátor |
| M07 | Terminálový adaptér | schválený binding → převzetí práce a normalizované události | explicitní capability; žádný obecný remote shell |
| M08 | Workspace a Git | schválený repo/workspace request → izolovaný worktree, SHA, diff | Git vlastní commit/branch; main je read-only projekce |
| M09 | Ověření a evidence | artefakt + revize + test/review → doložený výsledek | text workera je claim; proof má vlastní zdroj |
| M10 | Knihovna komponent | ověřená implementace a UX výsledek → versioned reusable component | licence, kompatibilita, kontrakt, testy, omezení |
| M11 | Routing a zdroje | risk + capability + budget → zvolený adapter/model a limity | měřená/odhadovaná/neznámá usage zvlášť; explicitní fallback |
| M12 | Inbox a obnova | události + cursory → upozornění a reconcile | dedupe, restart-safe pointers; žádné tajné pokračování |

Je to členění odpovědností, **ne požadavek na dvanáct mikroslužeb**. První implementace může být modulární monolit s jednou lokální databází a background jobs; externí paměť a modelové služby jsou volitelné adaptéry.

## 6. Doménový kontrakt

Navrhované entity:

- `Project`: identita, podstata, zdroje, zvolený lifecycle adapter a execution policy.
- `Node`: stabilní ID, parent, role, název, účel a odkazy. Uzel není totéž co jeden WorkUnit.
- `Goal`: zamýšlený výsledek, akceptace, vlastník a rozsah.
- `Relation`: stabilní ID, zdroj/cíl a význam (`depends_on`, `implements`, `consumes`, `constrains`, `evidenced_by`, `supersedes`). `contains` má přísnější stromová pravidla.
- `NodeSpecRevision`: goaly, non-goals, rozhraní, acceptance, rizika, rozhodnutí, dokumenty a původ.
- `Document` / `AssetRef`: strukturovaný obsah nebo blob reference; hash, revize, originál, citlivost, bezpečný preview. Generované shrnutí odkazuje na zdroje.
- `WorkUnitRevision`: přesný změnový řez, povolené cesty, DoD, workflow revize, tests, závislosti a vazba na NodeSpec.
- `ContextBundle`: zmrazený výběr těchto verzí, zdrojové hashe, rozpočet, zahrnuté/vynechané zdroje a digest. **Bundle není run.**
- `SupervisorBinding` / `RunBinding`: node, WorkUnit, bundle, policy, workspace, adapter, session/run a epoch. Identitu běhu doplní runtime, nikoli model.
- `EvidenceRecord`: původní pozorování nebo claim, druh ověření, ověřený commit/artifact, nástroj, výsledek a čas.
- `LessonRevision` / `ComponentVersion`: citovaný, revidovatelný a scope-bound výsledek učení.

Verze nejsou dekorace: klientská editace posílá `expected_revision`; souběžná zastaralá editace se nepropíše jako tiché last-write-wins. Kritická změna zadání po vydání bundle vytváří novou revizi a nový approval, ne přepis minulého běhu. Historie a čas události se zachovají; odvozené pohledy mají vlastní `observed_at` a stav freshness.

### Kdo vlastní pravdu

| Druh informace | Autorita | Co je jen odvozené |
|---|---|---|
| Schválená main revize kódu/specifikace | Git commit vybraného projektu | lokální index a main Canvas |
| Rozpracovaný editorový model | transakční pracovní revize OporaCC pro daný workspace | Canvas, outliner, Archify, context preview |
| Checkpoint modelu do Git | explicitní export konkrétní pracovní revize + hash | žádná druhá tichá synchronizace editovaných kopií |
| Externí editace stejného modelu | vstup k importu/reconciliation s konfliktem | nikoli automatické přepsání DB |
| WorkUnit lifecycle | nakonfigurovaná workflow autorita projektu | barevný badge v OporaCC |
| Stav konkrétního běhu a jeho seq | právě jeden deklarovaný RunOwner, např. Bridge | connector cursor, inbox a UI cache |
| Test / CI / review | konkrétní runner/CI/reviewer s vazbou na artefakt | shrnutí LLM |
| Přijatá zkušenost | verzovaný knowledge record s evidence a approval | embedding, souhrn a relevance skóre |

U OPORA se zachovává zavedená autorita WorkUnit/GitHub Projectu; editor z ní nedělá druhý lifecycle. U obecného projektu se adapter volí při onboardingu. Totéž platí pro Bridge: pokud je vlastníkem běhu, OporaCC ho řídí přes úzké rozhraní, ne duplikovaným state machine. Historické prompty tuto hranici opakují v P023, ř. 3366–3384.[1]

## 7. Supervisor a „tunel nad uzlem“

Tunel je **logický obousměrný kanál jednoho schváleného scope**, ne veřejný síťový tunel ani jeden trvalý LLM proces na každou kartičku.

- Každý uzel může mít supervisor konfiguraci, historii a zděděná omezení. Neaktivní uzel nemá placenou session.
- Rodič drží celkový záměr a rozhraní; dítě řeší ohraničený výsledek. Nový problém jde jako otázka/NEXT NODE k vlastníku, ne jako tiché rozšíření scope.
- VS Code je hostitel terminálu. LLM CLI je worker. OporaCC drží mozek a materiály; adapter řeší jejich předání a návrat důkazů.
- Preferovaný první transport je lokální stdio MCP pro kontextové a řídicí operace, doplněný adaptérem podporovaného CLI. Samotné MCP neprokazuje umění bezpečně spouštět, opravovat nebo zastavovat daný proces.
- Model s podporou tools načítá manifest a potřebné resources. CLI bez těchto schopností může dostat explicitní snapshot souboru, ale UI přizná nižší schopnosti a ruční předání; nesmí simulovat plnohodnotný tunel.
- Přepnutí aktivního uzlu v UI nesmí změnit žádný existující `RunBinding`.

Podrobný stavový, bezpečnostní a restart kontrakt je v `TUNNEL-AND-CONTEXT.md`. Převzaté principy jsou v P013 (773–812), P017, P025–P027 a P039; názvy konkrétních budoucích rozhraní jsou návrh, ne tvrzení o jejich existenci.[1]

## 8. Paměť a sebezdokonalování

Doporučený první krok je lokální citovaný knowledge store s full-text indexem, adresovatelnými zdroji, L0/L1/L2 projekcemi a invalidací revizí. OpenViking může později fungovat jako volitelný retrieval adapter. Jeho lokální dokumentace popisuje L0/L1 jako adresářové souhrny a L2 jako detaily, nikoli automaticky tři soubory pro každou poznámku.[18]

Zachovat oddělení:

1. **Originály a rozhodnutí člověka.** Nikdy nepřepisovat kvůli kompakci kontextu.
2. **Indexy a souhrny.** Obnovitelné odvozeniny, označená freshness a coverage.
3. **Pracovní paměť běhu.** Krátký relevantní stav, scope a checkpoint; ne celý chat navždy.
4. **Zkušenosti a komponenty.** Kandidát → ověření/review → přijatá verze → případné zneplatnění/supersession.

OpenViking session commit může archivovat zprávy a automaticky extrahovat, slučovat či mazat memories; toto chování se nepřevezme jako výchozí produktová politika, protože by nebylo totožné s požadavkem zachovat historii.[19] Duplicity zkušeností se počítají podle root evidence, ne podle počtu agentních shrnutí stejné chyby.

Systém se učí: chyba → reprodukce → příčina → oprava → regresní test → posouzená lesson. U fungujícího řešení navíc uloží kontrakt komponenty, dependency/licenční omezení a skutečné UX/CX ověření. Automatická změna vlastních pravidel, routing policy nebo produkčního kódu tím nevzniká.

## 9. CX / UX / UI jsou součást zadání

Každý relevantní uzel má tři odlišené části, nikoli univerzální kolonku „design“:

- **CX:** čí potřebu a část zákaznické cesty řeší, jaký dopad má vzniknout a kdo jej posoudí.
- **UX:** konkrétní cesta uživatele, rozhodnutí, empty/loading/error/recovery stavy, přístupnost a měřitelné dokončení úkolu.
- **UI:** komponenty, stavy, tokeny, chování, vizuální podklady a reference.

Komponenta se nabízí k opakovanému použití podle kompatibility kontraktu a důkazů, ne jen podobnosti screenshotu. Kvalita návrhu modelu není měřená kvalita použití; lidské hodnocení je jiný evidence typ než automatický test.

## 10. Rychlost je architektonický kontrakt

- Shell, navigace a základní editace nesmí čekat na Git, embedding, internet, model ani health všech služeb.
- Excalidraw se načte až při editaci kresby. Paměť a Git běží mimo kritický UI request a mimo zámek editorových transakcí.
- API nabízí stránkování, inkrementální změny a dotazy pro vybranou vrstvu. Ne každá změna přepočítává celý graf a souhrny všech předků.
- Deduplikované background jobs, invalidace podle hashe a oznámení staleness před drahým refresh.
- SQLite vlastní jeden aplikační writer; návrh inspirovaný jasným oddělením rendereru a graph authority v Logseq, nikoli kopie jeho celé platformy.[8]

**Navržené akceptační cíle, dosud NEZMĚŘENÉ:** p95 použitelného shellu do 1 s a p95 navigace/otevření uzlu do 300 ms na zaznamenaném referenčním PC, při testovací sadě 10 000 uzlů celkem a nejvýše 1 000 uzlů zobrazené vrstvy. Zvlášť se měří cold/warm průchod, nedostupný Git/paměť a editor s otevřenou kresbou. Tyto cíle se nejprve ověří a podle důkazu upraví; nejsou aktuálním výsledkem Canvasu.

## 11. Co skutečně umí nynější Canvas

Aktuální model uzlu obsahuje pouze ID, rodiče, kind, name, purpose a souřadnice; hrany nemají typovaný význam.[22] Backend současně omezuje celý graf na 2 000 uzlů a 4 000 hran a vyžaduje vazby jen mezi uzly stejné vrstvy.[21] SQLite tabulky v kontrolovaném service obsahují projekty, workspaces, drafts a jobs; nejde o hotový doménový model popsaný výše.[23]

**Závěr:** současný Canvas je použitelný navigační a Git/worktree základ, ale plný požadovaný editor ještě není hotov. Nová specifikace není důkaz implementace ani produkční připravenosti. Historický úspěch malých testů nenahrazuje důkaz hlubokého velkého grafu, terminálové izolace, paměti a skutečného uživatelského průchodu.

Zachovat: samostatný projekt, rychlý lokální shell, Python backend, schválený main versus workspace, prázdný produkční projekt a stávající kompatibilitu `opora-canvas.json`. Rozšíření modelu dostane explicitní schema verzi a nedestruktivní migraci; starý soubor ani aplikace se nemažou.

## 12. Rozpory vyřešené pro tento návrh

| Archivní návrh | Nynější výklad |
|---|---|
| Voice / ChatGPT web jako centrum | Editor je centrum; voice a konkrétní cloudová surface jsou volitelné |
| Přesně pět starých MCP tools | Zachovat úzký allowlist, ne navždy historický počet; context a runtime APIs mají oddělená oprávnění |
| Zákaz auto-routing v raném slice | Tehdejší scope; nyní navrhnout routing modul, ale nezapnout neověřené automatické přepínání |
| Jeden globální active_run_id | Bindingy podle node/workspace/WorkUnit/run; žádné sdílené globální řízení |
| Uzel = WorkUnit | Uzel je trvalý; WorkUnit je jeho konkrétní verzovaný změnový řez |
| Nekoneční běžící supervizoři | Trvalá konfigurace a historie, ale relace jen na požádání a s limity |
| Markdown pro všechno / úplné vyhození dokumentů | Strukturovaný model a editor; textové projekce/export jen kde pomáhají |
| „Učení“ z každého modelového závěru | Citované kandidáty, ověření, scope a verzované přijetí |
| STOP čeká na souhlas | Bezpečnostní STOP musí být dostupný okamžitě; destruktivní změny a restart potřebují odpovídající souhlas |
| Hotovo podle agenta či starého PASS | Artefakt + správná revize + test/review + autoritativní lifecycle |

Tyto závěry jsou rozhodnutí této syntézy. Jednotlivé sekční review v `reviews/` jsou podklady; jejich doporučení nejsou samostatnými aktuálními příkazy.

## 13. Hranice další realizace

Pořadí je editorový model → použitelná editace → důvěryhodný context bundle → skutečný terminálový handoff → ověřování a učení. Konkrétní řezy, non-goals, gates a průkazné testy jsou v `DELIVERY-GATES.md`.

První implementační karta vzniká jako kandidát, nikoli samozvané READY. Pokud je pro daný projekt nadále vyžadován Fablem vytvořený READY Node Card, musí tuto autoritu získat před produkčním kódováním. Tato syntéza nezakládá nové oprávnění ke změně cizích repozitářů, spuštění placených session ani merge.

## Sources

[1] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/prompt-opora-control-center.md — Prompty
[2] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/archify/PRODUCT.md — archify/PRODUCT.md
[4] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/excalidraw/README.md — excalidraw/README.md
[5] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/excalidraw/packages/excalidraw/package.json — excalidraw/packages/excalidraw/package.json
[8] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/logseq/docs/agent-guide/implemented/architecture/2026-08-24-logseq-runtime-and-engineering-guide.md — logseq/docs/agent-guide/implemented/architecture/2026-08-24-logseq-runtime-and-engineering-guide.md
[14] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/tuval/docs/agents.md — tuval/docs/agents.md
[15] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/tuval/docs/mcp.md — tuval/docs/mcp.md
[18] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/03.Agents-tools/OpenViking/docs/en/concepts/03-context-layers.md — OpenViking/docs/en/concepts/03-context-layers.md
[19] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/03.Agents-tools/OpenViking/docs/en/concepts/08-session.md — OpenViking/docs/en/concepts/08-session.md
[21] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/Opora-control-center-canvas/backend/graph.py — backend/graph.py
[22] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/Opora-control-center-canvas/src/types.ts — src/types.ts
[23] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/Opora-control-center-canvas/backend/service.py — backend/service.py
