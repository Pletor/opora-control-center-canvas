# Srdce → canvas → agent: kontrakt a evidence dokončení

Úkol Linie `OP-086DEE`, větev `feat/velin-linie-plan`, základ kódu `70131036f141e6dd5d90d7842f6fd8877cf466eb`. Úplný rozsah je v [původním zadání](2026-11-08-srdce-canvas-amplelab-zadani.md); tato evidence jej nezužuje. Výchozí stav všech požadavků je **neprokázáno**.

Návrh produktu není jeho přijetí ani realizace. Nezměněné karty, ID, historii, zdroje a přijaté revize zachováme. Zápisy musí používat autoritativní doménové operace; ověření uloženého výsledku je povinné. Hledání ani zelený dílčí test samy neprokazují celý milník.

## Milníky a důkazy

| Milník | Nutný důkaz | Stav |
|---|---|---|
| M0 | Aktuální běh: poslední úspěšný a první chybějící krok; konkrétní události, kód, data; konečný inventář všech 12 kategorií operací | doloženo v diagnóze a inventáři; oprava ještě ověřována |
| M1 | Srdce z konkrétního podkladu uloží malý návrh s vazbami; zpětné načtení přes API a obnovená stránka | neprokázáno |
| M2 | Každý řádek inventáře má nástroj, vstup/výstup, hranice oprávnění, chyby a ověření; pohled relace oddělen od plánu | neprokázáno |
| M3 | Skutečné V1–V5, jejich historie, důkazy i mezery propojeny s požadavky, rozhodnutími, úkoly a ověřením | neprokázáno |
| M4 | Neměnný pracovní balíček, jednoznačný vlastník, konflikt dvou relací, pokračování z rozpracovaného stavu | neprokázáno |
| M5 | Celý průchod, obnovení po chybě, relevantní skici, přehledné UI, testy i doložená omezení | neprokázáno |

## Akceptační scénáře

| # | Scénář | Autoritativní důkaz | Stav |
|---|---|---|---|
| 1 | Dokončený výzkum bez důkazu není ověřený závěr | uložené oddělené stavy + konkrétní mezera | neprokázáno |
| 2 | Částečný výzkum umožňuje nezávislý postup | návrh a jen skutečné blokující závislosti | neprokázáno |
| 3 | Zápis přežije reload | API před/po, revize, prohlížeč | neprokázáno |
| 4 | Retry po timeoutu bez duplicit | stejný identifikátor operace a stejné skutečné ID | neprokázáno |
| 5 | Dvě relace nad stejnou revizí | konflikt druhého zápisu, zachovaný první | neprokázáno |
| 6 | Jiný projekt/organizace | odmítnuté čtení i zápis cizí identitou | neprokázáno |
| 7 | Nové zjištění vůči přijatému plánu | návrh změny, nezměněná přijatá revize | neprokázáno |
| 8 | Přijetí vytváří správné úkoly bez duplicit | izolovaný testovací projekt, vazby a opakování | neprokázáno |
| 9 | Převzetí více agenty | jediný vlastník, rozlišení spolupráce a kolize | neprokázáno |
| 10 | Nová relace pokračuje | revize, kroky, problémy, ověření a další krok v balíčku | neprokázáno |
| 11 | Změna podkladu zneplatní jen závislé předávky | dotčené revize vyžadují nové posouzení, ostatní zachovány | neprokázáno |
| 12 | AmpleLab V1–V5 | skutečná ID a vazby v živém návrhu, připravenost každé části | neprokázáno |

## Povinná úplnost závěrečné předávky

Před uzavřením porovnat skutečný stav se všemi odstavci úplného zadání, nejen s touto tabulkou. Předávka musí obsahovat příčinu a opravu, inventář schopností, skutečné ID, revizi plánu a kódu, konkrétní pracovní balíček, výsledky všech scénářů i neúspěchy, připravené a blokované části a nejbližší další krok. Úplné `pytest backend`, `npm test`, `npm run build` a praktické ověření aplikace se evidují s přesným rozsahem.

## Průběžná evidence první implementace (není uzavření M1)

