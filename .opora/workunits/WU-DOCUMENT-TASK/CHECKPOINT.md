# WU-DOCUMENT-TASK — ověřený první průchod

## Doručený rozsah
Editor → AI nástroje → Kontext → Dokumentační úkol. Příprava uloží přesný schvalovaný task/context snapshot, samostatné potvrzení spustí instalovaný Hermes. Agent může pouze dočítat vymezený snapshot a psát `result.md` do vlastního Git prostoru. Uzel↔běh↔digest zadání je uložený. Výsledek i přesné zadání lze skutečně stáhnout; běh se obnoví z API po otevření panelu.

Nejde o obecné programování, rozdělování uzlů orchestrátorem ani celý desktop-v2 release. Pro tento typ běhu slouží panel Dokumentační úkol; ještě není obecně sjednocený s katalogem Live Run. Žádná závislost na starém Bridge/OporaCC. Stávající funkce zachovány.

## Skutečná acceptance (žádný mock)
- API8768, oddělená testovací data; model `gpt-6-astra`, provider `openai-codex`, limit60s.
- Běh `679c09fe8a6d40159d2a9f599c3f5250`: `completed`, `verification.passed=true`, lokální worker neaktivní.
- Skutečné události: tool_preflight → hermes_ready → context_read(map,documents,workspaceDocuments) → result_written → dokončení a nezávislé ověření.
- Výstup:99 slov,827 UTF-8 bajtů; SHA-256 `7df52e50d985ec23eb3b69027a7ade47e1764ad6b5c6df82e332ef2c818e0dc3`.
- Kontrolní značka nebyla v zadání; pocházela pouze z uložené dokumentace a je ve výsledku.
- Zdrojový README i jeho SHA zůstaly stejné. Výstup se do zdrojového projektu neaplikuje.
- Živá UI kontrola obnovila skutečný běh z API, stáhla dokument se stejným SHA a přesný export zadání. Nula mutujících API požadavků, nula JS chyb.
- Předchozí Git start pod dlouhou Windows cestou selhal bez modelu; opraveno lokálním `core.longpaths=true`, bez globálního nastavení. Další skutečný běh narazil na60s limit po zápisu; zůstal správně cancelled/neověřený. Oba pokusy jsou zachované v lokálních důkazech, nic se z nich automaticky nespouští.

## Gate
- 261 backendových testů prošlo,4 přeskočené (platformní/permission varianty); Windows junction byl zvlášť skutečně ověřen.
- 67 původních UI testů prošlo,1 přeskočený placený scénář.
- 11 nových UI kontraktů prošlo; tyto testy používají výslovné transport doubles, nenahrazují výše uvedený skutečný Hermes běh.
- Build/TypeScript a Ruff prošly. Přetrvávají původní deprecation/chunk-size warnings.
- Původní review nálezy pokryté opravami a regresními testy: scope/digest/export, stop/poll race, symlink/junction, mapovaná dokumentace bez ručního nodeId, zastavení vlastního procesu, Git inicializace a opakované close.
- Claude review nevydalo výsledek v limitu; žádné Claude schválení ani produkční release se netvrdí.

## Přesné hranice
Dokumentace ve snapshotu je označena jako uložený snímek bez nového ověření filesystemu. On-demand čtení znamená přístup k tomuto schválenému výřezu, nikoli libovolný disk. Časový limit není cenový strop. Timeout je cancelled, nikoli completed. Nový start vyžaduje explicitní potvrzení a aktuálnost podkladů.

Nasazení a zachování dat se dokládá zvlášť soubory preview-install/readback; samotný tento checkpoint není důkaz nasazení.
