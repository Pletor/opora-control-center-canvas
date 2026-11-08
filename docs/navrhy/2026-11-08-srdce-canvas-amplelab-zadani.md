/goal Dokonči propojení Pletor → Srdce → Canvas → zadání pro agenty tak, aby Srdce skutečně vytvářelo, ukládalo, aktualizovalo a ověřovalo plán na plátně. Oprav chybějící návaznosti a implementuj potřebná rozhraní, funkce nebo ovládací prvky. Výsledek předveď na aktuálních výzkumech a rozpracovaném plánu AmpleLab.
## 1. Cíl a očekávaný výsledek

Canvas má být pracovním prostředím specializovaným pro agenty a jejich relace. Musí jim jednoznačně zpřístupnit:

- co je cílem projektu a právě řešené části;
- co už existuje a co je potřeba změnit;
- co je doložené, navržené, přijaté nebo neověřené;
- jak spolu souvisejí požadavky, výzkumy, rozhodnutí, obrazovky, data a úkoly;
- co mohou dělat nyní a proč;
- co je blokuje;
- kdo na čem pracuje;
- jak ověří výsledek;
- na jakém místě pokračovat po přerušení nebo v nové relaci.

Úspěchem tohoto /goal je funkční změna aplikace a skutečně uložený plán. Závěrečný text, seznam doporučení ani samotné dokončení výzkumů nejsou dostačujícím výsledkem.

Implementuj nezbytné změny schopností Srdce a canvasu. U aktuálního plánu AmpleLab zachovej oddělení návrhu, přijetí a realizace. Oprava plánovacího systému sama o sobě nespouští všechny navržené produktové a databázové změny.

## 2. Zachovej role a existující práci

Respektuj následující odpovědnosti:

- **Pletor** komunikuje s uživatelem, drží jeho záměr, vysvětluje stav a předává požadavky Srdci.
- **Srdce** analyzuje podklady, sestavuje a aktualizuje návrh plánu, ovládá canvas a připravuje konkrétní předávky.
- **Canvas** zobrazuje společný uložený model požadavků, rozhodnutí, vztahů a práce.
- **Kancelář / realizační agenti** přebírají připravené úkoly a implementují je v mezích přijatého zadání.

Nejdříve zjisti skutečnou současnou architekturu. Názvy těchto rolí nepovažuj za důkaz, že odpovídající rozhraní nebo chování už existují.

Zachovej původní požadavky, existující karty, stabilní ID, historii, důkazy, přijatá rozhodnutí a rozpracované úkoly. Aktualizace musí navazovat na existující prvky.

Srdce může průběžně ukládat a rozpracovávat **návrh** bez potvrzování každé kartičky. Přijatý plán mění prostřednictvím dohledatelného návrhu změny podle existujícího způsobu přijetí. Již udělená a stále platná schválení znovu nevyžaduj.

## 3. Nejdříve zjisti konkrétní příčinu zastavení

Dohledáním aktuálního běhu projdi skutečný řetězec:

**požadavek uživatele → předání Pletorem → běh Srdce → výzkum → zpracování výsledku → návrh změny canvasu → zápis → zpětné načtení → zobrazení.**

Zjisti poslední úspěšný krok a první chybějící nebo chybný krok.

Prověř zejména:

- zda Srdce vůbec dostává nástroje pro práci s canvasem;
- zda je umí objevit a zná jejich vstupy a výsledky;
- zda dokončení výzkumu spouští další plánovací krok;
- zda běh nekončí po uložení výzkumného výsledku;
- zda proces nečeká na přijetí, které není v UI srozumitelně zobrazené;
- zda zápis neselhává kvůli validaci, oprávnění nebo konfliktu revizí;
- zda jsou změny uložené, ale UI zobrazuje starý stav;
- zda se při přerušení nebo obnovení relace neztratí pokračování.

Diagnózu dolož aktuálním kódem, relevantními událostmi a stavem dat. Uveď konkrétní rozhraní a místo chyby. Nevymýšlej příčinu ani nový endpoint podle názvu komponenty.

Po nalezení nezbytných kontraktů vytvoř první funkční průchod: Srdce uloží malou smysluplnou část návrhu, zpětně ji načte a zobrazí na canvasu. Teprve na tomto ověřeném základu rozšiřuj pokrytí funkcí.

