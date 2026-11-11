# Postavit plán práce (F3)

Most z plátna 2 na plátno 3 (`docs/navrhy/2026-11-11-platno-3-folie.md`, „Srdce staví plátno 3“).

- `components/PlanBuildButton.tsx`: tlačítko **Postavit plán práce** v hlavičce stránky (`PlanHeader` `tools`). Stavbu volá callbackem `onBuild(id)` (síť drží `PageEditor` přes `buildPlan`), sám drží jen stav panelu. Stavba pro stránku, v panelu výsledku ještě **Celá doména** a **Otevřít v Editoru →** (`onOpenEditor` nad procesem stránky, dokud není přijatý, nad doménou).
- `logic/plan-build.ts` (+ test): `POST /api/page-plan/{pageId|domainId}/build-plan` (`backend/canvas/plan_from_page.py`), tolerantní převod a věty panelu. Server jen založí nepřijatý návrh grafu srdce; přijímá člověk v OporaHubu (Návrhy grafu). Opakovaná stavba přidá jen rozdíl; čeká-li nepřijatý návrh stavby jiného rozsahu (stránka vs. doména), server vrátí 409 a panel ukáže jeho větu.
- `styles/plan-build.css`, předpona `plan-build`.
