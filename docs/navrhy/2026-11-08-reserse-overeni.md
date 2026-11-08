# Rešerše — ověření implementace

## Navazující realizace 8. listopadu 2026

Izolovaná větev `feat/velin-reserse-realizace`, základ `96605e2a`, úkol Linie `OP-6FF3AC`.
Živý náhled: `http://127.0.0.1:8792/?mode=research`; oddělená demonstrační data,
žádné automatické sloučení ani změna produkčních dat.

- Rozhodnutí má samostatné lidské posouzení s připnutými verzemi problému a důkazů.
  Negativně ověřený zdroj se nepočítá jako doklad. Historie zachovává i rozpory.
- Převod do Struktury používá existující návrhy OporaHubu; nezapisuje přijetí za člověka.
  Existující úkol zachovává ID a zadání, opakování nevytváří další návrh.
  Po přijetí lze synchronizovat zpětné odkazy; úplný kontext je v neměnném posouzení.
- Kancelář používá původní ticket, zpětnou vazbu a relaci. Výzkumná větev připíná revizi
  zadání a odpověď konkrétní verzi důkazu; odstranění úkolu neodstraní výzkum.
- API doplňuje témata, verzované části úplného obsahu a trvalé události pro synchronizaci.
- Import zachovává všechny podklady, porovnání variant a odlišuje ověření citace od inference.
  Pletor dostane pravdivou chybu při neúspěšném předání otázky srdci.
  Dlouhé odpovědi srdce podporují `--file` bez rozšíření oprávnění shellu.
- Přímý odkaz inicializuje autorizovanou UI relaci. Historický režim zůstává pouze pro čtení.
  Inspector má vlastní scroll, na mobilu zabere obrazovku; známá výzkumná data jsou čitelná,
  úplný původní JSON je dostupný beze změn v rozbalovacím detailu.

### Důkazy nové realizace

Finální frontend: **490 souborů / 2 804 testů prošlo**, TypeScript a produkční build prošly.
Filtrovaný graf nově počítá rozmístění jen z viditelných karet a vazeb a automaticky přizpůsobuje
pohled. Browser ověřil čitelné kartičky bez ručního tlačítka Fit; ID ani uložená data se nemění.
Společná výzkumná backendová sada po závěrečných doplněních: **217 testů prošlo** za 114,82 s
(`research-tests-audit.log`). Dřívější test závislý na nesledované místní REA konfiguraci používá
izolovaný fixture; celý společný běh nyní prošel najednou.
Úplná backendová sada doběhla: **6 267 prošlo, 5 selhalo, 17 přeskočeno** za 4 018,67 s
(`backend-tests.log`). Běh začal před závěrečnými opravami a načetl jejich starší podobu.
Přesné opakování všech pěti selhavších testů pomocí `--lf` na aktuálním HEAD následně skončilo
**5 prošlo** za 6,45 s (`backend-failed-rerun.log`). Jde o kombinované ověření plné sady
a oprav, nikoli o jeden čistý plný běh. Vedle společné výzkumné sady (217 testů) prošly celé
dotčené moduly srdce (86 testů) a dokumentace (11 testů). Zbývajících **17 přeskočených testů**
není započteno jako úspěch; jejich externí pokrytí zde není tvrzeno.
Samostatný audit přeskočení (`backend-skip-audit.log`: **109 prošlo, 17 přeskočeno**, 49,59 s)
doložil důvody: 12 nesouvisejících evaluací `opora-vs-bare` nemá Python modul `playwright.sync_api`,
3 testy nemohou pod tímto uživatelem Windows vytvářet symbolické odkazy a 2 testům chybí
připnuté PR Lens CLI. Browserové ověření Rešerše popsané níže používá Node Playwright
a skutečně proběhlo; chybějící Python modul se tohoto ověření netýká.
Při jejím průběhu byly opraveny dva zastaralé předpoklady testů (počet importovaných variant
a systémový prompt s výzkumnými instrukcemi); dotčené moduly prošly samostatně.
Kontrola dokumentace API původně selhávala také na výchozí větvi. Po doplnění výzkumných cest
zbývalo 61 starších nálezů. Ty jsou nyní pravdivě zdokumentované podle skutečných routerů
ve stávajícím `references/routy.md`; celý `test_skill_docs.py` prošel (11 testů).
Kontrola nebyla oslabena a chování nesouvisejících API se nezměnilo.

Playwright nad skutečnou sestavenou aplikací a API ověřil 11 interakcí: lidské posouzení,
návrh úkolu, obnovení stránky, OporaHub, testovací nativní přijetí, synchronizaci zpětných vazeb,
historický read-only detail, hledání, detail hrany, archivaci/obnovu a mobilní zobrazení.
Tento tok na portu 8794 je **syntetický scénář**, nikoli schválení skutečného projektu.
Čerstvé browser contexts na 8794 a 8792 fungují bez ruční inicializace cookie a bez JS chyb.