## 4. Zpřístupni Srdci všechny skutečné funkce canvasu

Vytvoř inventář současných funkcí canvasu. „Kompletní ovládání“ musí mít konečný a kontrolovatelný rozsah.

U každé existující operace zaznamenej:

- význam a konkrétní použití;
- kde je implementovaná;
- zda jde o trvalou změnu modelu, nebo o pohled konkrétní relace;
- zda ji Srdce umí vyvolat;
- vstupy, výstupy, oprávnění a chybové výsledky;
- způsob ověření;
- případnou chybějící implementaci.

Inventář musí podle skutečných možností aplikace zahrnout:

1. Čtení projektu, pláten, hierarchie, karet, detailů a vazeb.
2. Vyhledávání prvků a načtení relevantního výřezu grafu.
3. Vytváření a úpravy oblastí, sektorů, uzlů a jejich vlastností.
4. Přesouvání, seskupování, změny rodiče a organizaci struktury.
5. Vytváření a změny významových vazeb a datových portů.
6. Připojování výzkumů, důkazů, rozhodnutí a otevřených otázek.
7. Milníky, úkoly, závislosti, blokace a stav připravenosti.
8. Skici a kreslicí prvky, pokud je aplikace podporuje.
9. Rozložení prvků, sbalování, filtry, výběr a zaměření části plátna.
10. Historii, porovnání revizí, návrhy změn a podporované vratné operace.
11. Přípravu předávky agentovi a načtení výsledků jeho relace.
12. Další funkce nalezené v aktuální implementaci.

Existující smysluplná funkce nesmí zůstat dostupná pouze člověku v UI bez odpovídajícího způsobu použití Srdcem. Pokud je pro určitou operaci nutné lidské přijetí, Srdce musí umět připravit její návrh a srozumitelně ukázat důvod čekání.

Ovládání řeš přes autoritativní aplikační rozhraní a doménové operace. Znovupoužij pravidla, která používá aplikace. Nevytvářej druhou nezávislou implementaci stejných změn.

Změny pohledu, například zoom nebo výběr, odděl od změn společného plánu. Jedna agentní relace nesmí nechtěně přestavovat pracovní pohled jiné relace.

## 5. Každá změna musí být spolehlivá a dohledatelná

Navrhni nebo doplň kontrakt operací tak, aby podle relevance obsahoval:

- identitu projektu a organizace;
- identitu cíle, požadavku, běhu a relace;
- identifikátor operace pro bezpečné opakování;
- očekávanou revizi upravovaného stavu;
- validované změny;
- výsledek se skutečnými ID a novou revizí;
- dohledatelný záznam původu a důvodu změny.

Po zápisu ověř uložený stav zpětným načtením. Pletor smí oznámit, že je plán vytvořený, až když existují uložené prvky a jejich výsledek odpovídá požadavku.

Zajisti, aby:

- opakování stejného požadavku po timeoutu nevytvářelo duplicity;
- souběžné relace neztrácely navzájem své změny;
- neplatné vazby a odkazy byly odmítnuty;
- neúspěšná změna nezanechala neohlášený rozpracovaný stav;
- starší relace nepřepsala novější přijatou revizi;
- všechny operace respektovaly projektová a organizační oprávnění;
- šlo rozlišit návrh, odeslanou změnu, uloženou změnu, přijetí a realizaci.

Způsob transakcí, verzování a obnovy přizpůsob existujícímu úložišti. Nevydávej vícekrokový částečný zápis za atomickou změnu.

## 6. Výzkum musí průběžně měnit plán

Odděl alespoň tyto významy stavů; konkrétní názvy přizpůsob existujícímu modelu:

- **Stav výzkumného běhu:** čeká, probíhá, dokončen, selhal.
- **Platnost zjištění:** neověřené, podložené, sporné, zastaralé.
- **Stav rozhodnutí:** návrh, přijaté, odmítnuté, nahrazené.
- **Stav práce:** návrh, blokováno, připraveno, převzato, probíhá, k ověření, ověřeně dokončeno.

Dokončený výzkum bez relevantního důkazu může zůstat dokončeným během. Jeho závěr ale nesmí být vydávaný za ověřený fakt.