- Výchozí data Ample zálohována před zápisem: `P:/opora-data/backups/before-heart-plan-20261108`, SQLite quick_check OK; manifest 209 souborů. Přijatá hlava před změnou `1941c57790454d32f91d2cb0040b6adef598cc50`.
- CLI ukládá návrh výchozím způsobem bez přijetí; první požadavek s revizí žurnáluje před odesláním. Návrh a zpětné načtení mají oddělené výsledky.
- Nativní zápisy mají volitelný identifikátor operace vázaný na projekt, prostor, autora a obsah. Při přerušeném vícekrokovém zápisu Canvasu zůstane `operation_incomplete`; automatická obnova zatím není provedena.
- UI promítá uložený návrh do plátna pouze ke čtení. Hluboký odkaz zahrnuje projekt, prostor a ID návrhu. Praktické ověření probíhá.
- `npm test`: 496 souborů, 2838 testů prošlo. `npm run build`: prošlo (varování o velikosti bundlu). Úplné `pytest backend` stále běží; výsledek zatím neznámý.
- Tyto výsledky ještě nedokládají skutečný průchod Srdcem nad Ample ani milníky M2–M5.
### Izolované praktické ověření M1

Nativní testovací projekt na portu 8793: návrh `52ce19c525860204b16b26ee2674e1fa625691f0`, uzly `24242bc8-bab3-41a4-866a-4538ccc71386` a `36a8ef43-2326-497e-a080-a8c781f41324`. Playwright ověřil tři vykreslené uzly (včetně přijatého základu), jednu vazbu, detail zadání a obnovení stránky. Přijatá hlava před i po `12a24e6cb37d56098bd15024a756ae95a1fdec16`; digest před i po `5f2024951cee0b41282f90f8cd892620e259734c89f4bd9606f69711fbedd374`. Návrh nepřijat. Jde o syntetické API ověření, nikoli o skutečný běh Srdce nad Ample.

Nalezená chyba při zkoušce: App zahazovala ohGraph při přepisování URL; opraveno zachováním odkazu pouze pro totožný projekt a pracovní prostor. Readback původně porovnával jen ID; regresní případy nyní odmítají chybný název, obrácenou vazbu i chybný stav se stejnou revizí. Změna runtime instrukcí obnovuje relaci Srdce podle otisku skutečného promptu.

Rodičovský agent znovu spustil 60 cílených testů Canvas/receipt/readback/CLI/batch: prošly. Následně 102 testů CLI/replay/readback/batch: prošly. Úplná backendová sada stále není dokončena. Důkazy a screenshoty jsou v `C:/Users/Admin/AppData/Local/Temp/opora-plan-proof`.
Finální frontendová sada po opravě URL a zaměření nových karet: 496 souborů / 2840 testů prošlo. Izolovaný graf 185 přijatých + 2 navrhované karty ověřen i po reloadu; úplný graf zůstává dostupný přes ovládání přiblížení. Build prošel.

### Zjištění širší backendové sady

První úplný běh zachytil 17 selhání v integračních testech Heart. Šest modulů používalo implicitní přijetí plánu jako přípravu přijatého výchozího stavu. Přípravy dostaly výslovné `--accept`, sdílený helper si ponechal nový výchozí režim. Doplněna skutečná API kontrola výchozího návrhu bez přijetí a zachování acceptedHead=None. Dále upřesněny kontrakty implicitního aktivního workspace versus explicitního main a auditního souhrnu obsahujícího operationId.

Cílený běh po první úpravě: 26 passed / 3 failed. Odhalil i skutečnou chybu CLI: informace pro bezpečné opakování zakryla původní radu k pracovnímu prostoru. Oprava zachovává obě informace; samostatně 16 cílených testů včetně skutečných HTTP/Git workspace scénářů prošlo. Finální běh všech 29 testů šesti dotčených modulů probíhá. Původní úplný běh nelze vydávat za zelený; obsahuje již diagnostikovaná selhání a pokračuje v ostatních oblastech.
Finální opakování všech šesti dotčených integračních modulů: **29 passed** za 96,25 s. Výchozí návrh, výslovné přijetí, pracovní prostor i konkrétní chybová rada ověřeny. Kompletní sada zůstává nedokončená a její první běh obsahuje výše popsaná selhání.
