# Implementační řezy a důkazy

Datum: 2026-09-09. **Kandidátní fronta, ne schválené READY karty a ne hotový kód.**

## Pravidla dodávky

- Zachovat současný Canvas, originální prompty a reference projekty. Žádný další blanket rewrite.
- Jeden writer a jeden vymezený worktree na implementační řez; jiné nálezy jsou NEXT NODE, nikoli vedlejší nevyžádané opravy.
- Každý řez: cíl/UX/data/security → schválená SPEC → RED → implementace → GREEN → review přesného stavu → checkpoint s důkazy.
- Přesný commit, build, testy a review jsou artefakty, ne odhady. Fixture a skutečný LLM běh jsou odlišné evidence třídy.
- Bez Fablem vytvořené READY karty, pokud je to platná projektová autorita, nevydávat zdejší návrh za implementační oprávnění.

## Řezy

| ID | Dodávaný výsledek | Acceptance / důkaz | Non-goals a vstupní gate |
|---|---|---|---|
| R00 | Read-only onboarding existující codebase a přijaté mapování | přesný repo/SHA inventář; dohledatelné SourceRef; návrh sektorů/uzlů s diffem; explicitní přijetí; nový SHA vytvoří reconcile a stale kontext, ne tichý přepis | volitelné pro prázdný projekt, povinné pro práci s importovanou codebase; bez spuštění zdrojového kódu, hooks, write do zdroje a neprověřeného ingest do LLM |
| R01 | Trvalá NodeSpec a její jednoduchý editor u existujícího uzlu | uživatel upraví goal, non-goals a acceptance; reload je zachová; stale revision vyvolá čitelný konflikt; main read-only | bez spouštění agentů, paměťové služby a překreslení celého UI; schválená schema/migrační karta |
| R02 | Materiály a kresba u uzlu | Ctrl+V screenshot, bezpečný preview, reference na originál; Excalidraw scene reload; uzel zůstává sémantická identita | licence a ověřená knihovní verze; žádná automatická interpretace kresby jako execution |
| R03 | Hluboká navigace a typované vztahy | zanoření, návrat, přesun s dopadem, cross-sector dependency; stránkování velkého grafu; žádný globální reload při editaci | navazuje na M02, test cyklů a migrace; ne celá Logseq platforma |
| R04 | Preview a deterministický ContextBundle | stejný frozen input → stejný digest; povinné constraints nejsou potichu zkráceny; stale/missing source blokuje; explicitní výčet zahrnuto/vynecháno | žádný run; lokální zdroje jen ve vynuceném scope |
| R05 | Jeden skutečný terminálový handoff | reálný podporovaný CLI převezme přesný bundle do dočasného povoleného worktree, vrátí změnu a checkpoint; start/STOP/restart/duplicate request mají důkaz | capability/secret/izolační gate; max jeden writer; žádný produkční push/merge |
| R06 | Review a evidence uzavření | worker claim oddělený od skutečného testu; evidence navázaná na commit a WorkUnit; UI ukáže čekající schválení nebo blocker | fake worker neprokazuje runtime; žádné automatické DONE podle textu |
| R07 | Lokální paměť a knihovna komponent | chyba → reprodukce → lesson proposal → přijetí; dedupe root evidence; změněná verze zneplatní relevantní souhrn; kompatibilní komponenta jde vložit jako reference | bez povinného OpenViking/cloud embedding; žádné automatické přepisování originálů |
| R08 | Omezená multi-agent práce a goal-loop | dva disjunktní workspaces mají nezávislé bindingy; kolize scope je odmítnuta; budget/STOP/parent escalation fungují; inbox přežije restart | až po single-worker důkazu a technické izolaci; žádné neomezené noční smyčky |

Routing a resource policy se zavádí už s R05 v nejmenší potřebné podobě; R08 ji rozšiřuje, ne teprve vynalézá. Export Archify je projekce nad přijatým sémantickým modelem, ne samostatný nový editorový scope.

### Vstupní gate R00 pro existující projekt

R00 je malý zdrojový adapter a review návrhu mapování, nikoli automatické reverzní inženýrství celé aplikace. Zkontroluje explicitní repo allowlist, SHA a read scope; vygeneruje omezený inventář s provenance a coverage; nabídne odvozené mapování pro přijetí. Rozpracované NodeSpec a asset editor se rozvíjejí v R01/R02. Už přijatý graf se nesmí nahradit novým odhadem z parseru. U prázdného projektu lze začít R01 bez této brány.

Negativní případy: změna SHA během inventury, nepovolený/citlivý soubor, Windows link escape, nečitelný formát, dvojí import, přejmenování souboru, konflikt s ručně upraveným uzlem, výpadek parseru. Žádné chybějící pokrytí se nevydává za kompletní zmapování. Zápis do zdroje nebo spouštění jeho příkazů musí být fyzicky mimo capability importu.

