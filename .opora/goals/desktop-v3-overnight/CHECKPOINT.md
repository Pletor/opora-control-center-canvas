# Noční checkpoint — výchozí stav 2026-09-11

## Pravdivý stav
- Cílem nyní není pouze oprava jednoho testu: uživatel nově požaduje celonoční dokončení všech funkčních komponent Desktop v3, potom bod2 podle svých fotografií. Viz GOAL.md.
- Aktivní integrace `integration/desktop-v3`, HEAD `a3832dc` při založení cíle. Všechny předchozí backend/packet/UI lanes sloučené; main `31452ec` nezměněn. Původní dirty worktree na P: nezměněn.
- Necommitnutá, záměrná změna v integraci: `e2e/v2-ui-review.spec.ts`, pouze explicitní navigace přes Dohled běhů plus aserce nového hlavního regionu. Musí se otestovat a commitnout, nikoliv zahodit.
- Generated PNG evidence v integraci i starých agentních worktrees je dirty. Není to neintegrovaný kód; zachovat/archivovat, nikdy plošný reset/clean.
- Před novou CSS opravou: backend314 PASS/4skip, RuffPASS, tscPASS/buildPASS, v3 panel suite28PASS. Poslední celá legacy/document/clean-source sada: 93 tests, 81PASS/1skip, zbytek selhal na starém vstupu Live Run. Claude commit5624187 již upravil šest souborů tak, aby se nejprve ověřil nový hlavní region a explicitně otevřel Dohled běhů; původní aserce nesmazány. V2-review navigační oprava je zatím lokální. CELKOVÉ UI GREEN zatím NENÍ prokázané.
- Preview8780 běží z kopie dat, frontend/backend sjednocených podkladů publikován. Parent drawing30 prvků/revize1 ověřena přes náhled→snapshot→prepare→export včetně skutečného download tlačítka; modelStarts0. Dva skutečné návrhové výstupy v Live Run porovnány s API, 7tabů, světlo/tma a desktop widths bez errorů.

## Naléhavá nová chyba
Uživatel hlásí inspektor bez aktivovaného Wireframe. První kontrola pravého OPORA panelu samotného chybu neukázala. Po otevření módu Kreslení a výběru obdélníku se ukázal deformovaný native Excalidraw inspector vlevo: color swatches32px vysoké a úzké, opacity range32px s application-style padding/border. Hypotéza: globální OPORA pravidla v src/style.css (generic button/input/heading etc) protékají do .excalidraw. Screenshot `E/inspector-before-false.png`; reprodukční script `E/inspect-inspector.cjs` (read-only server routes; click97,308 v existující kresbě). NEDĚLAT náhodné změny rozměrů pravého panelu nebo skrývání native menu.

## Aktivní writer
Claude Code Opus `inspector-style`, spec E/inspector-style-spec.json, worktree `C:/Users/Admin/opora-v3-inspector`, branch `fix/v3-inspector-css-boundary`, process handle `proc_fe3f7116aa20`. Bounded600s/35turn/$12 cap, OAuth/Max. Výlučně src/style.css, src/drawing.css, nový e2e/inspector-style-boundary.spec.ts, vlastní handoff. RED→GREEN + screenshot + tsc + commit před koncem; test ports8742/8769/8771 rezervované této lane. Koordinátor musí stav/procesy ověřit, nespoléhat na naraci agenta. CLI outcome může být quota/limit/deadline, pak bezpečně převzít až po quiescence.

## Další kroky
1. Vyzvednout a ověřit CSS lane. Zkontrolovat přesnou příčinu a neoslabování testů. Nezávislé review.
2. Integrovat, build private dist, publish8780, ověřit běžící kresbu s vypnutým/zapnutým wireframe a doměřit menu.
3. Celá UI sada (jen jeden runner), potvrdit legacy nástroje za novou navigací, full backend pokud backend upraven. Commit v2-review asercí a checkpoint.
4. Komponentový audit skutečné684řádkové Desktopv3 předlohy a implementace chybějících funkcí, nikoliv automatické DONE po CSS.
5. Teprve po akceptaci celé fáze1 dohledat přesné fotografie a původní zadání fáze2. Zdroj zatím chybí; není dovoleno vybrat cizí náhodné fotografie nebo vymyslet bod2.

## Provoz
GOAL/STATE je trvalý. Noční monitor je `C:/Users/Admin/AppData/Local/hermes/scripts/desktop_v3_overnight_monitor.py`: stabilní stav, změny git/CLI/GOAL a dosažení quota resetu budí koordinátora. Bez změny netráví modelový rozpočet. Kvóta75%/resetza53min je uživatelův údaj; odhad02:43 CEST není garantovaný. Nepřepínat poskytovatele ani kupovat další quota bez souhlasu.
