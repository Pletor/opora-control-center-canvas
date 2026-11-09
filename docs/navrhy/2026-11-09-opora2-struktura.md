# OPORA 2.0: jeden plán a pracovní kontexty

Kontrakt realizace podle zadání člověka z 9. 11. 2026. Struktura skládá výsledný model aplikace a plán změn. Rešerše, Text, Kreslení a Storyboard vlastní podklady; Kancelář realizuje připnuté zadání. Velín zůstává globálním průřezem. Tento dokument není evidence přijetí ani dokončení implementace.

## Identity a autorita

- Prvek aplikace má stabilní existující `CanvasNode.id`; `parentId` je jediná autorita hierarchie. Přejmenování a přesun nemění identitu.
- Doménový druh prvku je samostatné `element` metadata. Nezaměňuje se s grafickým `kind`, workflow předponou ani `card.type`.
- Úkol popisuje změnu jednoho či více prvků a zachovává existující ticket ID. Milník je společný ověřitelný výsledek více úkolů napříč větvemi; rozšíří se existující evidence milníků.
- Výslovný rozsah realizace je `spec.fields.affectedNodeIds`: 1–50 různých ID dotčených prvků, bez ID samotného úkolu. Nejde o odvozený seznam sousedů ke čtení. Jedno přijaté zadání a jeden běh připnou `affectedElements` s revizemi dokumentů; oba protokoly Kanceláře zahrnou jejich pracovní kontexty, přijaté dokumenty a požadované vstupy. Změna dotčeného kontraktu odmítne výsledek proti starému zadání. Historická účtenka zůstává spojena se stejným execution ID, přijatou revizí a otiskem zadání. Nevznikají další tickety za jednotlivé prvky.
- Kontext pohledu tvoří projekt a ID prvku (kořen = null). Workspace určuje pracovní revizi, nikoliv novou identitu problému.
- Projektovou architekturu vlastní také služby, data, pravidla a rozhraní. Současné odvození pouze ze `site` nestačí. Staré identity, revize a konfliktní ochrany zůstávají zachované.

## Prvky a vztahy

Paleta obsahuje skupiny rozhraní člověka (stránka, formulář, přehled, dialog), chování (akce, služba, proces), data (entita, vztah, úložiště), pravidla (podmínka, oprávnění, omezení) a rozhraní částí (vstup, výstup, událost, API kontrakt). Prvek není automaticky ticket.

Sémantický vztah je nezávislý na vizuálním portu. Rozlišuje spolupráci, realizační závislost a doložení. Hierarchie se neduplikuje hranou. Server ověří obě identity, oprávnění, povolený typ a cykly blokujících závislostí. Realizační závislost vyjadřuje konkrétní požadovanou připravenost vstupu a revizi.

Vazba s výslovným `relation` nepřebírá staré workflow pořadí podle portu `next`; port zůstává vizuální a `carries` popisuje přenos. Staré netypované vazby zachovávají původní pořadí i zákaz workflow cyklů. Typované `uses` a `communicates_with` mohou tvořit spolupráci v obou směrech, zatímco `requires` musí zůstat acyklické. Požadované vstupy sektoru či jiného předka platí i pro jeho zanořené úkoly. Předávka připne identitu zdrojové vazby a přesné dokumenty cílových vstupů, ale nepřipojí požadavky nesouvisejícího sourozence.

Vazba `requires` nese `requirement: {readiness, revision, verification?}`. `revision` je přesná nezáporná revize přijatého zadání cílové karty, nikoliv ID hlavy pracovního prostoru. `design` vyžaduje tuto revizi v aktuálním přijatém snapshotu; `implemented` navíc začleněný běh s totožným připnutým dokumentem. `verified` navíc vyžaduje `verification: {positive, negative}`; každá položka má `stepId`, `check` a přesný `command`. Odkazují na dva různé přijaté testovací kroky. Server použije společný vyhodnocovač důkazů milníku: autentizovaná účtenka musí odpovídat revizi, zadání, oběma krokům, příkazům a plnému SHA začleněného běhu. Výsledek zůstává označený jako hlášení agenta, nikoliv nezávisle provedená zkouška. Neurčený, zastaralý nebo nedoložený vstup blokuje nové převzetí v obou protokolech Kanceláře; již vydané zadání uchovává neměnné reference důkazů.

## Pohledy a podklady

Přepnutí záložky zachová scope. Otevření vnořeného prvku změní scope všech pohledů. Každý pohled zobrazí lokální podklady, výslovně připojené sdílené podklady a označený relevantní kontext rodiče. Nevytváří kopie úkolů.

