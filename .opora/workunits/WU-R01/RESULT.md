# R01 — implementovaný editor zadání uzlu

Implementováno a testováno ve vývojovém worktree uvnitř primárního projektu. Nasazení primární instance se ověřuje samostatným read-backem.

## Funkční výsledek
Cíl, non-goals a acceptance se ukládají odděleně od původního purpose. GET nic neukládá. SQLite append-only revize, atomický CAS, posledních 20 revizí v history API. Main je read-only a pravdivě označuje chybějící Git import zadání. Workspaces mají oddělené lokální specifikace.
Rozpracovaný text přežije přepnutí uzlu a chybu zápisu v rámci otevřené aplikace. Pro úplný reload je nutné jej uložit. Stará odpověď nepřepíše jiný scope. UI obsahuje explicitní tlačítko Uložit zadání a konfliktní/error stav.

## EVIDENCE
- 25 backendových testů PASS; evidence/r01-pytest.xml.
- 8 Playwright testů PASS, včetně 6 R01 scénářů; evidence/r01-playwright.json.
- TypeScript/Vite build PASS, Ruff check + format PASS, git diff whitespace check PASS.
- Backend má 2 již existující dependency deprecation warnings (FastAPI/Starlette), nikoli nové test failures.
- Review a případné finální doplnění: REVIEW.json a REVIEW-FINAL.json.
- Screenshoty r01-editor.png a r01-mobile.png jsou izolovaná testovací data, ne změněný produkční projekt.

## RED → GREEN
1. Chybějící GET route 404 → API persistence a restart PASS.
2. Stará revize se přepsala 200 → CAS odmítne 409 a zachová historii.
3. Nevalidní payload prošel a test port byl odmítnut → striktní validation a oddělený loopback port.
4. UI pole chybělo → funkční editor a reload PASS.
5. Přepnutí uzlu smazalo neuložený text → scoped draft cache PASS.
6. Main history měla chybný tvar a DB chyba vracela 500 → konzistentní read-only history a safe JSON503.
7. UI zobrazovalo jiný port než skutečný → source-backed label z location.port.

## DISCOVERED / NEXT NODE
Git export/import lokálního zadání; materiály a kresba u uzlu; context bundle a terminálový adapter; paměť a knihovna komponent. Žádná z těchto funkcí není touto dodávkou prohlášena za hotovou. Žádný external push/merge ani agent dispatch.