Po převzetí výsledku výzkumu musí Srdce:

1. Zachovat původní otázku, zjištění a zdroje.
2. Vyhodnotit, která konkrétní tvrzení jsou zdroji podložená.
3. Připojit verzi, datum nebo revizi, pokud ovlivňuje platnost.
4. Propojit zjištění s existujícími požadavky a prvky plánu.
5. Zapsat varianty, jejich důsledky a doporučené rozhodnutí.
6. Aktualizovat příslušný návrh na canvasu.
7. Označit skutečné mezery a jejich dopad.
8. Připravit návrhy navazujících úkolů.
9. Pokračovat v částech, které nejsou blokované.
10. Vrátit Pletorovi skutečně provedené změny a další krok.

Nevyřešená otázka smí blokovat jen své skutečné závislosti. Není důvod držet celé plátno prázdné do dokončení všech výzkumů.

Každá další rešerše musí mít konkrétní otázku, důvod a podmínku ukončení. Pokud nepřináší nové podklady, zaznamenej mezeru a pokračuj dostupnou prací. Nevytvářej nekonečnou smyčku obecného výzkumu.

Samotný počet důkazů ani štítek „reálné“ není důkazem správnosti závěru.

## 7. Zachovej význam pláten a vytvoř srozumitelný model

Načti aktuální navigaci a skutečné typy pláten. Zachovej dohodnuté oddělení pravidel a ovládání, cílového chování produktu, detailního zadání a provozních poznatků.

Respektuj samostatnou Rešerši mezi Velínem a Textem a její návaznost na Strukturu. Ověř, jak jsou tyto významy nyní reprezentované v kódu; nenahrazuj současnou aplikaci historickým číslováním pláten.

Použij oblasti, sektory a uzly tam, kde odpovídají obsahu. Podle potřeby podporuj významy:

- cíl a požadavek;
- scénář a obrazovka;
- komponenta a její stavy;
- operace a rozhraní;
- datová entita a životní cyklus;
- výzkum, zjištění a důkaz;
- rozhodnutí a alternativa;
- otevřená otázka a riziko;
- milník, úkol a ověření;
- relace agenta a její výsledek.

Není nutné pro každý význam zavést nový nativní typ. Nejprve prověř existující typy a metadata.

Každý prvek musí mít stabilní ID, jasný název, účel, původ, stav a odpovídající detail. Karta v přehledu má ukazovat pouze informace potřebné k orientaci; úplný detail musí být dostupný na vyžádání.

Každá vazba musí mít existující zdroj a cíl a konkrétní význam, například:

- rozpracovává požadavek;
- vychází z důkazu;
- závisí na;
- předává data;
- čte nebo zapisuje;
- vyžaduje oprávnění;
- ověřuje;
- nahrazuje dřívější rozhodnutí.

U datového toku popiš předávaná data a podmínku předání.

Odděl graf pořadí práce od grafu chování aplikace. Závislosti realizace nesmějí obsahovat neřešitelný cyklus; provozní proces může mít smysluplnou smyčku.

Canvas, detail karty a zadání předané agentovi musí zobrazovat tentýž model a tutéž revizi.

## 8. Připrav konkrétní úkoly pro programování

Každý úkol označený jako připravený pro agenta musí podle relevance obsahovat:

- ID úkolu, projektu, cíle a revizi zadání;
- konkrétní problém a očekávaný výsledek;
- rozsah práce a hranice, které se nemají měnit;
- vazbu na požadavek a přijatá rozhodnutí;
- současný stav doložený aktuálním kódem;
- dotčené části frontend/backend/databáze;
- ověřené cesty, rozhraní a datové struktury;
- konkrétní implementační kroky a důvod jejich pořadí;
- vstupy, výstupy, validace a chybové výsledky;
- závislosti a konkrétní blokující otázky;
- pravidla oprávnění a souběhu;
- migrační postup a návrat, pokud se mění data nebo kontrakty;
- očekávané chování UI a odkazy na skici;
- akceptační scénáře a potřebné důkazy;
- způsob předání výsledku.

Názvy existujících souborů a rozhraní musí být ověřené proti konkrétní revizi repozitáře. Navržené nové soubory nebo kontrakty jako návrh označ.