Storyboard dnes ukládá revizi do přepisovaného JSON souboru, nikoliv samostatnou přijatou historii v SQL. Předávka proto zachytí `storyboards` s přesnou revizí, digestem a historickým snapshotem scény pro úkol i dotčené prvky. Označení `captured-at-claim` nepředstírá samostatné přijetí storyboardu. Změna scény po připnutí blokuje odevzdání proti starému zadání; historický snapshot běhu zůstává neměnný. Oba protokoly vážou scénu do kontextu již před převzetím, aby mezitím nebyla tiše nahrazena.

Sdílený podklad má jednu autoritativní identitu, původ a revize; připojení ke scope je reference. Historický pin předávky je neměnný doklad. Vyhledávací index je odvozený, deduplikuje identity a vynucuje oprávnění před výběrem výsledků. Zkušenost z jiného projektu není automaticky platné rozhodnutí.

Předávka připíná také `researchEvidence.canonicalScopes`: jeden `canonicalRef` (projekt, prostor, ID a revize) s více kontexty a revizemi vazeb. Zdroj ve stejném oprávněném prostoru má historický digest a původ; novější revize jej v běžícím zadání nenahradí. Změna výběru vazeb vyvolá řízený konflikt a nové připnutí. Cizí projekt či prostor bez delegovaného oprávnění zůstane výslovnou referencí `source_scope_not_delegated` z cílové vazby; Kancelář nedostane obsah, název ani digest cizího zdroje. Vazba sama není udělením přístupu. Plný obsah takového původu vyžaduje zvlášť autorizovaný kontrakt předávky.

## Milník a stav

Aktivní milník je viditelný na Struktuře. Jeho výběr zvýrazní dotčené prvky v různých větvích, ostatní zůstanou dostupné. Každá práce má rozsah a vazbu na požadovaný výsledek.

Karta odděleně zobrazuje návrh, realizaci a ověření, další krok a blokující podmínku. Tyto hodnoty se odvozují z přijatých revizí, běhů a důkazů; nevzniknou tři nezávisle editovatelné deklarace. Přijetí prototypu nedokončuje funkci. Milník vyžaduje integrační scénář včetně negativních případů.

Srdce načte stručný kontext, identifikuje mezeru aktivního milníku, doplní cílený výzkum a navrhne nejmenší ucelenou změnu. Server vynucuje explicitní blokace a přijaté revize. Změna významu označí dotčené kontrakty, kosmetické přejmenování nezneplatní důkazy.

## Pořadí práce a ověření

1. Odstranit ruční bránu založení vývojového úkolu a evidovat skutečnou identitu agenta. Autonomní technické přijetí nesmí předstírat lidskou zkoušku.
2. Implementovat typ prvku, projektové vlastnictví a typované vztahy v modelu, validaci a API.
3. Sjednotit scope pracovních pohledů a reference sdílených podkladů.
4. Doplnit paletu a vlastnosti prvků, vazby úkolů na více prvků, milníkovou projekci a oddělené stavy na kartách.
5. Propojit předávku, realizaci, důkazy a dopad změny pod přesnými revizemi.

Pilot: AMPLE obsahuje Přihlášení a Izolaci tenantů s oddělenými lokálními podklady a jedním sdíleným ověřeným zdrojem. Další projekt má odlišné přihlášení. Hledání vrátí dvě řešení s původem, rozdíly a stavem ověření. Milník propojí UI, identitu a data bez kopií. Změna organizačního modelu označí dotčené kontrakty, nikoliv nesouvisející práci. Kancelář vrátí výsledek k přesné revizi zadání. Schválený prototyp se nepovažuje za funkčně ověřený průchod.

Povinná závěrečná kontrola: cílené integrační testy uvedených invariantů, `uv run pytest backend`, `npm test`, `npm run build`; report Linie s přesnou revizí, místem změny a návodem k vyzkoušení. Zelené dílčí testy nejsou důkazem celého pilotu.

## Realizační evidence a otevřené části

Vývoj patří úkolu `OP-E5D614` (`tk_e5d614a8124bebacc1177b81f7cb1754`), větev `feat/velin-linie-autonomie` z rodiče `feat/velin-linie`. Založení a `linie task` proběhly pod skutečnou identitou `agent:codex`; autonomní workflow má samostatný commit `2ca5be3e`. Autoritativní revizi, kontroly, technické přijetí agenta a začlenění uchovává kulička OP-E5D614 v Linii. Tato evidence nezapisuje přijetí člověkem.

Implementace propojuje typované trvalé prvky, významové vazby, víceprvkový rozsah úkolu a milníku, společný scope pracovních pohledů a jeden panel „Podklady a hledání“. Podklady mají kanonickou identitu a přesnou revizi; připojení ukládá reference bez kopií obsahu. Čtení cizího zdroje vyžaduje jeho vlastní oprávnění a token nepřebírá širší identitu z UI cookie. Hledání rozlišuje záznam rešerše od identity řešení a používá lexikální shodu a strukturální vazby; nejde o vektorové vyhledávání.

