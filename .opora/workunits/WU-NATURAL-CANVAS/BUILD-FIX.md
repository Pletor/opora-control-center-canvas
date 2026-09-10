# Parent verification — natural Canvas + oprava buildu

## Skutečný blokující build problém
Parent nezávisle reprodukoval `npm run build` exit1 v natural-canvas: kopírovací skript hledal Excalidraw fonts v neexistujícím lokálním node_modules. Typová kontrola a Vite přitom procházely.
Opus návrh `require.resolve('@excalidraw/excalidraw/package.json')` byl rovněž ověřen a REFUTED: reálný balíček0.18.1 tento subpath neexportuje (`ERR_PACKAGE_PATH_NOT_EXPORTED`). Oprava proto řeší veřejný vstup balíčku, aniž jej spouští, a bere sousední fonts stejně jako původní prod layout.

## RED → GREEN
Přidán tests/test_drawing_assets_build.py před změnou skriptu. Fixture s local i hoisted instalací, pouze veřejný default export, chybějící package.json export, cesta s mezerami, throwing index.js pro důkaz že nedochází k vykonání balíčku, byte-exact kopie/source preservation.
- RED `uv run pytest tests/test_drawing_assets_build.py -q`: exit1,1failed(hoisted ENOENT),1passed(local).
- Produkční změna pouze scripts/copy-drawing-assets.mjs: createRequire(import.meta.url).resolve('@excalidraw/excalidraw'), dirname(entry)/fonts.
- GREEN:2passed; první lint zachytil chybějící explicitní check=False v test subprocess.run, doplněno bez změny assertions.
- Full `uv run pytest -q`: exit0,92passed,2 dependency deprecation warnings.
- `uv run ruff check backend tests scripts`: exit0,All checks passed.
- ÚPLNÝ `npm run build`: exit0, kopie fonts potvrzená; build-parent-fixed.log. Zůstává Vite upozornění na velikost chunků, ne chyba.
- Parent `npx playwright test --reporter=line`: exit0,37passed,1skipped(live coding),e2e-parent.log. Port8741 byl před během prokazatelně volný. Produkce8740/8738 nezměněna.

## Nezávislé review změny buildu
Nová samostatná Claude Code Sonnet evidence-synthesis session bez tools, pouze přesný staged diff + reálné test facts; review-build-envelope.json. Výsledek passed:true,security_concerns:[],logic_errors:[], pouze nezávazné style/future package-layout poznámky. Review se týká POUZE této build opravy, ne celého natural Canvas feature diffu a nijak neřeší ani neobchází oddělenou permission bránu Ample.

## Rozsah převzetí
Není deploy. Původní feature acceptance gaps v HANDOFF.md zůstávají: pending-edit navigation guard, IME/mobile, část backlinks e2e a chooser vztahů. Stav 'map shows actual hierarchy' v parent fullsuite rovněž GREEN; historickou příčinu dřívějšího transient RED nelze tvrdit bez baseline reprodukce. Obecný coding harness dosud není ověřen live testem.
Parent commit jen copy-drawing-assets.mjs, test_drawing_assets_build.py a tato evidence/logs; screenshot side effects a cizí změny nezahrnovat.