Kroky typu „dodělat backend“, „napojit frontend“ nebo „otestovat“ samy o sobě nejsou dostatečné. Rozepiš je tak, aby agent znal místo změny, očekávaný kontrakt, relevantní stavy a způsob ověření.

Rozklad musí vycházet ze skutečných závislostí a samostatně ověřitelných výsledků. Počet karet není měřítkem kvality plánu.

Po přijetí návrhu vytvoř navázané úkoly ve Struktuře. Přípravu úkolu, jeho převzetí agentem a spuštění realizace drž jako rozlišitelné události.

## 9. Podporuj více agentů a pokračování mezi relacemi

Každá práce musí mít dohledatelného vlastníka, běh a relaci.

Zajisti:

- jednoznačné převzetí úkolu;
- rozlišení vlastníka od dalších spolupracujících agentů;
- detekci kolizní práce nad stejnými částmi;
- označení přerušeného běhu a řízené převzetí;
- ochranu před zápisem ze zastaralé relace;
- předání skutečného rozpracovaného stavu.

Nová relace musí umět načíst pracovní balíček obsahující:

- aktuální cíl a relevantní výřez grafu;
- přijatou revizi zadání;
- související rozhodnutí a důkazy;
- skutečně dokončené a rozpracované kroky;
- aktuální revizi kódu, případně větev nebo pracovní kopii;
- provedená ověření a jejich výsledky;
- nalezené problémy a odmítnuté varianty;
- nejbližší další krok.

Do každé relace neposílej automaticky celý projekt a celou historii. Udržuj stručný přehled a načítání detailů podle potřeby.

Při změně požadavku nebo rozhodnutí označ dotčené úkoly, předávky a ověření k novému posouzení. Nesouvisející dokončenou práci zachovej.

## 10. Nové funkce, tlačítka a skici přidávej podle konkrétní potřeby

Můžeš vytvořit nové funkce, ovládací prvky, typy karet nebo pohledy, pokud řeší doloženou mezeru a zlepší orientaci agentů nebo předání práce.

U každého nového prvku musí být jasné:

- jaký problém řeší;
- kdo jej používá;
- jaká data potřebuje;
- jakou operaci vyvolá;
- co změní v uloženém modelu;
- jak se pozná úspěch, chyba a čekání;
- jak tutéž operaci vyvolá Srdce;
- na jaký požadavek navazuje.

Posuď například pohledy nebo akce:

- co může agent dělat nyní;
- co konkrétní úkol blokuje;
- zobrazit podklady rozhodnutí;
- porovnat změnu plánu;
- připravit předávku;
- převzít úkol;
- pokračovat v nové relaci;
- připojit důkaz dokončení;
- zobrazit další krok.

Jde o možné prostředky, nikoli povinný seznam nových tlačítek. Znovupoužij existující funkce, pokud už problém řeší.

Pokud je pro zadání potřeba vzhled nebo interakce, vytvoř na kreslicím plátně propojenou skicu. Zachyť relevantní výchozí, prázdný, načítací, chybový a úspěšný stav a přechody mezi nimi.

Skica musí být svázaná s požadavkem a implementačními úkoly. Statický obrázek není důkaz, že je funkce implementovaná.

## 11. Použij aktuálních pět výzkumných témat AmpleLab

Níže uvedená označení V1–V5 jsou pracovní označení tohoto zadání. Skutečná ID výzkumů dohledáš v aplikaci.

### V1 — Izolace organizací, retrieval a cache

Výpis uvádí dva důkazy, druhé kolo, stav zadáno a jednu zpětnou vazbu.

Dohledat a zpracovat témata:

- RLS pro tabulky s `organization_id`;
- JWT claims v `app_metadata`;
- role `authenticated` a `service_role`;
- indexy a použití `(select auth.jwt())`;
- `vector(1024)` versus `halfvec`;
- HNSW s filtrem projektu;
- dostupnost a chování iterative index scans;
- verzování klíče cache odpovědí při reindexaci.

Rozděl tento široký výzkum do souvisejících rozhodnutí a návazných úkolů. Zachovej společné důkazy a nevytvářej jejich nezávislé kopie.

Ověř význam stavu druhého kola a zpětné vazby. Nepřepínej jej mechanicky na hotovo podle počtu odkazů.