Návrh, realizace a ověření se odvozují z přijatých zadání a připnutých běhů. Kontrola připravenosti i porovnání důkazů zahrnují zděděné `requires` předků a jejich tranzitivní vstupy; změna těchto kontraktů zneplatní související důkaz. Efektivní cykly přes hierarchii se odmítají. Typované vazby nepřebírají staré workflow pořadí podle portu. Sémantická kompatibilita zachovává důkaz při kosmetické změně, porovnává relevantní zděděná pravidla a nezahrnuje nesouvisející sourozence. Předávka připíná zdroje i snapshot Storyboardu. Cizí zdroj bez delegace zůstává pouze referencí bez obsahu. Funkční důkaz zůstává `reported_evidence`, `independent: false`.

Historické ověření může čerpat z dříve aktivního milníku pouze s uloženou proveniencí nahrazení `replaced_by`. Zamítnuté návrhy a stará historie bez této provenience se za dříve schválený důkaz nepovažují. Rozšíření schématu je nullable; původní neznámý stav se zpětně nedoplňuje domněnkou.

Pilot `backend/api/editor/test_opora2_pilot.py` používá dočasné AMPLE a druhý projekt: typované přihlášení, izolaci tenantů, službu a entitu v různých větvích, jeden zdroj ve dvou kontextech bez kopie a přesně dvě identity řešení přihlášení. Kontroluje zachování historického pinu při nové revizi zdroje a přejmenování. Skutečné AMPLE nemění. Další důkazy jsou v `backend/editor/research/test_knowledge.py`, `test_solution_verification.py`, `backend/canvas/test_execution_canonical_research.py`, `test_execution_storyboard_evidence.py`, `test_requirement_readiness.py` a `backend/brain_opora/determinism/test_milestone_evidence.py`, `test_milestone_lineage.py`, `test_milestone_next_work.py`. Oddělené testy zdrojů, realizace a milníku nejsou tvrzením, že jediný pilot sám prokazuje všechny tyto vrstvy.

Dokončené kontroly: frontend **2908 testů v 522 souborech**, produkční build zeleně; společná sada tools/database **444 passed, 2 skipped**; skripty skillu a evaluační harness **199 passed**. Úplná backendová sada skončila s návratovým kódem 0: **6869 passed, 21 skipped, 34 warnings**, 16 workerů, 982,22 s. Otisk zdrojů před a po běhu zůstal stejný: `ba49ea3c6132741a3cd8952290db61caf80bd29ec9bf8f3720bbc421e3a6a675`.

Skutečný Chrome připojený přes MCP ověřil vývojový náhled na portu **8799**: stavové údaje zůstávají v kartách, vstup do sektoru a přepnutí Rešerše zachovávají scope a společný panel nabízí hledání bez chybových alertů. Náhled při zkoušce používal vypnutý lifespan, aby nezdvojoval pracovní smyčky. Tato prohlížečová zkouška dokládá chování náhledu, nikoliv stav nasazení nebo lidské přijetí.

Aktivní Brain skill je `opora-control-center@718903c96f0bc7549b30638ad7405d0a8441023d`. Aktualizace proběhla přes standardní registr a skutečné modelové evaly bez force či změny autorizace; konečné generování vybraného skillu zachovalo hashe všech jeho souborů i ostatních skillů. Instalovaný `opora_read.py` má SHA256 `359702c1568d13893a694ae92ca3d8060a708fb4600ac88a125eee1c17c49b90`. Příkazy `research-context`, `knowledge-search` a `research-card` jsou dostupné a zdokumentované. Deterministické testy a skutečný parser s nahrazenou HTTP vrstvou ověřují scope, typ řešení a přesnou revizi zdroje.

Opravený evaluační harness parsuje YAML pomocí vývojové závislosti PyYAML; předchozí chybné escapování regexů nelze vykládat jako měření schopností modelu. Oba skutečné běhy s opravenými gradery prošly standardní agregovanou branou (.733333 proti .733333 a diagnosticky .433333 proti .433333), ale nejsou důkazem obecné spolehlivosti modelu: obecnému požadavku na pracovní kontext odpověděl starším `node-brief`; správné hledání a pin také vyjádřil Python seznamem argumentů, který shellové regexy zamítají. Další iterace modelu nebyly provedeny. Přesná historie, skutečný aktér `agent:codex`, opravy auditní atribuce a výsledky jsou zachovány v `P:/opora-data/brain-admin-updates/opora2-knowledge-cli-corrected-harness.json` a souvisejících auditních souborech; finální text a kontrola argumentů v `knowledge-corrected-harness-debug/`.