Na portu 8792 běžel **skutečný model Pletora a srdce**. Pletor založil `pq_6c9676327ef5`;
srdce použilo stávající výzkumný stůl a uložilo tři výzkumy: data
`94bf6c4fe11345be8348d4d9fe0f023b`, UX `7356d9129a5b4baeb8d758fb365b90c9`
a autentizační logika `32252c1e450d4d169b870c1fe4c504bd`. Kontrola citací: 12/12, 12/12,
10/12. Shoda citace není automatické potvrzení správnosti výkladu.
Odpověď se skutečně doručila přes `pletor-answer --file`. Navazující modelový tah uložil
varianty A/B/C a podmíněné rozhodnutí `rc_b6f1c9e3a2d84b7f9c0e5d48` jako inference bez
lidského schválení. Read-only kontrola skutečného API a browseru existenci potvrdila.
Čtyři starší karty mají revizi 2: v původním JSON se změnilo jen vnořené `verified` na
`inference`; tvrzení, citace a zdroje zůstaly zachovány, revize 1 je nadále dostupná.
Pletor následně přes skutečný model přečetl rozhodnutí/varianty a část důkazů a v odpovědi
rozlišil inference, podmínky i nepřečtené podklady. Nepřečetl celou 128k rešerši; toto omezení
ve výsledku výslovně přiznal. Živý průchod nepředstírá lidské přijetí ani realizaci úkolů.

Artefakty v `C:/Users/Admin/AppData/Local/Temp/opora-browser-proof/`:
`research-ui-result.json`, `research-fresh-context-result.json`,
`research-live-detail-1440.png` (živá data), `research-final-accepted-390.png` (testovací data),
`live-heart-decision-1440.png`, `live-heart-variants-1440.png`, `live-heart-final-proof.json`,
`live-pletor-research-1440.png`, `live-pletor-transcript.txt`, `research-filter-proof.json`,
`research-direction-counts.json`, `research-direction-counts-1440.png`, `research-source-location-1440.png`,
`pletor-final-result.json`, `frontend-tests-final.log`, `backend-tests.log`, `backend-failed-rerun.log`,
`research-tests-final.log`, `research-tests-audit.log`, `backend-skip-audit.log`.

Následující části zachycují předchozí implementační etapu; její omezení neživého modelového
ověření jsou překonána výše uvedeným živým průchodem, nikoli syntetickým přijetím úkolů.

### Kontrola konkrétních požadavků cíle

| Požadavek | Implementace a přímý důkaz |
|---|---|
| Audit a opětovné použití (§3) | Výzkum používá stávající `opora_research`, Schránku a ověřování citací; návrhy používají `OporaGraphProposals`/`OporaChangesets`, odpovědi nativní ticket gate. `test_research_realization.py` kontroluje skutečné přijaté dokumenty a původní relaci. |
| Navigace a nezávislé téma (§4) | Skutečné screenshoty App: pořadí Struktura, Velín, Rešerše, Text, Kreslení, Kancelář, Storyboard. `research-model` rozmisťuje výzkumné karty, nikoli uzly Struktury. `test_reads_events.py` ověřuje hierarchii témat. |
| Stabilní ID, úplný obsah, návaznosti (§5) | `test_research_routes.py` ověřuje změnu názvu, CAS, historii, archivaci a nezkrácený obsah/citace; `test_reads_events.py` rekonstruuje části s připnutou revizí a scope. `test_relation_headers.py` ověřuje odvozené příchozí/odchozí počty bez změny uložené revize; browser potvrzuje skutečné zobrazení. |
| Významové vazby a oddělené schválení (§6) | Hrany nesou typ, směr, reason, resolved, missing a evidenceIds. `test_closure_context.py` vynucuje kontext skutečného uzavření; uzavření rozhovoru není řešení problému. Historické vazby zůstávají čitelné. Lidské posouzení je samostatný neměnný záznam, nativní přijetí plánu zůstává oddělené. |
| Pletor a Srdce (§7) | Živé artefakty `heart-finish.json`, `pletor-final-result.json` a `live-pletor-transcript.txt`; modely skutečně používaly API/CLI. Čtení má explicitní limit a Pletor přiznal nedočtené části. Syntéza variant je inference, citace se ověřují proti získaným zdrojům. |
| Zdroje a vizuální podklady (§8) | `test_opora_research_map.py` zachovává všechny nálezy ze stejné URL, stavy, refs, čas videa, revizi a umístění kódu. Tentýž modul ověřuje ukládání přílohy přes existující Kreslení. `research-source-location-1440.png` ukazuje umístění v detailu zdroje; původní JSON zůstává celý dostupný. |
| Realizační úkoly (§9) | `test_decision_tasks.py` ověřuje nový i existující úkol, závislosti, připnutý původ, retry/recovery a skutečné přijetí v nativním úložišti. UI scénář ověřuje lidské posouzení, návrh, přijetí pouze ve fixture a synchronizaci zpětných refs. |
| Návrat z Kanceláře (§10) | `test_ticket_bridge.py` a `test_research_realization.py` ověřují původní ticket, feedback, verzi zadání, session, připnutou odpověď a idempotentní doručení. Jiná relace odpověď nedostane. |
| API, izolace, trvalost (§11) | `test_research_routes.py`, `test_reads_events.py` a rozhodovací testy ověřují scope tokenů, odmítnutí worker zápisu, atomické operace, neexistující reference, snapshoty a opakované události. Oddělený ask/batch zachovává dlouhou výzkumnou práci. |
| Celý scénář (§12) | Živá otázka přihlášení vytvořila UX, autentizaci a datové podklady, varianty i doporučení. Následná realizace a návrat z Kanceláře jsou integrační test se syntetickými důkazy, ne tvrzené živé schválení. Odstranění realizovaného úkolu zachová výzkum, review i původ ticketu. |
| Ověření gate (§13) | Frontend, build a browser prošly. Plná backendová sada: 6 267 prošlo, 5 selhalo, 17 přeskočeno; všech pět selhání po opravách prošlo při přesném opakování na aktuálním HEAD. Celé cílené sady: 217 výzkumných, 86 srdce a 11 dokumentačních testů prošlo. Je doložen kombinovaný výsledek, nikoli jeden čistý plný běh; 17 přeskočených testů nedokládá externí pokrytí. |