### V2 — Návrh 17 obrazovek a sedmi fází

Výpis uvádí nula důkazů a hotovo.

Dohledat skutečný návrh a porovnat ho s routami, komponentami a chováním aplikace, včetně `App.tsx`.

Vytvořit mapování:

**navržená obrazovka nebo sekce → skutečná route a komponenta → doložený stav → chybějící část → odpovídající úkol.**

Existence route sama o sobě nepotvrzuje dokončenou obrazovku ani její funkčnost.

Názvy sedmi fází a sedmnácti obrazovek převezmi z podkladů. Nevymýšlej je.

### V3 — Verze embeddingů a přepnutí aktivní sady

Výpis uvádí tři důkazy a hotovo.

Zachovej porovnání variant:

- samostatná tabulka `kb_chunk_vectors` se sadami;
- další embeddingový sloupec na `kb_chunks`.

Odděl změnu modelu při stejné dimenzi od změny samotné dimenze. Ověř slučitelnost typu sloupce, indexů a dotazů s oběma případy.

Zpracuj rozhodnutí a navazující plán pro:

- vytvoření nové sady;
- průběžné doplnění dat;
- kontrolu její připravenosti;
- konzistentní přepnutí aktivní sady;
- souběžné čtení během přepnutí;
- návrat na předchozí sadu;
- navázání retrievalu a cache na správnou revizi;
- zachování původních dat podle přijatého retenčního pravidla.

Nepovažuj výzkumnou variantu za přijatou architekturu bez doloženého rozhodnutí.

### V4 — Kvalita odpovědí, latence a cena

Výpis uvádí nula důkazů a hotovo.

Dohledat skutečné logování a dostupná data. Z nich odvodit:

- přesné definice metrik;
- místo a okamžik měření;
- vazbu na projekt, odpověď a použitou konfiguraci;
- testovací nebo referenční data pro kvalitu;
- rozlišení automaticky měřené hodnoty a hodnoticího úsudku;
- zobrazení výsledků a návazné úkoly.

Neznámé hodnoty zobrazovat jako neznámé. Nepoužívat vymyšlená čísla jako měření.

Základní měření latence nebo ceny nemusí čekat na všechny části hodnocení citací, pokud skutečné závislosti umožňují samostatný postup.

### V5 — Lokátory zdrojů a kompatibilita retrievalu

Výpis uvádí jeden důkaz a hotovo.

Ověřit relevantní části:

- `backend/core/knowledge/knowledge_types.py`;
- `backend/rag/indexing/indexing_phase.py`;
- `database/supabase/migrations/0044_match_kb_chunks_model.sql`;
- příslušnou migraci `0025_derived.sql`;
- skutečný kontrakt pětargumentové `match_kb_chunks`.

Zpracovat návrh přenosu `section_id`, `page_number`, `source_url` a `anchor` od indexace přes uložení a retrieval až k citaci v odpovědi.

Doložit dopad na typy, chybějící lokátory, kompatibilitu volajících, filtrování a pořadí výsledků. Změnu metadat neoznačovat automaticky za bezdopadovou.

### Společný výstup těchto témat

Každé téma musí mít na canvasu dohledatelné:

- zjištění nebo konkrétní mezeru;
- podklady;
- návrh rozhodnutí;
- dotčené požadavky;
- návazné úkoly a jejich připravenost;
- závislosti;
- způsob ověření.

Technické otázky ověřuj proti aktuální revizi repozitáře a skutečně používaným verzím. Jako primární zdroje použij zejména:

- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://supabase.com/docs/guides/api/custom-claims-and-role-based-access-control-rbac
- https://github.com/pgvector/pgvector

Veřejná dokumentace dokládá vlastnosti technologie; sama nedokládá stav této aplikace.

## 12. Postupuj po ověřitelných milnících

**M0 — Doložená příčina zastavení.**  
Je identifikované místo, kde se současný průchod přerušuje, a existuje inventář dostupných a chybějících schopností.

**M1 — První skutečný zápis.**  
Srdce převezme konkrétní podklad, vytvoří část návrhu s vazbami, uloží ji, zpětně načte a zobrazí v aplikaci. Stav přežije obnovení stránky.