## Kandidát první editorové karty R01

**Status:** CANDIDATE / NOT READY. **Purpose:** člověk nemusí zadání uzlu držet v chatu a přepisovat ho LLM.

**UX:** v detailu existujícího uzlu je oddíl Zadání: goal, non-goals, acceptance. Stav Ukládá se/Uloženo/Konflikt/Chyba, zachovaný rozepsaný text při problému, main pouze pro čtení. Žádné tlačítko „Spustit“, dokud neexistuje schválený runtime.

**Data:** samostatná verzovaná NodeSpec vázaná na project/workspace/node; invariant neměnné identity, `expected_revision`, historii změn a kompatibilitu existujícího grafu. Výchozí prázdná specifikace nesmí přepsat původní `purpose` ani vydávat absence za schválený goal.

**Plánované rozhraní:** read spec / propose-and-save spec v povoleném draft/workspace; konkrétní route/schema se finalizuje v READY kartě. Povinné je ověření vlastnictví projektu a uzlu před čtením i zápisem.

**Kandidátní souborový scope — musí jej potvrdit READY karta:** nové `backend/node_specs.py`, `src/NodeSpecEditor.tsx`, `tests/test_node_specs.py`, `e2e/node-spec.spec.ts`; nejmenší nutné integrační změny `backend/app.py`, `backend/service.py`, `src/types.ts`, `src/App.tsx`. Jeden writer; žádné refaktory sousedních aplikací.

**RED případy:** persistence po restartu; druhý klient uloží starou revision; neexistující/cizí node; pokus main write; nevalidní dlouhé pole; souběžný update; selhání zápisu nezpůsobí falešné Uloženo. Přesné limity polí se schválí jako parametr kontraktu, nikoli odhadnou v UI.

**GREEN evidence:** skutečný backend test, UI průchod edit → reload → stejná verze, druhý klient → konflikt, main write → odmítnutí; build a základní regrese Canvasu. Review přesné výsledné revize a prokazatelně zachovaný původní `opora-canvas.json`.

**Migration/rollback:** append-only schema a historie, původní data zachovaná. Feature lze vypnout bez zahození nových specifikací; export a rollback se testují na kopii, ne produkčních datech.

## Release gates celého produktu

### Uživatelský gate

Člověk bez ručního skládání dlouhého promptu vytvoří projektový cíl, zanořený uzel, vloží podklad, vidí relevantní kontext, zadá práci a dohledá ověřený výsledek. Chyba či nedostupná služba ho nepřipraví o práci. CX/UX/UI akceptace se ověří na konkrétním scénáři, nikoli jen screenshotem.

### Data a historie

Zdrojové dokumenty, graph identity, NodeSpec revize a důkazy mají provenance. Restore z exportu je ověřený. Souběžná editace nevede k tiché ztrátě. Přesun uzlu aktualizuje dopad na dědění; layout změna neinvaliduje sémantický bundle.

### Bezpečnost a integrace

Žádná obecná shell proxy. Skutečný scope enforcement, main guard, citlivé soubory, MIME/přílohy, injection v dokumentech, secret redakce, atomický/idempotentní start, STOP a restart race mají negativní testy. Samotný worktree a prompt nejsou sandbox — archiv to výslovně rozlišuje v P013, ř. 773–812.[1]

### Výkon

Sledovat p95 použitelného shellu, navigace, textové editace, otevření kresby, context compile a paměťovou stopu na známé fixture a zaznamenaném hardware. Cíle z `EDITOR-SPEC.md` jsou předmětem měření. Zvlášť cold/warm, velký graf a nedostupné služby. Levná API odpověď bez použitelného editoru není výkonový PASS.

### Důkazy produkčního výsledku

Schválená SPEC a změnový scope → přesný commit/diff → skutečné testy/build → nezávislé review → správná lifecycle autorita. Plná produkční připravenost zůstává NEPROKÁZANÁ, dokud tyto gates neprojdou na cílovém průchodu; dnešní source syntéza ji neprohlašuje.

## Záměrně odložené dveře

Voice a realtime mikrofon; veřejný/remote tunel; cloud sync a týmové realtime co-editing; autonomní merge; generický plugin marketplace; povinné vnoření celého Logseq/Tuval/Open Note; automatické rozsáhlé benchmark kampaně; nepřetržitý placený agent na každý uzel. Každé rozšíření potřebuje vlastní uživatelskou hodnotu, licenci, riziko a skutečný probe.

## Sources

[1] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/prompt-opora-control-center.md — Prompty