Pracovní větev `feat/velin-reserse`, základ `f470d3e0`, 8. listopadu 2026.
Kontrakt: [Rešerše](2026-11-08-reserse.md). Kontrola původní revize:
[nálezy 7480db2](2026-11-08-reserse-review.md).

## Výsledek

- Všechny pohledy v jednom řádku; Rešerše mezi Velínem a Textem.
- Tematický canvas, směrované vztahy s důvodem, vyřešeným a chybějícím kontextem.
- Hlavičky a úplný detail; zdroje, citace, platformy, vizuální přílohy, historie a archiv.
- Trvalý zápis srdce, atomické dávky, ochrana před souběžným přepsáním a opakovaným importem.
- Pletor čte podle ID a tématu; pokračování kontroluje stejnou revizi dat i prostor.
- Otázky, upřesnění, odpovědi a uzavření se obnovitelně promítají z deníku rozhovoru.
- Podklady nesou ID otázek, ticketů, relací a úkolů. Dosavadní rozhodování a schvalování zůstává platné.

## Provedené kontroly

- `npm test`: **488 souborů, 2 793 testů prošlo**.
- `npm run build`: TypeScript i produkční sestavení prošly po poslední úpravě stylů.
- Společná cílená backendová sada: **98 testů prošlo**. Zahrnuje API, zápis/čtení srdce,
  modelové transporty Pletora, pokračovací čtení, historii, oprávnění a deník otázek.
- Dodatečný test skutečného ticketového toku prošel: existující úkol → ticket → otázka pracovníka →
  rešerše s ID úkolu/ticketu/relace → odpověď srdce → doručení původní relaci. Jiná relace odpověď nezíská.
  Samotný zápis podkladů nemění plán ani neodpovídá za srdce.
- Dodatečné kontroly čtení ověřují odmítnutí pokračování v jiném prostoru a při změně dat.
- Chromium/Playwright: skutečné komponenty nad izolovanými testovacími odpověďmi, šířky 1440/640/390 px.
  Ověřeny všechny pohledy, lazy detail, dlouhý obsah, citace, hrany, historie, filtry, archivace/obnova,
  screenshot, chybějící příloha a předání odkazu do Struktury/Kreslení. Bez chyb JavaScriptu a přetečení stránky.
  Nalezený tmavý podklad canvasu ve světlém motivu opraven. Jde o komponentový test, nikoli celou běžící App.

Globální kontrola repozitáře má zděděné nálezy: Ruff **144 proti 147** v čistém základu; dokumentace
**496 proti 498**; struktura v obou případech 160 délkových nálezů, 12 umístění a 5 chybějících README.
Nové moduly nepřidávají nálezy. Staré limity v nástroji verify těmto hodnotám neodpovídají; nebyly přepsány.
Celá backendová sada byla po rozšíření nad rámec cílených kontrol zastavena; její úplný průchod netvrdíme.

## Hranice ověření a provozu

Testy nespouštějí placenou živou rešerši ani nepotvrzují kvalitu konkrétní odpovědi skutečného LLM.
Existující výzkumný stůl má vlastní limity sběru; nová paměť zachovává celý jeho vydaný výsledek.
Pletor má limit 12 čtení za tah a konečný kontext; nedočtený obsah přizná, další tah automaticky nenavazuje.
Screenshot se ukládá do úložiště Kreslení; vložení do konkrétní scény je samostatná existující operace.
Starší otázky bez připnutého prostoru zůstávají ve svém původním prostoru. Nové otázky prostor připnou při vzniku.

Schéma je přídavné. Návrat ke starému kódu nesmaže nové tabulky ani jejich historii.
Git commity jsou uloženy na pracovní větvi; přijetí, sloučení a nasazení nebylo provedeno.
Pokus o čtení evidence pomocí `linie.py trace` s identitou agenta server odmítl HTTP 403
(krok pouze pro člověka v UI). To neblokuje autorizovanou práci ve větvi a není to důkaz zobrazení či přijetí úkolu.
