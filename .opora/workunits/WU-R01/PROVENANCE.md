# R01 — průběžná evidence

## Před implementací
Autor implementace: rodičovská Astra, effort není nástrojem doložen. Fable přes Hermes skončil HTTP401; uživatel výslovně povolil vlastní postup Astry. Baseline: 8 pytest PASS (2 dependency deprecation warnings), Vite/TypeScript build PASS. Žádné external Git remote není nakonfigurované.

## T-01 — ověřený pracovní řez
2026-09-09T11:25:50.849744+00:00

Oracle: tests/test_node_specs.py + e2e/node-spec.spec.ts. Finální testy: 25 Python PASS, 8 Playwright PASS; původní 2 warnings zachované. Baseline/node graph kompatibilita zachována. RED příčiny a NEXT NODE jsou v RESULT.md. Produkční source writer byl pouze parent Astra. Před integrací se ověřují hashe nezávislého review; žádné předstírání Fable schválení.

## Integrace primární aplikace
2026-09-09T11:29:55.917088+00:00

Implementační commit: babb50c0b14809833320110dbc7f4bd1504a6d91. Lokální fast-forward do main; žádný remote push. Na 8740 ověřen HTTP health, nové NodeSpec routes, shoda skutečně servírovaného JS s buildem a shoda všech review hashů. Produkční graph digest zůstal nezměněný; před aktualizací ověřena SQLite záloha .data/backups/pre-r01-20260909T112718Z.sqlite. Důkaz: evidence/r01-deployment.json.

Live UI read-only smoke na 8740: tlačítko + Uzel aktivní, správný port, 0 produkčních uzlů a 0 page errors. Screenshot evidence/r01-live.png. Žádný testovací uzel nebyl vytvořen v produkci.
