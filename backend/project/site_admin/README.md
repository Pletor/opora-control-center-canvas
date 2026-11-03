# Správa webu: dokument a design systém projektu

Backend Správy webu (`docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2, PR S-2). Jeden dokument na projekt:
globální nastavení webu (`settings`) a design systém (`design`). Gramatika tokenů je převzatá z otevřeného formátu
`tokens.json` typu Design System, kód typu ne.

- `tokens.py` – gramatika `design.tokens`: jména, barvy a aliasy (bez cyklu, chybějícího cíle, hloubka ≤ 16,
  chybějící téma dědí z prvního), délky, typografie, stíny, vlastní rodiny a limity. Neplatná hodnota se zahodí
  s poznámkou, chyba tvaru je `SiteAdminInvalid` (422).
- `design_system.py` – celý dokument: `settings` (seo, affiliate, email, header, footer, buttons, gdpr) se
  ověřuje podle pevného schématu, tajemství se odmítne (jen `secretRef`); `design` (readme, sections, components,
  assetGroups, cover) a `empty()`.
- `compile.py` – odvozené soubory: `tokens.css` (rozvržení formátu), `tokens.json` a `README.md` (brand book a
  generovaná sekce „Jak systém použít“).
- `store.py` – `projects/<id>/site/design-system.json` s revizí (409 při jiné), assety
  `site/assets/<skupina>/<soubor>`, fonty `site/fonts/<soubor>`, typ podle prvních bajtů a limity velikosti.
- `fixture.py` – zkrácený vzorek systému pro testy.
- Router: `backend/api/project/site_admin_routes.py` (`/api/site-admin…`).

Test: `test_design_system.py`, `test_compile.py`, `test_store.py` (`uv run pytest backend/project/site_admin`).