**M2 — Úplné ovládání zjištěného rozsahu.**  
Všechny operace z inventáře mají funkční způsob použití Srdcem, včetně validace, oprávnění a chyb. Pro operace vyžadující přijetí existuje použitelná cesta návrhu.

**M3 — Aktuální výzkumy jsou zapracované.**  
V1–V5 jsou propojené s konkrétním plánem. Chybějící důkazy a rozhodnutí jsou viditelné a blokují jen příslušné části.

**M4 — Zadání a relace agentů navazují.**  
Agent obdrží konkrétní pracovní balíček, práce má jednoznačné vlastnictví a nová relace dokáže pokračovat z uloženého stavu.

**M5 — Ověřený průchod a přehledné UI.**  
Jsou ověřené změny modelu, vykreslení, potřebné skici, předávka a obnova po chybě. Nové ovládací prvky mají prokazatelný účel.

Po každém milníku aktualizuj skutečný stav na plátně. Neponechávej dokončenou práci pouze v závěrečné odpovědi agenta.

## 13. Akceptační scénáře

Proveď a dolož alespoň následující scénáře:

1. **Výzkum bez důkazu:** běh může skončit, ale závěr zůstane neověřený a vytvoří konkrétní mezeru.
2. **Částečně dokončený výzkum:** dostupné závěry se promítnou do návrhu, nezávislé části pokračují.
3. **Zápis a obnovení stránky:** uložené prvky, vazby a stavy se po načtení zachovají.
4. **Opakování po timeoutu:** nevzniknou duplicitní karty, oblasti ani úkoly.
5. **Dvě relace nad stejnou revizí:** konflikt je rozpoznaný a změny se neztratí.
6. **Jiný projekt nebo organizace:** neoprávněné čtení a změna jsou odmítnuté.
7. **Nové zjištění vůči přijatému plánu:** vznikne dohledatelný návrh změny; původní přijatá revize zůstane zachovaná.
8. **Přijetí návrhu:** vzniknou správně navázané úkoly ve Struktuře bez duplicit.
9. **Převzetí úkolu více agenty:** vlastník a související běhy jsou jednoznačné.
10. **Pokračování v nové relaci:** agent načte správnou revizi, dosažené výsledky, blokace a další krok.
11. **Změna podkladu:** dotčené předávky a ověření se označí k novému posouzení; nesouvisející práce zůstane zachovaná.
12. **Aktuální případ AmpleLab:** všech pět témat má skutečné propojení na canvasu a odpovídající připravenost další práce.

Přijetí a předání otestuj v testovacím projektu, pokud aktuální návrh ještě nebyl uživatelem přijat. Stav ostrého plánu nepovyšuj kvůli testu na schválený.

## 14. Podmínky dokončení a závěrečná předávka

Tento /goal uzavři jako dokončený až tehdy, když:

- je doložená a opravená příčina zastavení;
- Srdce umí používat ověřený rozsah funkcí canvasu;
- aktuální návrh existuje v uložených datech a je viditelný v aplikaci;
- výzkumy mají skutečné vazby na rozhodnutí a plán;
- připravené úkoly obsahují konkrétní zadání pro programování;
- stav a kontext práce přežijí změnu relace;
- byly provedené relevantní akceptační scénáře;
- zbývající produktová rozhodnutí jsou jasně označená.

Závěrečná předávka musí obsahovat:

1. Skutečnou příčinu původního problému a provedenou opravu.
2. Přehled doplněných schopností a změněných částí aplikace.
3. Odkazy nebo skutečná ID vytvořených a aktualizovaných prvků canvasu.
4. Revizi plánu a relevantní revizi kódu.
5. Příklad konkrétního zadání předaného agentovi.
6. Výsledky ověření včetně neúspěchů a omezení.
7. Přehled částí připravených k práci, blokovaných částí a důvodů.
8. Nejbližší konkrétní další krok.

Pokud narazíš na chybějící přístup nebo skutečnou blokaci, uveď přesné místo, důkaz a nutnou podmínku pokračování. Pokračuj v ostatní dostupné práci. Nedostupný zápis neoznačuj jako provedený.

Výsledkem musí být fungující schopnost Srdce stavět a udržovat plán na canvasu a konkrétní aktuální plán, podle kterého se agenti dokážou orientovat a navazovat mezi relacemi.