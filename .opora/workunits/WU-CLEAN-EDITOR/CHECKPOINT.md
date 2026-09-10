# WU-CLEAN-EDITOR — desktopový náhled ověřen

## Cíl a hranice
Uživatel navrhuje funkce bez znalosti souborů. Projekt / Kód 1:1 zůstává skutečný filesystem; Editor / Stavba aplikace dovoluje konceptuální sektory a uzly bez sourceRef. Nic neklasifikujeme jako nepoužívaný kód bez analýzy a nic nemažeme z disku.

## Změna
- `workspace_sources.py`: kompatibilní default API `visibility=all`, UI explicitně používá `working`; běžný přehled skrývá technické adresáře, .env a pravidla .gitignore včetně negací a zanoření. Filtrace před stránkováním, src první, backend druhý. Neplatný filtr a nebezpečné cesty se odmítají.
- `SourceExplorer.tsx`: explicitní přepínač úplného stromu, informace o filtru a nulových filesystem změnách.
- `App.tsx`: volba `Jen funkce / myšlenka, bez souboru` pro sektor i uzel. Zdrojově vázané režimy a jejich guardy zachovány.
- `EnvironmentSwitch.tsx`: Projekt / Kód1:1, Editor / Stavba aplikace, Live Run zachován.
- Skutečný projekt `4b38182c5b04482bb00e0f3d3ae55656`: všech403 starých uzlů zachováno v Technické mapě. Přidány dva oddělující sektory, čtyři funkční oblasti a prázdný sektor Nové nápady — zelená louka. Celkem410. Doložené vazby na existující zdrojové uzly.

## Důkazy
- Backend RED pozorován před implementací filtrování. Full pytest:265 PASS,4skip,2 deprecation warnings.
- Nové UI RED pozorováno před implementací. Závěrečná sada:92 PASS,1skip,0fail,0flaky.
- Ruff a TypeScript PASS. `git diff --check` PASS.
- První kombinovaná UI sada použila nesprávný port/fixture; druhá ještě četla manifest starého živého buildu. Opraven pouze testovací harness: původní bezpečnostně fixované porty a fixture, explicitní OPORA_TEST_DIST pro izolovaný sestavený frontend. Žádný test nebyl přeskočen kvůli selhání.
- Nezávislá statická review bez dalších security/race nálezů. CE-1 (konceptuální sektor) po nezávislé kontrole kontraktu odvolán: sektor není filesystem oprávnění. Přidán přímý E2E sektor+potomek+zakázaná existující vazba. Claude evidence-only review timeout; NENÍ označeno jako Claude PASS.
- Před nasazením SQLite backup s integrity_check a kopie původního dist. Restart pouze vlastního8768, bez aktivních potomků/běhů. Nový source/frontend hash a nezměněné původní DB tabulky po restartu ověřeny.
- Přeskupení nejprve prošlo skutečným API izolované fixture, poté CAS zápisem a přesným readbackem cílového projektu. Dokumentace/deník přečteny zpět.
- Live UI na8768: pět funkčních karet, prázdná zelená louka, dostupná bezsouborová volba, filtrovaný strom1:1 se src první.0 page errors,0 API writes,0 model starts během ověření. Screenshoty zkontrolovány.

## Artefakty
`C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/`
- `clean-editor-backend-gate.json`, `clean-editor-ui-final.json`
- `clean-editor-review.json`, `clean-editor-adjudication.json`
- `clean-editor-delivery/{runtime-before.json,runtime-after.json,canvas-before.sqlite,graph-before.json,graph-after.json,live-ui-result.json}`
- `clean-editor-delivery/live-{build,greenfield,code}.png`

## Stav a omezení
Lokálně nasazeno do stejného desktopového náhledu8768 ve worktree `feat/isolated-document-task`; toto není tvrzení o GitHub merge ani čistém release commitu. Předchozí necommitnutý WU-DOCUMENT-TASK zůstává zachován.8750 a8740 nedotčeny.
Filtrace není autorizace souborů ani detekce mrtvého kódu. Graf je importovaná mapa, nikoli automatická synchronizace nových souborů. Bezsouborový uzel sám nespouští implementaci. Obecná coding orchestrace a stream této Telegram relace do Live Run zůstávají mimo tento úkol.
