# Clean Workspace — funkční redesign OPORA Canvas

## Pověření a role
Uživatel výslovně žádá moderní, čisté a přehledné UI; každé tlačítko má mít jasné místo a skutečnou funkci. Odmítá přemíru tabulek, formulářových panelů a velkou klikačku. Požaduje Claude Design a Fable5.1 v samostatné větvi. Model claude-fable-5-1 byl skutečně ověřen (DESIGN_FABLE_READY). Větev design/clean-workspace, base abdf852 (spojený natural abf6d89 a observability85e8199). Jeden writer Fable5.1 zde; Astra sama implementuje backend/integraci jinde a provede nezávislé převzetí.

## Claude Design — poctivé rozlišení
Projektově lokální MCP claude-design je registrován, ale get vracíHTTP403: přihlášeníClaudeCode nestačí; je třeba /design-login + přístup účtu. BEZauth nevolat cloudovýDesign, nezkoušet kopírovat tokeny, nepovolovat extrausage. Tato lane zatím používá LOKÁLNÍ workflow ze skillu claude-design. Neoznačovat svou práci za výstup hostedClaudeDesign. Po přihlášení lze přes něj získat další nezávislou vizuální iteraci.

## Kompozice před barvami
Primární surface: COMMAND / INSPECT, Explore sekundární. Hlavní je obsah/plátno, nikoli ovládací tabulky. Jedna kompaktní navigace a jedna kontextová oblast k právě vybranému obsahu. Neshromažďovat všechny formuláře stále na obrazovce. Zachovat volné plátno, přímé psaní a outliner, graf i datované deníky. Žádný hero, falešnémetriky, marketingovékarty, dekorativníikony nebo přebarvený starýlayout. Postupné odkrývání nastavení a méně trvale viditelných ovladačů, ne skrývání důležitých funkcí bez dostupné náhrady.

## Zdrojové podklady — skutečně přečíst
- START-HERE.md, src/App.tsx, aktuální globalCSS z importů src/main.tsx, workspace-modes.css, natural-canvas.css; NodePanel, TextWorkspace, BlockOutline, NodeTextEditor, NodeJournal, AgentsWorkspace, NodeActivity, ProjectHome, workspace-settings.
- .opora/workunits/WU-EDIT-SAFETY/HANDOFF.md: opravy ztráty rozepsaného textu se NESMĚJÍ přepsat.
- C:/Users/Admin/AppData/Local/hermes/skills/creative/claude-design/SKILL.md (Read jako metodika, ne hostedtool API).
- Obrázky: C:/Users/Admin/AppData/Local/hermes/cache/images/img_8028c6cb069a.jpg (Tuval kompaktní navigace a galerie); img_d9a3b7168fa6.jpg (Tuval rozsáhlé plátno/sektory a levá úzká nástrojová lišta); img_b112659f5491.jpg (Logseq graf, nikoli outliner); img_fddd93be38fc.jpg (Logseq deník s datumem, zanořeným textem a kontextovým slashmenu).
- Inspirovat se principy, nekopírovat branding ani obsah referencí. Současný OPORA obsah a identita zůstávají.
- Čtyři engineering vrstvy jsou společný rámec: prompt/zadání, kontext/zdroje, harness/nástroje+ověření, loop/iterace+rozpočet. Neukazovat neimplementované možnosti jako funkční.

## Výstup — ne jen návrhový dokument
1. Krátká inventura současných akcí: účel, nový domov, kontext dostupnosti, skutečný handler/API. Uvědoměle zachovat primárníworkflow i důležité guardy. Do800slov, ne půlhodinyplánování.
2. Uvést tři kompoziční směry stručně; realizovat nejlépe sedící čistý command/inspect směr v EXISTUJÍCÍM React/TypeScript stacku. Nezakládat další app, nenahradit ji standaloneHTML.
3. Implementovat funkční přeskupení shellu a inspectoru, lepšítypografii/rozestupy/kontrast/responzivitu. Nové komponenty mají vyprávět účel. Používat lokální CSS tokens, ne CDN framework.
4. Návrat k práci maximálně přímý: volba uzlu→detail, psaní→uložení, blok→kontextováakce, běh→detailzdroje. Nastavení má jasné oddělené místo. Žádná ozdobná tlačítka bezhandleru.
5. Screenshot desktopu a mobilu z testovací aplikace a krátký slop audit před/po. Funkce musí odpovídat reálnému API; unavailable/missing zůstanou explicitní.

## Vlastnictví a hranice
POUZE src/**, e2e/**, playwright.config.ts (jen izolace portu/datasetu), .opora/workunits/WU-CLEAN-DESIGN/** a evidence/design-* v TOMTOworktree. Žádné backend změny, jinéworktrees, globální/profilovéconfigy,auth,sessions,produkčnídata,Amplegate,gitpush/rebase/reset/clean. Nedělat paidagentlaunch přes app. Nezasahovat do uložených souborů draftů, CAS, redakce ani modelů runtime.

Parent má rozpracované napojení /api/agents v integračním backend/app.py; ještě není v base tohoto worktree. Existující AgentsWorkspace/NodeActivity lze zasadit do nového shellu, ale před finálním APIE2E převezme tento dvouřádkový backendcommit rodič. Do té doby loading/error musí zůstat pravdivé, případná UIfixture jasněoznačená pouzevtestu.

## Ověření
TDD pro změněné interakce. Zachovat dosavadníassertions; legitimnízměna navigace může upravit přesný selector/cestu, nikoli oslabit funkčnívýsledek. Zejména zachovat e2e text-remount-regression, journal-scope-regression, natural-edit-safety, live-links-regression. Dále view scope/main/readOnly/drawing/keyboard.
Testovací port8742, OPORA_CANVAS_PORT8742, dataroot .data/e2e-design-<unique>; NESPOUŠTĚTserver8740/8738/8741 a produkcisezákazem. Playwright testserver a screenshoty mohou běžet izolovaně; žádný automatickýbrowseruse přístup k osobním stránkám/účtům. Při konfliktu portu stop, nezabíjet cizí procesy.
Spustit npm run build, relevantní E2E a potom celouE2Esadu, uv run pytest -q a uv run ruff check backend tests scripts. Nepipeovat přeshead/tail, neoznačovatwarning/skip zaPASS. Max3opravy stejného selhání; zbývající blocker zapsat.

## Handoff a stop
HANDOFF.md + EVIDENCE.json (skutečné command/exit/skipped,changedpaths,scopegap) a screenshoty. Commit jen vlastní soubory po testech; bez tvrzení nezávislého schválení. Pokud limit běhu, ukončit v bezpečném testovaném řezu, nezvyšovat limit a nespouštět další agenty. Při potřebě uživatelského rozhodnutí/permission/auth stop jen danou část a explicitně popsat. Fable je zde designer a frontendwriter, nikoli nový orchestrátor produktu.
