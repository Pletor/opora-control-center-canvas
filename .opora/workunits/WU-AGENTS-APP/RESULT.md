# WU-AGENTS-APP — uzavřený API řez

## Výsledek
Skutečný backend/app.py připojuje existující agentní router před StaticFiles. /api/agents/sources vrací JSON ze zdrojového katalogu, ne404/statickýfallback. Platí globální Host/Origin/JSON middleware, lokální databáze a lifecycle stejné CanvasService. Tento krok nespouští žádného agenta.

## Důkazy
- Původní RED tohoto integračního testu:404 místo200.
- `uv run pytest -q`: exit0,167passed,3skipped (symlink),2dependencywarnings; přesný výstup pytest.log.
- `uv run ruff check backend tests scripts`: exit0, All checks passed.
- Staged added-line scan: shell0, eval/pickle0, credential assignment0. Heuristika, nikoli úplný securityaudit.
- Claude Sonnet nezávislé review: PASS, security_concerns=[],logic_errors=[]; review-envelope.json + review-bundle.md. Pin TREE64b09a31a67ccdad0801d6080035f2da2172fc64 proti abdf852.
- Test je nad skutečným create_app přes TestClient. Záměrně nedostupné externízdroje jsou fixture; není to tvrzení živého Bridge.

## Hranice uzavření
DONE pouze pro APIregistraci a jejíregresi. Frontendové zobrazení Agenti, celkovýdesign, kontextovýbalík, obecnýharness/loop a produkčnínasazení nejsou tímto krokem hotové. Nový frontendtest e2e/agents-integration.spec.ts zůstává samostatná nedokončená práce a není součástí tohoto commitu. Amplegate nedotčená.

Repo nemá Gitremote; žádný GitHubPR/push/CIclaim. Lokální commit musí zachovat backend/tests identické s reviewedTREE (kontroluje následné gitdiff). Neblokující doporučení review: přidat v budoucnu přímý POST boundary assertion také do tohoto integračního testu; stávající celý backend boundarysuite prošel.
